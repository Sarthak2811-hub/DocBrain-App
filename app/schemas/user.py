from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# 1. Registration input validation
class UserCreate(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, description="User password (min 6 characters)")


# 2. Login response data validation
class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# 3. Successful login token format
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None 
    type: Optional[str] = None 


class TokenRefreshRequest(BaseModel):
    refresh_token: str
