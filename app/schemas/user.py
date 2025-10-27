#app\schemas\user.py
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    mobile: str | None = None

class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool
    is_verified: bool
    role: str

    class Config:
        from_attributes = True