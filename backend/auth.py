from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from passlib.context import CryptContext
from jose import JWTError, jwt

from backend.config import settings

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"

for path in (USERS_FILE,):
    if not path.exists():
        path.write_text("{}", encoding="utf-8")

# Password hashing context
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


class TokenData(BaseModel):
    username: str


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def hash_password(password: str) -> str:
    """Hash password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(username: str, expires_delta: timedelta | None = None) -> tuple[str, int]:
    """Create JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.jwt_expiration_hours)
    
    expire = datetime.utcnow() + expires_delta
    to_encode = {"username": username, "exp": expire}
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt, int(expires_delta.total_seconds())


def verify_token(token: str) -> str:
    """Verify JWT token and return username"""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("username")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(authorization: str | None = Header(default=None, alias="Authorization")) -> str:
    """Extract and verify current user from Authorization header"""
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or malformed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split("Bearer ", 1)[1].strip()
    return verify_token(token)


def get_current_user_optional(authorization: str | None = Header(default=None, alias="Authorization")) -> str | None:
    """Extract current user if token is present, otherwise return None"""
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
    """Register a new user"""
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
    """Login user and return JWT token"""
    users = load_json(USERS_FILE)
    user = users.get(request.username)
    
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token, expires_in = create_access_token(request.username)
    return AuthResponse(access_token=token, expires_in=expires_in)


@router.post("/logout")
def logout_user(current_username: str = Depends(get_current_user)) -> dict:
    """Logout user (token invalidation handled on client side)"""
    return {"status": "ok", "message": "Logged out successfully"}


@router.get("/me")
def get_profile(current_username: str = Depends(get_current_user)) -> dict:
    """Get current user profile"""
    users = load_json(USERS_FILE)
    user = users.get(current_username)
    return {
        "username": current_username,
        "user_id": user.get("user_id") if user else None,
        "created_at": user.get("created_at") if user else None,
    }
