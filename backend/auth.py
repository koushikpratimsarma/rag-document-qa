from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from passlib.context import CryptContext

from backend.config import settings

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"

for path in (USERS_FILE,):
    if not path.exists():
        path.write_text("{}", encoding="utf-8")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(username: str, expires_delta: timedelta | None = None) -> tuple[str, int]:
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_expiration_hours)
    return username, int(expires_delta.total_seconds())


def get_current_user(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_username: str | None = Header(default=None, alias="X-Username"),
) -> str:
    if x_username:
        return x_username
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        if token:
            return token
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def get_current_user_optional(
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_username: str | None = Header(default=None, alias="X-Username"),
) -> str | None:
    if x_username:
        return x_username
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        if token:
            return token
    return None


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register_user(request: RegisterRequest) -> AuthResponse:
    users = load_json(USERS_FILE)
    if request.username in users:
        raise HTTPException(status_code=400, detail="Username already exists")

    users[request.username] = {
        "password_hash": hash_password(request.password),
        "created_at": datetime.utcnow().isoformat(),
        "user_id": str(uuid.uuid4()),
    }
    save_json(USERS_FILE, users)

    token, expires_in = create_access_token(request.username)
    return AuthResponse(access_token=token, expires_in=expires_in)


@router.post("/login", response_model=AuthResponse)
def login_user(request: LoginRequest) -> AuthResponse:
    users = load_json(USERS_FILE)
    user = users.get(request.username)

    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token, expires_in = create_access_token(request.username)
    return AuthResponse(access_token=token, expires_in=expires_in)


@router.post("/logout")
def logout_user(current_username: str = Depends(get_current_user)) -> dict:
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me")
def get_profile(current_username: str = Depends(get_current_user)) -> dict:
    users = load_json(USERS_FILE)
    user = users.get(current_username)
    return {
        "username": current_username,
        "user_id": user.get("user_id") if user else None,
        "created_at": user.get("created_at") if user else None,
    }
