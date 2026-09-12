from pydantic import BaseModel, ConfigDict, Field


class DeliveryWorkerCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(min_length=1, max_length=255)
    phone: str = Field(min_length=1, max_length=32)
    is_active: bool = True


class DeliveryWorkerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, min_length=1, max_length=32)
    is_active: bool | None = None


class DeliveryWorkerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    is_active: bool
