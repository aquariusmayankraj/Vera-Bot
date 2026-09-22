from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class ContextRequest(RequestModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str = Field(min_length=1, max_length=240)
    version: StrictInt = Field(ge=1)
    payload: dict[str, Any]
    delivered_at: AwareDatetime


class TickRequest(RequestModel):
    now: AwareDatetime
    available_triggers: list[str] = Field(default_factory=list, max_length=2000)


class ReplyRequest(RequestModel):
    conversation_id: str = Field(min_length=1, max_length=240)
    merchant_id: str | None = Field(default=None, max_length=240)
    customer_id: str | None = Field(default=None, max_length=240)
    from_role: Literal["merchant", "customer"]
    message: str = Field(min_length=1, max_length=12000)
    received_at: AwareDatetime
    turn_number: StrictInt = Field(ge=1, le=10000)
