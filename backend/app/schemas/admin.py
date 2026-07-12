import uuid
from datetime import datetime

from pydantic import BaseModel


class AdminUserSummary(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_admin: bool
    created_at: datetime
    document_count: int
    done_count: int
    error_count: int
