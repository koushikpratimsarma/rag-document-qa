from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("{}", encoding="utf-8")


class HistoryItem(BaseModel):
    timestamp: str
    query: str
    answer: str


class HistoryResponse(BaseModel):
    history: List[HistoryItem]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def add_history(username: str, query: str, answer: str) -> None:
    history_data = load_json(HISTORY_FILE)
    user_history = history_data.get(username, [])
    user_history.append(
        {
            "timestamp": datetime.utcnow().isoformat(),
            "query": query,
            "answer": answer,
        }
    )
    history_data[username] = user_history
    save_json(HISTORY_FILE, history_data)


def get_history_for_user(username: str) -> List[Dict[str, str]]:
    history_data = load_json(HISTORY_FILE)
    history = history_data.get(username, [])
    history = sorted(history, key=lambda item: item.get("timestamp", ""), reverse=True)
    return history


def clear_history_for_user(username: str) -> None:
    history_data = load_json(HISTORY_FILE)
    history_data[username] = []
    save_json(HISTORY_FILE, history_data)


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=HistoryResponse)
def read_history(current_username: str = Depends(get_current_user)) -> HistoryResponse:
    history_list = get_history_for_user(current_username)
    return HistoryResponse(history=history_list)


@router.post("/clear")
def clear_history(current_username: str = Depends(get_current_user)) -> dict:
    clear_history_for_user(current_username)
    return {"status": "ok", "message": "History cleared"}
