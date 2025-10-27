# File: app/schemas/auth.py

from pydantic import BaseModel, EmailStr, Field

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)
    mobile: str | None = None

class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=512)

class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class EmailOnly(BaseModel):
    email: EmailStr

class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8)