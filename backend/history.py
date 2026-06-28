from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.auth import get_current_user

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("{}", encoding="utf-8")


class HistoryItem(BaseModel):
    id: str
    timestamp: str
    query: str
    answer: str
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    documents_used: Optional[List[str]] = None
    session_id: Optional[str] = None


class HistoryResponse(BaseModel):
    history: List[HistoryItem]


class SessionResponse(BaseModel):
    sessions: List[Dict[str, Any]]


class ConversationContext(BaseModel):
    """Context for multi-turn conversations"""
    session_id: str
    conversation_history: List[Dict[str, str]]


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def add_history(
    username: str,
    query: str,
    answer: str,
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    documents_used: Optional[List[str]] = None,
    session_id: Optional[str] = None
) -> str:
    """
    Add query-answer pair to user history
    
    Returns:
        History item ID
    """
    history_data = load_json(HISTORY_FILE)
    user_history = history_data.get(username, [])
    
    item_id = str(uuid.uuid4())
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    history_item = {
        "id": item_id,
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "answer": answer,
        "retrieved_chunks": retrieved_chunks or [],
        "documents_used": documents_used or [],
        "session_id": session_id,
    }
    
    user_history.append(history_item)
    history_data[username] = user_history
    save_json(HISTORY_FILE, history_data)
    
    return item_id


def get_history_for_user(
    username: str,
    limit: int = 100,
    session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get user's query history
    
    Args:
        username: Username
        limit: Maximum number of items to return
        session_id: Optional session filter
    """
    history_data = load_json(HISTORY_FILE)
    history = history_data.get(username, [])
    
    # Filter by session if provided
    if session_id:
        history = [h for h in history if h.get("session_id") == session_id]
    
    # Sort by timestamp descending
    history = sorted(history, key=lambda item: item.get("timestamp", ""), reverse=True)
    
    return history[:limit]


def get_conversation_sessions(username: str) -> List[Dict[str, Any]]:
    """Get all conversation sessions for a user"""
    history_data = load_json(HISTORY_FILE)
    history = history_data.get(username, [])
    
    # Group by session_id
    sessions = {}
    for item in history:
        session_id = item.get("session_id", "default")
        if session_id not in sessions:
            sessions[session_id] = {
                "session_id": session_id,
                "created_at": item.get("timestamp"),
                "messages": 0,
                "last_message": item.get("timestamp"),
            }
        sessions[session_id]["messages"] += 1
        sessions[session_id]["last_message"] = item.get("timestamp")
    
    # Sort by last message time
    sessions_list = sorted(
        sessions.values(),
        key=lambda x: x["last_message"],
        reverse=True
    )
    
    return sessions_list


def get_conversation_history(username: str, session_id: str) -> List[Dict[str, str]]:
    """Get conversation history for a specific session"""
    history_data = load_json(HISTORY_FILE)
    history = history_data.get(username, [])
    
    # Filter by session and sort by timestamp
    session_history = [
        h for h in history
        if h.get("session_id") == session_id
    ]
    session_history = sorted(
        session_history,
        key=lambda item: item.get("timestamp", "")
    )
    
    # Convert to conversation format (alternating user/assistant)
    conversation = []
    for item in session_history:
        conversation.append({
            "role": "user",
            "content": item["query"],
            "timestamp": item["timestamp"]
        })
        conversation.append({
            "role": "assistant",
            "content": item["answer"],
            "timestamp": item["timestamp"]
        })
    
    return conversation


def clear_history_for_user(username: str) -> None:
    """Clear all history for a user"""
    history_data = load_json(HISTORY_FILE)
    history_data[username] = []
    save_json(HISTORY_FILE, history_data)


def clear_session_history(username: str, session_id: str) -> None:
    """Clear history for specific session"""
    history_data = load_json(HISTORY_FILE)
    user_history = history_data.get(username, [])
    
    # Remove items from this session
    history_data[username] = [
        h for h in user_history
        if h.get("session_id") != session_id
    ]
    save_json(HISTORY_FILE, history_data)


def search_history(username: str, query_text: str) -> List[Dict[str, Any]]:
    """Search user's history by query text"""
    history_data = load_json(HISTORY_FILE)
    history = history_data.get(username, [])
    
    query_lower = query_text.lower()
    results = [
        h for h in history
        if query_lower in h.get("query", "").lower() or
           query_lower in h.get("answer", "").lower()
    ]
    
    return sorted(results, key=lambda item: item.get("timestamp", ""), reverse=True)


router = APIRouter(prefix="/history", tags=["history"])


@router.get("/", response_model=HistoryResponse)
def read_history(
    current_username: str = Depends(get_current_user),
    session_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000)
) -> HistoryResponse:
    """Get user's query history"""
    history_list = get_history_for_user(current_username, limit=limit, session_id=session_id)
    return HistoryResponse(history=history_list)


@router.get("/sessions", response_model=SessionResponse)
def read_sessions(current_username: str = Depends(get_current_user)) -> SessionResponse:
    """Get all conversation sessions for user"""
    sessions = get_conversation_sessions(current_username)
    return SessionResponse(sessions=sessions)


@router.get("/session/{session_id}")
def read_session(
    session_id: str,
    current_username: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """Get full conversation for a session"""
    conversation = get_conversation_history(current_username, session_id)
    return {"session_id": session_id, "conversation": conversation}


@router.get("/search")
def search_history_endpoint(
    q: str = Query(..., min_length=1),
    current_username: str = Depends(get_current_user)
) -> HistoryResponse:
    """Search history by query text"""
    results = search_history(current_username, q)
    return HistoryResponse(history=results)


@router.post("/clear")
def clear_history(current_username: str = Depends(get_current_user)) -> dict:
    """Clear all history for user"""
    clear_history_for_user(current_username)
    return {"status": "ok", "message": "History cleared"}


@router.post("/session/{session_id}/clear")
def clear_session(
    session_id: str,
    current_username: str = Depends(get_current_user)
) -> dict:
    """Clear history for specific session"""
    clear_session_history(current_username, session_id)
    return {"status": "ok", "message": f"Session {session_id} history cleared"}
