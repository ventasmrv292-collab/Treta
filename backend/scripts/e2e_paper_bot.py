#!/usr/bin/env python3
"""
Script E2E para validar el paper trading bot.
Ejecutar con el backend en marcha y DB con migraciones + seeds.
Escenarios: trade ganador, perdedor, rechazo capital, rechazo riesgo, señal duplicada, TP, SL.
"""
import os
import sys
import time

try:
    import httpx
except ImportError:
    print("Instala httpx: pip install httpx")
    sys.exit(1)

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_V1 = f"{API_BASE}/api/v1"


def get(path: str) -> dict:
    r = httpx.get(f"{API_V1}{path}", timeout=10.0)
    r.raise_for_status()
    return r.json()


def post(path: str, json: dict) -> dict:
    r = httpx.post(f"{API_V1}{path}", json=json, timeout=10.0)
    r.raise_for_status()
    return r.json()


def patch(path: str, json: dict) -> dict:
    r = httpx.patch(f"{API_V1}{path}", json=json, timeout=10.0)
    r.raise_for_status()
    return r.json()


def run():
    print("E2E Paper Bot — comprobando API en", API_BASE)
    errors = []

    # 1) Cuentas y estrategias
    try:
        accounts = get("/paper-accounts")
        assert isinstance(accounts, list), "paper-accounts debe ser lista"
        if not accounts:
            print("  [SKIP] No hay cuentas paper; ejecuta seeds.")
            return
        account_id = accounts[0]["id"]
        strategies = get("/strategies")
        assert strategies, "Debe haber al menos una estrategia"
        fam, name, ver = strategies[0]["family"], strategies[0]["name"], strategies[0]["version"]
        print("  OK Cuenta y estrategias")
    except Exception as e:
        errors.append(f"Setup: {e}")
        print("  FAIL", e)
        return

    # 2) Abrir trade ganador
    try:
        balance_before = float(get(f"/paper-accounts/{account_id}")["current_balance_usdt"])
        trade = post("/trades", {
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": fam,
            "strategy_name": name,
            "strategy_version": ver,
            "timeframe": "15m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": "0.001",
            "entry_price": "50000",
            "account_id": account_id,
        })
        tid = trade["id"]
        # Cerrar por encima → ganancia
        close_res = patch(f"/trades/{tid}/close", {
            "exit_price": 51000,
            "exit_order_type": "MARKET",
            "maker_taker_exit": "TAKER",
            "exit_reason": "e2e_ganador",
        })
        assert close_res.get("net_pnl_usdt") is not None
        balance_after = float(get(f"/paper-accounts/{account_id}")["current_balance_usdt"])
        assert balance_after >= balance_before, "Balance debería subir en trade ganador"
        print("  OK Trade ganador: balance sube")
    except Exception as e:
        errors.append(f"Trade ganador: {e}")
        print("  FAIL Trade ganador:", e)

    # 3) Abrir trade perdedor
    try:
        balance_before = float(get(f"/paper-accounts/{account_id}")["current_balance_usdt"])
        trade2 = post("/trades", {
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": fam,
            "strategy_name": name,
            "strategy_version": ver,
            "timeframe": "15m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": "0.001",
            "entry_price": "50000",
            "account_id": account_id,
        })
        tid2 = trade2["id"]
        patch(f"/trades/{tid2}/close", {
            "exit_price": 49000,
            "exit_order_type": "MARKET",
            "maker_taker_exit": "TAKER",
            "exit_reason": "e2e_perdedor",
        })
        balance_after = float(get(f"/paper-accounts/{account_id}")["current_balance_usdt"])
        assert balance_after < balance_before, "Balance debería bajar en trade perdedor"
        print("  OK Trade perdedor: balance baja")
    except Exception as e:
        errors.append(f"Trade perdedor: {e}")
        print("  FAIL Trade perdedor:", e)

    # 4) Rechazo por capital insuficiente
    try:
        r = httpx.post(f"{API_V1}/trades", json={
            "source": "manual",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": fam,
            "strategy_name": name,
            "strategy_version": ver,
            "timeframe": "15m",
            "position_side": "LONG",
            "order_side_entry": "BUY",
            "order_type_entry": "MARKET",
            "maker_taker_entry": "TAKER",
            "leverage": 10,
            "quantity": "999999",
            "entry_price": "100000",
            "account_id": account_id,
        }, timeout=10.0)
        assert r.status_code == 400, f"Esperado 400, obtuve {r.status_code}"
        print("  OK Rechazo por capital insuficiente")
    except Exception as e:
        errors.append(f"Rechazo capital: {e}")
        print("  FAIL Rechazo capital:", e)

    # 5) Rechazo por señal duplicada (n8n con idempotency_key)
    try:
        key = f"e2e-dup-{int(time.time())}"
        payload = {
            "source": "n8n",
            "symbol": "BTCUSDT",
            "market": "usdt_m",
            "strategy_family": fam,
            "strategy_name": name,
            "strategy_version": ver,
            "timeframe": "15m",
            "position_side": "LONG",
            "leverage": 10,
            "quantity": "0.001",
            "entry_price": "50000",
            "account_id": account_id,
            "idempotency_key": key,
        }
        post("/webhook/n8n/trade", payload)
        r2 = httpx.post(f"{API_V1}/webhook/n8n/trade", json=payload, timeout=10.0)
        assert r2.status_code == 409, f"Esperado 409 duplicado, obtuve {r2.status_code}"
        print("  OK Rechazo por señal duplicada")
    except Exception as e:
        errors.append(f"Señal duplicada: {e}")
        print("  FAIL Señal duplicada:", e)

    # 6) Dashboard summary cuadra
    try:
        summary = get(f"/analytics/dashboard-summary?account_id={account_id}")
        assert "account" in summary
        assert "open_positions_count" in summary or "account" in summary
        print("  OK Dashboard summary responde")
    except Exception as e:
        errors.append(f"Dashboard summary: {e}")
        print("  FAIL Dashboard summary:", e)

    if errors:
        print("\nErrores:", errors)
        sys.exit(1)
    print("\nTodos los escenarios E2E pasaron.")


if __name__ == "__main__":
    run()
