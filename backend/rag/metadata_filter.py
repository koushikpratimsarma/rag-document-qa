from __future__ import annotations
import json
from backend.rag.llm import get_llm
import logging
import re
from typing import Any, Dict, Optional

from qdrant_client.http import models


logger = logging.getLogger(__name__)

COMPANY_ALIASES = {
    "apple": "Apple Inc.",
    "apple inc": "Apple Inc.",
    "apple inc.": "Apple Inc.",
    "aapl": "Apple Inc.",
    "nvidia": "NVIDIA Corporation",
    "nvda": "NVIDIA Corporation",
    "nvidia corporation": "NVIDIA Corporation",
    "nvidia corp": "NVIDIA Corporation",
    "microsoft": "Microsoft Corporation",
    "msft": "Microsoft Corporation",
    "microsoft corporation": "Microsoft Corporation",
    "meta": "Meta Platforms, Inc.",
    "facebook": "Meta Platforms, Inc.",
    "tesla": "Tesla, Inc.",
    "google": "Alphabet Inc.",
    "alphabet": "Alphabet Inc.",
    "goog": "Alphabet Inc.",
}

TICKER_TO_COMPANY = {
    "aapl": "Apple Inc.",
    "nvda": "NVIDIA Corporation",
    "msft": "Microsoft Corporation",
    "meta": "Meta Platforms, Inc.",
    "goog": "Alphabet Inc.",
    "tsla": "Tesla, Inc.",
}


def extract_company_from_query(query: str) -> Optional[str]:
    prompt = f"""
Identify the company mentioned in this question.

Return ONLY valid JSON.

{{
    "company": null
}}

Question:
{query}
"""

    try:
        llm = get_llm()

        response = llm.invoke(prompt)

        text = response.content if hasattr(response, "content") else str(response)

        data = json.loads(text)

        return data.get("company")

    except Exception:
        return None


def extract_company_from_query_rule_based(query: str) -> Optional[str]:
    query_lower = query.lower()

    for alias, canonical in COMPANY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", query_lower):
            return canonical

    return None


def extract_ticker_from_query(query: str) -> Optional[str]:
    query_lower = query.lower()

    for ticker in TICKER_TO_COMPANY.keys():
        if re.search(rf"\b{re.escape(ticker)}\b", query_lower):
            return ticker.upper()

    return None


def normalize_company_name(name: str | None) -> str | None:
    if not name:
        return None

    normalized = str(name).strip()
    lower = normalized.lower()

    aliases = {
        "apple": "Apple Inc.",
        "apple inc": "Apple Inc.",
        "nvidia": "NVIDIA Corporation",
        "nvda": "NVIDIA Corporation",
        "nvidia corporation": "NVIDIA Corporation",
        "meta": "Meta Platforms, Inc.",
        "facebook": "Meta Platforms, Inc.",
        "tesla": "Tesla, Inc.",
        "google": "Alphabet Inc.",
        "alphabet": "Alphabet Inc.",
    }

    return aliases.get(lower, normalized)


def extract_query_metadata(query: str) -> Dict[str, Any]:
    query_lower = query.lower()

    company = normalize_company_name(extract_company_from_query(query))
    ticker = extract_ticker_from_query(query)

    if not company and ticker:
        company = TICKER_TO_COMPANY.get(ticker.lower())

    metadata: Dict[str, Any] = {
        "company": company,
        "ticker": ticker,
        "year": None,
        "quarter": None,
        "document_type_label": None,
    }

    year_match = re.search(r"\b(20\d{2})\b", query_lower)
    if year_match:
        try:
            metadata["year"] = int(year_match.group(1))
        except (ValueError, TypeError):
            metadata["year"] = None

    if re.search(r"\bq1\b|first quarter", query_lower):
        metadata["quarter"] = "Q1"
    elif re.search(r"\bq2\b|second quarter", query_lower):
        metadata["quarter"] = "Q2"
    elif re.search(r"\bq3\b|third quarter", query_lower):
        metadata["quarter"] = "Q3"
    elif re.search(r"\bq4\b|fourth quarter", query_lower):
        metadata["quarter"] = "Q4"

    if "10-q" in query_lower or "10q" in query_lower:
        metadata["document_type_label"] = "10-Q"
    elif "10-k" in query_lower or "10k" in query_lower:
        metadata["document_type_label"] = "10-K"
    elif "annual report" in query_lower:
        metadata["document_type_label"] = "Annual Report"

    logger.info(
        "QUERY_METADATA_EXTRACTED | query=%r | year=%s | quarter=%s "
        "| document_type=%s",
        query,
        metadata.get("year"),
        metadata.get("quarter"),
        metadata.get("document_type_label"),
    )

    return metadata


def build_user_session_filter(
    current_user: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[models.Filter]:
    must = []

    if current_user:
        must.append(
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=current_user),
            )
        )

    if session_id:
        must.append(
            models.FieldCondition(
                key="session_id",
                match=models.MatchValue(value=session_id),
            )
        )

    return models.Filter(must=must) if must else None


def build_filter_from_query(
    query: str,
    current_user: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Optional[models.Filter]:
    must = []

    user_session_filter = build_user_session_filter(
        current_user=current_user,
        session_id=session_id,
    )

    if user_session_filter is not None and user_session_filter.must is not None:
        must.extend(user_session_filter.must)

    query_metadata = extract_query_metadata(query)

    logger.info(
        "QUERY_METADATA_BEFORE_FILTER | metadata=%s",
        query_metadata,
    )

    for key, value in query_metadata.items():
        if value is None:
            continue

        if key == "company":
            value = normalize_company_name(value)

        must.append(
            models.FieldCondition(
                key=key,
                match=models.MatchValue(value=value),
            )
        )

        logger.info(
            "FILTER_CONDITION_ADDED | key=%s | value=%s | type=%s",
            key,
            value,
            type(value).__name__,
        )

    query_filter = models.Filter(must=must) if must else None

    logger.info(
        "QDRANT_FILTER_BUILT | query=%r | user=%s | session_id=%s "
        "| condition_count=%d | filter=%s",
        query,
        current_user or "anonymous",
        session_id,
        len(must),
        query_filter,
    )

    return query_filter

    return query_filter