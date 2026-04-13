import re
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime


def _validate_password_strength(password: str) -> str:
    """Validates password has uppercase, lowercase, digit, and special char."""
    if not re.search(r'[A-Z]', password):
        raise ValueError('Senha deve conter pelo menos uma letra maiúscula')
    if not re.search(r'[a-z]', password):
        raise ValueError('Senha deve conter pelo menos uma letra minúscula')
    if not re.search(r'\d', password):
        raise ValueError('Senha deve conter pelo menos um número')
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/~`]', password):
        raise ValueError('Senha deve conter pelo menos um caractere especial')
    return password


class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=100)


class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=8, max_length=128,
        description="Senha: mínimo 8 caracteres, com maiúscula, minúscula, número e especial"
    )

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: int
    status: str
    is_superuser: bool
    roles: list[str] = []
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """Response for login endpoint - includes user data along with tokens"""
    user: UserResponse


class TokenPayload(BaseModel):
    user_id: int
    email: str
    roles: list[str] = []
    exp: Optional[datetime] = None


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None
    permissions: dict = {}


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[dict] = None


class RoleResponse(RoleBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        return _validate_password_strength(v)
