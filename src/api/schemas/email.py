from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class EmailCreateRequest(BaseModel):
    user_id: UUID
    email: EmailStr


class EmailUpdateRequest(BaseModel):
    user_id: UUID
    email: EmailStr


class EmailConfirmRequest(BaseModel):
    code: str = Field(min_length=1)


class EmailSendConfirmationRequest(BaseModel):
    user_id: UUID


class EmailResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    approved: bool


class ConfirmationResponse(BaseModel):
    status: str
    user_email_id: str
