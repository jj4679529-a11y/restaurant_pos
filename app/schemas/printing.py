from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrintJobStatus


class PrintOrderRequest(BaseModel):
    printer_id: int = Field(gt=0)


class PrintJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    print_job_id: int
    order_id: int
    printer_id: int
    status: PrintJobStatus
    attempted_at: datetime | None
    printed_at: datetime | None
    error_message: str | None
