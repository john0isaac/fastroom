from uuid import UUID

from pydantic import BaseModel


class TokenPayload(BaseModel):
    sub: str  # username
    exp: int
    iat: int
    v: int  # schema/version
    typ: str = "access"  # token type: access or refresh
    jti: UUID


class InvalidToken(Exception):
    pass


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshToken(BaseModel):
    refresh_token: str
    token_type: str = "bearer"


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str
