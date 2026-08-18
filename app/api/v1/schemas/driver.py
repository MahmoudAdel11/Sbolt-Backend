from pydantic import BaseModel


class DriverStatusUpdateRequest(BaseModel):
    is_online: bool
