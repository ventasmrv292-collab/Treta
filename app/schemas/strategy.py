"""Strategy schemas."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StrategyBase(BaseModel):
    family: str
    name: str
    version: str
    description: str | None = None
    default_params_json: str | None = None
    active: bool = True


class StrategyCreate(StrategyBase):
    pass


class StrategyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family: str
    name: str
    version: str
    description: str | None
    default_params_json: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
