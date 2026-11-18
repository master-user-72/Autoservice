from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ParsedItem(BaseModel):
    description: str
    quantity: int = Field(default=1, ge=1, le=99)
    original_required: bool = False
    urgent: bool = False
    kit_key: Optional[str] = None
    kit_scope: Optional[str] = None
    article: Optional[str] = None


class ParsedRequest(BaseModel):
    vin: Optional[str] = None
    make: Optional[str] = None
    plate: Optional[str] = None
    items: list[ParsedItem] = Field(default_factory=list)
    clarifying_question: Optional[str] = None
    raw_text: str = ""
    nlu_source: str = "local"


class IngestBody(BaseModel):
    text: str


class SettingsPatch(BaseModel):
    training_mode: Optional[bool] = None
    send_hour: Optional[int] = Field(default=None, ge=0, le=23)
    send_minute: Optional[int] = Field(default=None, ge=0, le=59)


class VehicleBody(BaseModel):
    vin: str
    make: str = ""
    plate: str = ""
    model: str = ""
    year: str = ""
    engine: str = ""
    body: str = ""


class KitLoadBody(BaseModel):
    kit_key: str = "grm"
    vin: str = ""
    make: str = ""
    model: str = ""
    engine: str = ""
    text: str


class ReplaceBody(BaseModel):
    description: str


class QuantityBody(BaseModel):
    quantity: int = Field(ge=1, le=99)


class SendSelectedBody(BaseModel):
    item_ids: list[int] = Field(min_length=1)
