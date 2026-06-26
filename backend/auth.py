from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
SESSION_EXPIRE_MINUTES = 24 * 60

for path in (USERS_FILE, SESSIONS_FILE):
    if not path.exists():
        path.write_text("{}", encoding="utf-8")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_session(username: str) -> str:
    sessions = load_json(SESSIONS_FILE)
    token = uuid.uuid4().hex
    expires_at = (datetime.utcnow() + timedelta(minutes=SESSION_EXPIRE_MINUTES)).isoformat()
    sessions[token] = {"username": username, "expires_at": expires_at}
    save_json(SESSIONS_FILE, sessions)
    return token


def verify_token(token: str) -> str:
    sessions = load_json(SESSIONS_FILE)
    session = sessions.get(token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_at = datetime.fromisoformat(session["expires_at"])
    if datetime.utcnow() > expires_at:
        sessions.pop(token, None)
        save_json(SESSIONS_FILE, sessions)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return session["username"]


def get_current_user(authorization: str | None = Header(default=None)) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split("Bearer ", 1)[1].strip()
    return verify_token(token)


def get_current_user_optional(authorization: str | None = Header(default=None)) -> str | None:
    if authorization is None or not authorization.startswith("Bearer "):
        return None
    try:
        token = authorization.split("Bearer ", 1)[1].strip()
        return verify_token(token)
    except HTTPException:
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
    }
    save_json(USERS_FILE, users)
    token = create_session(request.username)
    return AuthResponse(access_token=token)


@router.post("/login", response_model=AuthResponse)
def login_user(request: LoginRequest) -> AuthResponse:
    users = load_json(USERS_FILE)
    user = users.get(request.username)
    if not user or user["password_hash"] != hash_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(request.username)
    return AuthResponse(access_token=token)


@router.post("/logout")
def logout_user(current_username: str = Depends(get_current_user)) -> dict:
    sessions = load_json(SESSIONS_FILE)
    tokens_to_remove = [token for token, session in sessions.items() if session["username"] == current_username]
    for token in tokens_to_remove:
        sessions.pop(token, None)
    save_json(SESSIONS_FILE, sessions)
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me")
def get_profile(current_username: str = Depends(get_current_user)) -> dict:
    return {"username": current_username}
