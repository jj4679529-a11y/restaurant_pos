from pydantic import BaseModel, ConfigDict, Field


class SettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str


class SettingUpdate(BaseModel):
    value: str = Field(max_length=10_000)
