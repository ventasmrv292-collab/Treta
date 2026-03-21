"""
Motor de estrategias: carga estrategias activas, obtiene velas de DB, ejecuta estrategias,
genera señales y las ejecuta (signal_event -> validación riesgo -> trade -> ledger -> logs).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.models.strategy import Strategy
from app.models.strategy_runtime_config import StrategyRuntimeConfig
from app.models.candle import Candle
from app.models.trade import Trade
from app.models.paper_account import PaperAccount
from app.models.risk_profile import RiskProfile
from app.models.signal_event import SignalEvent
from app.models.account_ledger import AccountLedger
from app.services.strategies import get_strategy_fn, STRATEGY_REGISTRY
from app.services.strategies.base import StrategySignal
from app.services.trade_service import prepare_n8n_trade, n8n_create_to_trade, has_exposure_conflict
from app.services.order_execution import classify_entry, pending_order_triggered
from app.models.pending_order import PendingOrder
from app.schemas.trade import N8nTradeCreate
from app.services.bot_log_service import (
    log_event as bot_log_event,
    MODULE_STRATEGY,
    EVENT_STRATEGY_SIGNAL_CREATED,
    EVENT_SIGNAL_REJECTED,
    EVENT_TRADE_OPENED,
    EVENT_RISK_LIMIT_BLOCK,
    EVENT_DUPLICATE_SIGNAL,
)
from app.services.trading_capital import (
    calc_margin_used,
    calc_exit_fee,
    estimate_total_cost_usdt,
    estimate_total_cost_pct,
    compute_expected_net_rr,
    compute_min_tp_for_net_rr,
    check_tp_within_limits,
)
from app.services.pushover_service import send_trade_opened
from app.services.market_regime import (
    DEFAULT_MARKET_REGIME_CONFIG,
    MarketRegimeSnapshot,
    classify_market_regime,
    evaluate_long_permission,
    evaluate_short_permission,
    get_reference_timeframe,
)

logger = logging.getLogger(__name__)

SYMBOL = "BTCUSDT"
CANDLES_LIMIT = 200
DEFAULT_LEVERAGE = 10
DEFAULT_QUANTITY = Decimal("0.001")


async def _get_default_account_and_profile(session: AsyncSession) -> tuple[int | None, int | None, int]:
    """
    Primera cuenta paper activa y risk profile a usar (cuenta.default_risk_profile_id o "V2 20x Realista").
    Retorna (account_id, risk_profile_id, leverage). Leverage sale del perfil (allowed_leverage_json, primer valor) o 20.
    """
    r = await session.execute(select(PaperAccount).where(PaperAccount.status == "ACTIVE").order_by(PaperAccount.id).limit(1))
    acc = r.scalar_one_or_none()
    account_id = acc.id if acc else None
    risk_profile_id = None
    if acc and acc.default_risk_profile_id is not None:
        risk_profile_id = acc.default_risk_profile_id
    if risk_profile_id is None:
        rp = await session.execute(
            select(RiskProfile).where(RiskProfile.name == "V2 20x Realista").limit(1)
        )
        profile = rp.scalar_one_or_none()
        if profile:
            risk_profile_id = profile.id
    if risk_profile_id is None:
        rp = await session.execute(select(RiskProfile).order_by(RiskProfile.id).limit(1))
        profile = rp.scalar_one_or_none()
        risk_profile_id = profile.id if profile else None
    leverage = 20
    if risk_profile_id is not None:
        prof = (await session.execute(select(RiskProfile).where(RiskProfile.id == risk_profile_id))).scalar_one_or_none()
        if prof and prof.allowed_leverage_json:
            try:
                data = json.loads(prof.allowed_leverage_json)
                if isinstance(data, list) and len(data) > 0 and isinstance(data[0], (int, float)):
                    leverage = int(data[0])
            except (json.JSONDecodeError, TypeError):
                pass
    return (account_id, risk_profile_id, leverage)


SHORT_EXPERIMENT_STRATEGIES = frozenset({"breakout_volume_v2", "vwap_snapback_v2", "ema_pullback_v2"})


async def _resolve_risk_profile_for_signal(
    session: AsyncSession,
    signal: StrategySignal,
    default_risk_profile_id: int | None,
    default_leverage: int,
) -> tuple[int | None, int]:
    """Perfil dedicado SHORT_EXPERIMENT_20X_R075 para señales SHORT de las estrategias v2 del experimento."""
    if signal.position_side == "SHORT" and signal.strategy_name in SHORT_EXPERIMENT_STRATEGIES:
        r = await session.execute(
            select(RiskProfile).where(RiskProfile.name == "SHORT_EXPERIMENT_20X_R075").limit(1)
        )
        prof = r.scalar_one_or_none()
        if prof:
            lev = default_leverage
            if prof.allowed_leverage_json:
                try:
                    data = json.loads(prof.allowed_leverage_json)
                    if isinstance(data, list) and len(data) > 0:
                        lev = int(data[0])
                except (json.JSONDecodeError, TypeError):
                    pass
            return prof.id, lev
    return default_risk_profile_id, default_leverage


def _trade_regime_fields_immediate(snapshot: MarketRegimeSnapshot) -> dict:
    """Campos de régimen en apertura inmediata (sin pending)."""
    return {
        "market_regime_detected": snapshot.regime,
        "regime_timeframe_used": snapshot.timeframe_used,
        "cooldown_active_at_open": snapshot.cooldown_active,
        "market_regime_at_signal": snapshot.regime,
        "regime_timeframe_at_signal": snapshot.timeframe_used,
        "cooldown_active_at_signal": snapshot.cooldown_active,
        "regime_changed_since_pending": False,
        "entry_source": "IMMEDIATE",
    }


def _trade_regime_fields_from_pending_fill(
    regime_at_fill: MarketRegimeSnapshot,
    pending: PendingOrder,
) -> dict:
    """Régimen al ejecutar vs al crear la orden pendiente."""
    sig_reg = pending.market_regime_detected_at_create
    sig_tf = pending.regime_timeframe_used_at_create
    sig_cd = pending.cooldown_active_at_create
    changed: bool | None = None
    if sig_reg is not None:
        changed = regime_at_fill.regime != sig_reg
    return {
        "market_regime_detected": regime_at_fill.regime,
        "regime_timeframe_used": regime_at_fill.timeframe_used,
        "cooldown_active_at_open": regime_at_fill.cooldown_active,
        "market_regime_at_signal": sig_reg,
        "regime_timeframe_at_signal": sig_tf,
        "cooldown_active_at_signal": sig_cd,
        "regime_changed_since_pending": changed,
        "entry_source": "PENDING_FILL",
        "pending_order_id": pending.id,
    }


async def _get_runtime_config(
    session: AsyncSession,
    strategy: Strategy,
    symbol: str,
    timeframe: str,
) -> StrategyRuntimeConfig | None:
    """Configuración granular por estrategia/símbolo/timeframe (si existe)."""
    result = await session.execute(
        select(StrategyRuntimeConfig).where(
            StrategyRuntimeConfig.strategy_id == strategy.id,
            StrategyRuntimeConfig.symbol == symbol,
            StrategyRuntimeConfig.timeframe == timeframe,
        )
    )
    return result.scalar_one_or_none()


def _signal_to_n8n_payload(
    signal: StrategySignal,
    account_id: int | None,
    risk_profile_id: int | None,
    idempotency_key: str,
    quantity: Decimal,
    leverage: int,
    strategy_id: int | None = None,
    entry_price_override: Decimal | None = None,
    entry_order_type: str = "MARKET",
) -> N8nTradeCreate:
    entry = entry_price_override if entry_price_override is not None else signal.entry_price
    return N8nTradeCreate(
        source="BACKEND",
        strategy_id=strategy_id,
        symbol=signal.symbol,
        market="PERP",
        strategy_family=signal.strategy_family,
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        timeframe=signal.timeframe,
        position_side=signal.position_side,
        leverage=leverage,
        entry_price=entry,
        take_profit=signal.take_profit,
        stop_loss=signal.stop_loss,
        quantity=quantity,
        entry_order_type=entry_order_type,
        maker_taker_entry="TAKER",
        signal_timestamp=datetime.now(timezone.utc),
        strategy_params_json=json.dumps(signal.metadata, default=str) if signal.metadata else None,
        notes=f"Auto signal {signal.strategy_name}",
        account_id=account_id,
        risk_profile_id=risk_profile_id,
        idempotency_key=idempotency_key,
    )


# Tolerancia para comparaciones float (evitar rechazos por redondeo: rr=1.2 vs min=1.20)
_RR_TOLERANCE = 1e-6
# Tolerancia Decimal para expected_net_rr vs min_net_rr_ratio (evitar rechazos por redondeo)
_NET_RR_TOLERANCE = Decimal("0.0001")


async def _load_closed_candles(
    session: AsyncSession,
    symbol: str,
    interval: str,
    limit: int,
) -> list[dict]:
    result = await session.execute(
        select(Candle)
        .where(Candle.symbol == symbol, Candle.interval == interval, Candle.is_closed == True)
        .order_by(Candle.open_time.desc())
        .limit(limit)
    )
    rows = list(result.scalars().all())
    return [
        {
            "symbol": c.symbol,
            "open_time": c.open_time,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in reversed(rows)
    ]


async def _create_regime_blocked_signal_event(
    session: AsyncSession,
    signal: StrategySignal,
    reason: str,
    regime_detected: str,
    regime_timeframe: str,
    regime_reason: str,
) -> None:
    idempotency_key = f"backend|{signal.strategy_family}|{signal.strategy_name}|{signal.timeframe}|{signal.entry_price}|{signal.symbol}"
    payload = {
        "position_side": signal.position_side,
        "entry_price": str(signal.entry_price),
        "take_profit": str(signal.take_profit) if signal.take_profit else None,
        "stop_loss": str(signal.stop_loss) if signal.stop_loss else None,
        "metadata": {
            **(signal.metadata or {}),
            "market_regime_detected": regime_detected,
            "market_regime_reason": regime_reason,
            "regime_timeframe_used": regime_timeframe,
        },
    }
    signal_event = SignalEvent(
        source="BACKEND",
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_family=signal.strategy_family,
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        payload_json=json.dumps(payload, default=str),
        status="REJECTED",
        decision_reason=reason,
        idempotency_key=idempotency_key,
    )
    session.add(signal_event)
    await session.flush()
    await bot_log_event(
        session,
        "WARN",
        MODULE_STRATEGY,
        EVENT_SIGNAL_REJECTED,
        f"Signal rejected (market regime): {reason}",
        context={
            "reason": reason,
            "strategy": signal.strategy_name,
            "timeframe": signal.timeframe,
            "market_regime_detected": regime_detected,
            "regime_timeframe_used": regime_timeframe,
        },
        related_signal_event_id=signal_event.id,
    )
    await session.commit()


async def _create_ambiguous_bar_event(
    session: AsyncSession,
    *,
    strategy_family: str,
    strategy_name: str,
    strategy_version: str,
    timeframe: str,
    symbol: str,
    reason: str,
    regime_snapshot: MarketRegimeSnapshot,
) -> None:
    """Registra rechazo por barra ambigua (p. ej. breakout LONG y SHORT en la misma vela)."""
    idempotency_key = f"backend|{strategy_family}|{strategy_name}|{timeframe}|AMBIGUOUS|{symbol}"
    payload = {
        "position_side": None,
        "entry_price": None,
        "take_profit": None,
        "stop_loss": None,
        "metadata": {
            "market_regime_detected": regime_snapshot.regime,
            "market_regime_reason": regime_snapshot.reason,
            "regime_timeframe_used": regime_snapshot.timeframe_used,
            "cooldown_active": regime_snapshot.cooldown_active,
        },
    }
    signal_event = SignalEvent(
        source="BACKEND",
        symbol=symbol,
        timeframe=timeframe,
        strategy_family=strategy_family,
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        payload_json=json.dumps(payload, default=str),
        status="REJECTED",
        decision_reason=reason,
        idempotency_key=idempotency_key,
    )
    session.add(signal_event)
    await session.flush()
    await bot_log_event(
        session,
        "WARN",
        MODULE_STRATEGY,
        EVENT_SIGNAL_REJECTED,
        f"Signal rejected (ambiguous bar): {reason}",
        context={
            "reason": reason,
            "strategy": strategy_name,
            "timeframe": timeframe,
            "market_regime_detected": regime_snapshot.regime,
        },
        related_signal_event_id=signal_event.id,
    )
    await session.commit()


def _validate_signal_limits(
    signal: StrategySignal,
    cfg: StrategyRuntimeConfig,
) -> tuple[bool, str]:
    """Valida min_stop_distance_pct y min_rr_ratio. Retorna (ok, reason)."""
    entry = float(signal.entry_price)
    if entry <= 0:
        return False, "INVALID_ENTRY_PRICE"
    stop = float(signal.stop_loss) if signal.stop_loss else None
    tp = float(signal.take_profit) if signal.take_profit else None
    if stop is None:
        return True, ""
    risk_dist = abs(entry - stop)
    stop_pct = (risk_dist / entry) * 100
    if cfg.min_stop_distance_pct is not None and stop_pct < float(cfg.min_stop_distance_pct) - _RR_TOLERANCE:
        return False, f"STOP_TOO_CLOSE: stop_dist_pct={round(stop_pct, 4)}% < min={cfg.min_stop_distance_pct}"
    if cfg.min_rr_ratio is not None and tp is not None and risk_dist > 0:
        reward_dist = abs(tp - entry)
        rr = reward_dist / risk_dist
        min_rr = float(cfg.min_rr_ratio)
        if rr < min_rr - _RR_TOLERANCE:
            return False, f"RR_BELOW_MIN: rr={round(rr, 2)} < min_rr_ratio={cfg.min_rr_ratio}"
    return True, ""


async def _execute_signal(
    session: AsyncSession,
    signal: StrategySignal,
    current_price: Decimal,
    account_id: int | None,
    risk_profile_id: int | None,
    leverage: int,
    strategy_id: int | None = None,
    runtime_cfg: StrategyRuntimeConfig | None = None,
    regime_snapshot: MarketRegimeSnapshot | None = None,
) -> Trade | None:
    """
    Crea signal_event, clasifica entrada (MARKET/LIMIT/STOP/STALE), y o bien abre trade (MARKET),
    crea orden pendiente (LIMIT/STOP) o marca señal STALE. Retorna trade si se abrió, None en caso contrario.
    """
    idempotency_key = f"backend|{signal.strategy_family}|{signal.strategy_name}|{signal.timeframe}|{signal.entry_price}|{signal.symbol}"
    meta = dict(signal.metadata or {})
    if regime_snapshot is not None:
        meta["market_regime_detected"] = regime_snapshot.regime
        meta["regime_timeframe_used"] = regime_snapshot.timeframe_used
        meta["cooldown_active_at_signal"] = regime_snapshot.cooldown_active
    payload_json = json.dumps({
        "position_side": signal.position_side,
        "entry_price": str(signal.entry_price),
        "take_profit": str(signal.take_profit) if signal.take_profit else None,
        "stop_loss": str(signal.stop_loss) if signal.stop_loss else None,
        "metadata": meta,
    }, default=str)
    signal_event = SignalEvent(
        source="BACKEND",
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        strategy_family=signal.strategy_family,
        strategy_name=signal.strategy_name,
        strategy_version=signal.strategy_version,
        payload_json=payload_json,
        status="RECEIVED",
        idempotency_key=idempotency_key,
    )
    session.add(signal_event)
    await session.flush()

    if runtime_cfg is not None:
        ok, reason = _validate_signal_limits(signal, runtime_cfg)
        if not ok:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = reason
            await bot_log_event(
                session,
                "WARN",
                MODULE_STRATEGY,
                EVENT_SIGNAL_REJECTED,
                f"Signal rejected (limits): {reason}",
                context={"reason": reason, "strategy": signal.strategy_name, "timeframe": signal.timeframe},
                related_signal_event_id=signal_event.id,
            )
            await session.commit()
            return None

    # Clasificación de entrada realista: MARKET / LIMIT / STOP / STALE
    entry_tol = float(runtime_cfg.entry_tolerance_pct) if runtime_cfg and runtime_cfg.entry_tolerance_pct is not None else 0.1
    max_dev = float(runtime_cfg.max_entry_deviation_pct) if runtime_cfg and runtime_cfg.max_entry_deviation_pct is not None else 2.0
    # Sin bar_high/bar_low aquí: evitar lookahead. La señal se genera al cierre de la vela;
    # no usamos high/low de esa misma vela para "rellenar en la misma barra". Los fills
    # intrabar solo ocurren al evaluar órdenes PENDIENTES (creadas en runs anteriores)
    # con la vela actual en _evaluate_pending_orders.
    decision = classify_entry(
        signal, current_price,
        entry_tolerance_pct=entry_tol,
        max_entry_deviation_pct=max_dev,
        bar_high=None,
        bar_low=None,
    )

    if decision.action == "STALE":
        signal_event.status = "STALE"
        signal_event.decision_reason = decision.reason
        await bot_log_event(
            session,
            "WARN",
            MODULE_STRATEGY,
            EVENT_SIGNAL_REJECTED,
            f"Signal stale/missed: {decision.reason}",
            context={"reason": decision.reason, "strategy": signal.strategy_name, "entry": str(signal.entry_price), "current": str(current_price)},
            related_signal_event_id=signal_event.id,
        )
        await session.commit()
        return None

    if decision.action in ("LIMIT", "STOP"):
        # Crear orden pendiente; no abrir trade aún
        expires_at = None
        if runtime_cfg and runtime_cfg.pending_order_expiry_minutes is not None:
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=runtime_cfg.pending_order_expiry_minutes)
        pending_kw: dict = dict(
            signal_event_id=signal_event.id,
            strategy_id=strategy_id,
            account_id=account_id,
            risk_profile_id=risk_profile_id,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            position_side=signal.position_side,
            order_type=decision.order_type,
            trigger_price=decision.fill_price or signal.entry_price,
            quantity=DEFAULT_QUANTITY,
            leverage=leverage,
            take_profit=signal.take_profit,
            stop_loss=signal.stop_loss,
            strategy_family=signal.strategy_family,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            idempotency_key=idempotency_key,
            payload_json=payload_json,
            status="PENDING",
            expires_at=expires_at,
            expires_after_bars=runtime_cfg.pending_order_expiry_bars if runtime_cfg else None,
        )
        if regime_snapshot is not None:
            pending_kw["market_regime_detected_at_create"] = regime_snapshot.regime
            pending_kw["regime_timeframe_used_at_create"] = regime_snapshot.timeframe_used
            pending_kw["cooldown_active_at_create"] = regime_snapshot.cooldown_active
        pending = PendingOrder(**pending_kw)
        session.add(pending)
        signal_event.status = "PENDING_ORDER"
        signal_event.decision_reason = decision.reason
        await bot_log_event(
            session,
            "INFO",
            MODULE_STRATEGY,
            EVENT_STRATEGY_SIGNAL_CREATED,
            f"Pending {decision.order_type} order created: {signal.strategy_name} @ {decision.fill_price}",
            context={"order_type": decision.order_type, "trigger": str(decision.fill_price), "strategy": signal.strategy_name},
            related_signal_event_id=signal_event.id,
        )
        await session.commit()
        return None

    # MARKET: entrada inmediata al precio actual (con slippage en prepare_n8n_trade)
    payload = _signal_to_n8n_payload(
        signal, account_id, risk_profile_id, idempotency_key, DEFAULT_QUANTITY, leverage,
        strategy_id=strategy_id,
        entry_price_override=decision.fill_price,
        entry_order_type="MARKET",
    )

    try:
        data_override = await prepare_n8n_trade(session, payload)
    except ValueError as e:
        msg = str(e)
        if "DUPLICATE" in msg:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = "DUPLICATE_SIGNAL"
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_DUPLICATE_SIGNAL, f"Signal rejected: {msg}", context={"idempotency_key": idempotency_key}, related_signal_event_id=signal_event.id)
        elif "RISK_LIMIT" in msg:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = msg
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_RISK_LIMIT_BLOCK, f"Signal rejected: {msg}", context={"reason": msg}, related_signal_event_id=signal_event.id)
        else:
            signal_event.status = "REJECTED"
            signal_event.decision_reason = msg
            await bot_log_event(session, "WARN", MODULE_STRATEGY, EVENT_SIGNAL_REJECTED, f"Signal rejected: {msg}", context={"reason": msg}, related_signal_event_id=signal_event.id)
        await session.commit()
        return None

    # --- FASE 1: validación expected_net_rr y ajuste de TP (límites max_tp_*) ---
    entry_price = Decimal(str(payload.entry_price))
    stop_loss = Decimal(str(payload.stop_loss)) if payload.stop_loss else None
    take_profit_base = Decimal(str(payload.take_profit)) if payload.take_profit else None
    quantity = data_override.get("quantity") or Decimal(str(payload.quantity))
    entry_fee = data_override.get("entry_fee") or Decimal("0")
    entry_notional = data_override.get("entry_notional") or (quantity * entry_price)
    fee_rate = data_override.get("fee_rate")
    slippage_est_usdt = data_override.get("slippage_est_usdt") or Decimal("0")

    if (
        runtime_cfg is not None
        and take_profit_base is not None
        and stop_loss is not None
        and fee_rate is not None
        and runtime_cfg.min_net_rr_ratio is not None
    ):
        position_side = payload.position_side
        # Exit fee estimada usando notional al TP final (más precisa que ≈ entry_fee)
        exit_notional_at_tp = quantity * take_profit_base
        exit_fee_est = calc_exit_fee(exit_notional_at_tp, fee_rate)
        estimated_total_cost_usdt = estimate_total_cost_usdt(entry_fee, exit_fee_est, slippage_est_usdt)
        expected_net_rr, _, _ = compute_expected_net_rr(
            entry_price, take_profit_base, stop_loss, quantity,
            position_side, entry_fee, exit_fee_est, slippage_est_usdt,
        )
        min_net_rr = runtime_cfg.min_net_rr_ratio

        if expected_net_rr < min_net_rr - _NET_RR_TOLERANCE:
            tp_min = compute_min_tp_for_net_rr(
                entry_price, stop_loss, quantity, position_side,
                min_net_rr, entry_fee, fee_rate, slippage_est_usdt,
            )
            ok_tp, reason_tp = check_tp_within_limits(
                entry_price, tp_min, stop_loss, position_side,
                runtime_cfg.max_tp_distance_pct,
                runtime_cfg.max_tp_rr_ratio,
            )
            if not ok_tp:
                signal_event.status = "REJECTED"
                signal_event.decision_reason = "NET_RR_REQUIRES_UNREASONABLE_TP"
                await bot_log_event(
                    session, "WARN", MODULE_STRATEGY, EVENT_SIGNAL_REJECTED,
                    f"Signal rejected: {reason_tp} (expected_net_rr requires TP beyond limits)",
                    context={"reason": reason_tp, "strategy": signal.strategy_name, "timeframe": signal.timeframe},
                    related_signal_event_id=signal_event.id,
                )
                await session.commit()
                return None
            # Ajustar TP al mínimo que cumple min_net_rr
            data_override["take_profit"] = tp_min
            exit_notional_at_tp = quantity * tp_min
            exit_fee_est = calc_exit_fee(exit_notional_at_tp, fee_rate)
            expected_net_rr, _, _ = compute_expected_net_rr(
                entry_price, tp_min, stop_loss, quantity,
                position_side, entry_fee, exit_fee_est, slippage_est_usdt,
            )
            estimated_total_cost_usdt = estimate_total_cost_usdt(entry_fee, exit_fee_est, slippage_est_usdt)

        estimated_total_cost_pct_val = estimate_total_cost_pct(estimated_total_cost_usdt, entry_notional)
        data_override["expected_net_rr_at_open"] = expected_net_rr
        data_override["estimated_total_cost_usdt_at_open"] = estimated_total_cost_usdt
        data_override["estimated_total_cost_pct_at_open"] = estimated_total_cost_pct_val
        data_override["take_profit_base_at_open"] = take_profit_base
    elif take_profit_base is not None and stop_loss is not None and fee_rate is not None:
        # Sin min_net_rr_ratio: solo persistir métricas ex ante si tenemos TP
        exit_notional_at_tp = quantity * take_profit_base
        exit_fee_est = calc_exit_fee(exit_notional_at_tp, fee_rate)
        estimated_total_cost_usdt = estimate_total_cost_usdt(entry_fee, exit_fee_est, slippage_est_usdt)
        expected_net_rr, _, _ = compute_expected_net_rr(
            entry_price, take_profit_base, stop_loss, quantity,
            payload.position_side, entry_fee, exit_fee_est, slippage_est_usdt,
        )
        data_override["expected_net_rr_at_open"] = expected_net_rr
        data_override["estimated_total_cost_usdt_at_open"] = estimated_total_cost_usdt
        data_override["estimated_total_cost_pct_at_open"] = estimate_total_cost_pct(estimated_total_cost_usdt, entry_notional)
        data_override["take_profit_base_at_open"] = take_profit_base

    # No persistir en Trade campos solo usados para cálculo (fee_rate, slippage_est_usdt)
    data_override.pop("fee_rate", None)
    data_override.pop("slippage_est_usdt", None)

    data = n8n_create_to_trade(payload, data_override)
    if regime_snapshot is not None:
        data.update(_trade_regime_fields_immediate(regime_snapshot))
    trade = Trade(**data)
    trade.signal_event_id = signal_event.id
    if strategy_id is not None:
        trade.strategy_id = strategy_id
    session.add(trade)
    await session.flush()

    signal_event.status = "ACCEPTED"
    signal_event.trade_id = trade.id
    signal_event.processed_at = datetime.now(timezone.utc)

    # Ledger: TRADE_OPEN
    if trade.account_id is not None:
        acc = (await session.execute(select(PaperAccount).where(PaperAccount.id == trade.account_id))).scalar_one_or_none()
        if acc:
            balance_before = acc.current_balance_usdt or Decimal("0")
            acc.used_margin_usdt = (acc.used_margin_usdt or Decimal("0")) + (trade.margin_used_usdt or Decimal("0"))
            acc.current_balance_usdt = balance_before - (trade.entry_fee or Decimal("0"))
            acc.available_balance_usdt = acc.current_balance_usdt - acc.used_margin_usdt
            balance_after = acc.current_balance_usdt
            ledger = AccountLedger(
                account_id=trade.account_id,
                trade_id=trade.id,
                event_type="TRADE_OPEN",
                amount_usdt=-(trade.entry_fee or Decimal("0")) - (trade.margin_used_usdt or Decimal("0")),
                balance_before_usdt=balance_before,
                balance_after_usdt=balance_after,
                meta_json=json.dumps({"trade_id": trade.id, "entry_fee": str(trade.entry_fee), "margin_used": str(trade.margin_used_usdt)}),
            )
            session.add(ledger)

    await bot_log_event(
        session,
        "INFO",
        MODULE_STRATEGY,
        EVENT_STRATEGY_SIGNAL_CREATED,
        f"Trade #{trade.id} opened from signal: {signal.strategy_name} {signal.position_side}",
        context={"trade_id": trade.id, "strategy": signal.strategy_name, "position_side": signal.position_side},
        related_trade_id=trade.id,
        related_signal_event_id=signal_event.id,
    )
    await bot_log_event(
        session,
        "INFO",
        "trade_service",
        EVENT_TRADE_OPENED,
        f"Trade #{trade.id} opened: {trade.symbol} {trade.position_side}",
        context={"symbol": trade.symbol, "position_side": trade.position_side},
        related_trade_id=trade.id,
    )
    asyncio.create_task(send_trade_opened(trade))
    await session.commit()
    return trade


def _pending_order_to_payload(pending: PendingOrder) -> N8nTradeCreate:
    """Construye N8nTradeCreate desde una orden pendiente (para fill)."""
    maker_taker = "MAKER" if pending.order_type == "LIMIT" else "TAKER"
    return N8nTradeCreate(
        source="BACKEND",
        strategy_id=pending.strategy_id,
        symbol=pending.symbol,
        market="PERP",
        strategy_family=pending.strategy_family,
        strategy_name=pending.strategy_name,
        strategy_version=pending.strategy_version,
        timeframe=pending.timeframe,
        position_side=pending.position_side,
        leverage=pending.leverage,
        entry_price=pending.trigger_price,
        take_profit=pending.take_profit,
        stop_loss=pending.stop_loss,
        quantity=pending.quantity,
        entry_order_type=pending.order_type,
        maker_taker_entry=maker_taker,
        signal_timestamp=datetime.now(timezone.utc),
        strategy_params_json=pending.payload_json,
        notes=f"Fill pending {pending.order_type} {pending.strategy_name}",
        account_id=pending.account_id,
        risk_profile_id=pending.risk_profile_id,
        idempotency_key=pending.idempotency_key,
    )


async def _fill_pending_order(
    session: AsyncSession,
    pending: PendingOrder,
    regime_at_fill: MarketRegimeSnapshot | None = None,
) -> Trade | None:
    """Ejecuta el fill de una orden pendiente: crea trade, actualiza orden y signal_event."""
    payload = _pending_order_to_payload(pending)
    try:
        data_override = await prepare_n8n_trade(session, payload)
    except ValueError as e:
        logger.warning("fill_pending_order rejected: %s", e)
        return None
    entry_price = Decimal(str(payload.entry_price))
    quantity = data_override.get("quantity") or pending.quantity
    stop_loss = payload.stop_loss
    take_profit_base = Decimal(str(payload.take_profit)) if payload.take_profit else None
    if (
        take_profit_base is not None
        and stop_loss is not None
        and (fee_rate := data_override.get("fee_rate")) is not None
    ):
        entry_fee = data_override.get("entry_fee") or Decimal("0")
        slippage_est = data_override.get("slippage_est_usdt") or Decimal("0")
        exit_notional_at_tp = quantity * take_profit_base
        exit_fee_est = calc_exit_fee(exit_notional_at_tp, fee_rate)
        expected_net_rr, _, _ = compute_expected_net_rr(
            entry_price, take_profit_base, stop_loss, quantity,
            payload.position_side, entry_fee, exit_fee_est, slippage_est,
        )
        data_override["expected_net_rr_at_open"] = expected_net_rr
        data_override["estimated_total_cost_usdt_at_open"] = estimate_total_cost_usdt(
            entry_fee, exit_fee_est, slippage_est
        )
        data_override["estimated_total_cost_pct_at_open"] = estimate_total_cost_pct(
            data_override["estimated_total_cost_usdt_at_open"], quantity * entry_price
        )
        data_override["take_profit_base_at_open"] = take_profit_base
    data_override.pop("fee_rate", None)
    data_override.pop("slippage_est_usdt", None)
    data = n8n_create_to_trade(payload, data_override)
    if regime_at_fill is not None:
        data.update(_trade_regime_fields_from_pending_fill(regime_at_fill, pending))
    trade = Trade(**data)
    trade.signal_event_id = pending.signal_event_id
    trade.strategy_id = pending.strategy_id
    session.add(trade)
    await session.flush()

    pending.status = "FILLED"
    pending.trade_id = trade.id
    pending.filled_at = datetime.now(timezone.utc)
    if regime_at_fill is not None:
        pending.market_regime_detected_at_fill = regime_at_fill.regime
        pending.regime_timeframe_used_at_fill = regime_at_fill.timeframe_used
        pending.cooldown_active_at_fill = regime_at_fill.cooldown_active
    signal_event = (await session.execute(select(SignalEvent).where(SignalEvent.id == pending.signal_event_id))).scalar_one_or_none()
    if signal_event:
        signal_event.status = "ACCEPTED"
        signal_event.trade_id = trade.id
        signal_event.processed_at = datetime.now(timezone.utc)

    if trade.account_id is not None:
        acc = (await session.execute(select(PaperAccount).where(PaperAccount.id == trade.account_id))).scalar_one_or_none()
        if acc:
            balance_before = acc.current_balance_usdt or Decimal("0")
            acc.used_margin_usdt = (acc.used_margin_usdt or Decimal("0")) + (trade.margin_used_usdt or Decimal("0"))
            acc.current_balance_usdt = balance_before - (trade.entry_fee or Decimal("0"))
            acc.available_balance_usdt = acc.current_balance_usdt - acc.used_margin_usdt
            ledger = AccountLedger(
                account_id=trade.account_id,
                trade_id=trade.id,
                event_type="TRADE_OPEN",
                amount_usdt=-(trade.entry_fee or Decimal("0")) - (trade.margin_used_usdt or Decimal("0")),
                balance_before_usdt=balance_before,
                balance_after_usdt=acc.current_balance_usdt,
                meta_json=json.dumps({"trade_id": trade.id, "entry_fee": str(trade.entry_fee), "margin_used": str(trade.margin_used_usdt)}),
            )
            session.add(ledger)
    await bot_log_event(
        session, "INFO", MODULE_STRATEGY, EVENT_STRATEGY_SIGNAL_CREATED,
        f"Trade #{trade.id} opened from pending {pending.order_type}: {pending.strategy_name}",
        context={"trade_id": trade.id, "order_type": pending.order_type},
        related_trade_id=trade.id, related_signal_event_id=pending.signal_event_id,
    )
    await bot_log_event(
        session, "INFO", "trade_service", EVENT_TRADE_OPENED,
        f"Trade #{trade.id} opened: {trade.symbol} {trade.position_side}",
        context={"symbol": trade.symbol, "position_side": trade.position_side},
        related_trade_id=trade.id,
    )
    asyncio.create_task(send_trade_opened(trade))
    return trade


async def _evaluate_pending_orders(
    session: AsyncSession,
    symbol: str,
    timeframe: str,
    bar_high: Decimal,
    bar_low: Decimal,
    regime_snapshot: MarketRegimeSnapshot | None = None,
) -> list[Trade]:
    """Evalúa órdenes PENDING para symbol/timeframe con la vela (high, low); llena las activadas y retorna trades abiertos."""
    from sqlalchemy import and_
    result = await session.execute(
        select(PendingOrder).where(
            and_(
                PendingOrder.symbol == symbol,
                PendingOrder.timeframe == timeframe,
                PendingOrder.status == "PENDING",
            )
        )
    )
    pendings = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    opened: list[Trade] = []
    for po in pendings:
        if po.expires_at is not None and now >= po.expires_at:
            po.status = "EXPIRED"
            signal_ev = (await session.execute(select(SignalEvent).where(SignalEvent.id == po.signal_event_id))).scalar_one_or_none()
            if signal_ev:
                signal_ev.status = "EXPIRED"
                signal_ev.decision_reason = "PENDING_ORDER_EXPIRED_TIME"
            logger.debug("Pending order %s expired (time)", po.id)
            continue
        if pending_order_triggered(po.order_type, po.trigger_price, po.position_side, bar_high, bar_low):
            trade = await _fill_pending_order(session, po, regime_at_fill=regime_snapshot)
            if trade:
                opened.append(trade)
    return opened


async def run_strategies_for_timeframe(interval: str) -> list[Trade]:
    """
    Carga estrategias activas que apliquen al intervalo, obtiene velas cerradas de DB,
    ejecuta cada estrategia y procesa señales. Retorna lista de trades abiertos en esta ejecución.
    """
    opened: list[Trade] = []
    async with async_session_maker() as session:
        result = await session.execute(
            select(Strategy).where(Strategy.active == True).order_by(Strategy.id)
        )
        strategies = list(result.scalars().all())
        if not strategies:
            return opened

        available_tfs = {interval, "1h", "4h", "30m"}
        regime_tf = get_reference_timeframe(interval, available_tfs)
        candles = await _load_closed_candles(session, SYMBOL, interval, CANDLES_LIMIT)
        if len(candles) < 20:
            logger.debug("strategy_engine: not enough candles for %s (%d)", interval, len(candles))
            return opened
        regime_candles = await _load_closed_candles(session, SYMBOL, regime_tf, CANDLES_LIMIT)
        if len(regime_candles) < max(DEFAULT_MARKET_REGIME_CONFIG.ema_slow_period, 60):
            fallback_tf = "1h"
            regime_tf = fallback_tf
            regime_candles = await _load_closed_candles(session, SYMBOL, fallback_tf, CANDLES_LIMIT)
        regime_snapshot = classify_market_regime(
            candles=regime_candles if regime_candles else candles,
            timeframe_used=regime_tf if regime_candles else interval,
        )

        account_id, risk_profile_id, leverage = await _get_default_account_and_profile(session)

        for strat in strategies:
            fn = get_strategy_fn(strat.family, strat.name, strat.version)
            if not fn:
                continue
            try:
                cfg = await _get_runtime_config(session, strat, SYMBOL, interval)
                if cfg is None:
                    logger.debug(
                        "strategy_engine: %s/%s no se ejecuta: no existe strategy_runtime_config para symbol=%s timeframe=%s",
                        strat.family, strat.name, SYMBOL, interval,
                    )
                    continue
                if not cfg.active:
                    continue
                params = {}
                if strat.default_params_json:
                    try:
                        params = json.loads(strat.default_params_json)
                    except Exception:
                        pass
                params["timeframe"] = interval
                if strat.name == "breakout_volume_v2":
                    from app.services.strategies.breakout import breakout_volume_v2_eval

                    signal, reject_reason = breakout_volume_v2_eval(candles, params)
                    if reject_reason:
                        async with async_session_maker() as amb_session:
                            await _create_ambiguous_bar_event(
                                amb_session,
                                strategy_family=strat.family,
                                strategy_name=strat.name,
                                strategy_version=strat.version,
                                timeframe=interval,
                                symbol=SYMBOL,
                                reason=reject_reason,
                                regime_snapshot=regime_snapshot,
                            )
                        continue
                else:
                    signal = fn(candles, params)
                if signal is None:
                    continue
                if cfg is not None:
                    if signal.position_side == "LONG" and not cfg.allow_long:
                        continue
                    if signal.position_side == "SHORT" and not cfg.allow_short:
                        continue
                if signal.position_side == "LONG":
                    long_allowed, long_reason = evaluate_long_permission(
                        strategy_name=signal.strategy_name,
                        signal=signal,
                        regime=regime_snapshot,
                    )
                    if not long_allowed:
                        async with async_session_maker() as reject_session:
                            await _create_regime_blocked_signal_event(
                                reject_session,
                                signal,
                                long_reason,
                                regime_snapshot.regime,
                                regime_snapshot.timeframe_used,
                                regime_snapshot.reason,
                            )
                        continue
                elif signal.position_side == "SHORT":
                    short_allowed, short_reason = evaluate_short_permission(
                        strategy_name=signal.strategy_name,
                        signal=signal,
                        regime=regime_snapshot,
                    )
                    if not short_allowed:
                        async with async_session_maker() as reject_session:
                            await _create_regime_blocked_signal_event(
                                reject_session,
                                signal,
                                short_reason,
                                regime_snapshot.regime,
                                regime_snapshot.timeframe_used,
                                regime_snapshot.reason,
                            )
                        continue
                rp_id, lev = await _resolve_risk_profile_for_signal(session, signal, risk_profile_id, leverage)
                current_price = Decimal(str(candles[-1]["close"]))
                async with async_session_maker() as exec_session:
                    if cfg is not None:
                        blocked, reason = await has_exposure_conflict(
                            exec_session,
                            symbol=SYMBOL,
                            strategy_id=strat.id,
                            strategy_name=strat.name,
                            timeframe=interval,
                            position_side=signal.position_side,
                            max_open_positions=cfg.max_open_positions,
                            cooldown_minutes=cfg.cooldown_minutes,
                        )
                        if blocked:
                            await bot_log_event(
                                exec_session,
                                "WARN",
                                MODULE_STRATEGY,
                                EVENT_SIGNAL_REJECTED,
                                f"Signal rejected (exposure): {reason}",
                                context={
                                    "strategy": strat.name,
                                    "timeframe": interval,
                                    "position_side": signal.position_side,
                                    "reason": reason,
                                },
                            )
                            await exec_session.commit()
                            continue
                    trade = await _execute_signal(
                        exec_session, signal, current_price,
                        account_id, rp_id, lev,
                        strategy_id=strat.id, runtime_cfg=cfg,
                        regime_snapshot=regime_snapshot,
                    )
                    if trade:
                        opened.append(trade)
            except Exception as e:
                logger.exception("strategy_engine: %s/%s failed: %s", strat.family, strat.name, e)

        # Evaluar órdenes pendientes con la última vela (high/low): fill o expire
        bar_high = Decimal(str(candles[-1]["high"]))
        bar_low = Decimal(str(candles[-1]["low"]))
        async with async_session_maker() as eval_session:
            filled = await _evaluate_pending_orders(
                eval_session, SYMBOL, interval, bar_high, bar_low, regime_snapshot=regime_snapshot
            )
            opened.extend(filled)
            await eval_session.commit()
    return opened
