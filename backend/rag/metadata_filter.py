"""
Metadata filtering module for document retrieval
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime


class MetadataFilter:
    """Filter documents based on metadata"""
    
    def __init__(self):
        self.filters: List[Dict[str, Any]] = []
    
    def add_filter(self, field: str, value: Any, operator: str = "equals") -> MetadataFilter:
        """
        Add a filter condition.
        
        Args:
            field: Metadata field name
            value: Value to filter by
            operator: "equals", "contains", "gt", "lt", "gte", "lte", "in"
        
        Returns:
            self for method chaining
        """
        self.filters.append({
            "field": field,
            "value": value,
            "operator": operator
        })
        return self
    
    def add_date_range_filter(self, field: str, start_date: datetime, end_date: datetime) -> MetadataFilter:
        """Filter by date range"""
        self.filters.append({
            "field": field,
            "value": (start_date, end_date),
            "operator": "date_range"
        })
        return self
    
    def add_user_filter(self, user_id: str) -> MetadataFilter:
        """Filter by user ID"""
        self.add_filter("user_id", user_id, "equals")
        return self
    
    def add_document_type_filter(self, doc_type: str) -> MetadataFilter:
        """Filter by document type (pdf, txt, etc.)"""
        self.add_filter("document_type", doc_type, "equals")
        return self
    
    def clear(self) -> MetadataFilter:
        """Clear all filters"""
        self.filters = []
        return self
    
    def build_qdrant_filter(self) -> Dict[str, Any] | None:
        """
        Build Qdrant filter format.
        Returns None if no filters, otherwise returns filter dict.
        """
        if not self.filters:
            return None
        
        # For single filter
        if len(self.filters) == 1:
            return self._build_single_filter(self.filters[0])
        
        # For multiple filters (AND operation)
        return {
            "must": [self._build_single_filter(f) for f in self.filters]
        }
    
    def _build_single_filter(self, filter_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Build a single Qdrant filter condition"""
        field = filter_spec["field"]
        value = filter_spec["value"]
        operator = filter_spec["operator"]
        
        if operator == "equals":
            return {"key": field, "match": {"value": value}}
        elif operator == "contains":
            return {"key": field, "match": {"text": str(value)}}
        elif operator == "gt":
            return {"key": field, "range": {"gt": value}}
        elif operator == "lt":
            return {"key": field, "range": {"lt": value}}
        elif operator == "gte":
            return {"key": field, "range": {"gte": value}}
        elif operator == "lte":
            return {"key": field, "range": {"lte": value}}
        elif operator == "in":
            return {"key": field, "match": {"any": value}}
        elif operator == "date_range":
            start_date, end_date = value
            return {
                "key": field,
                "range": {
                    "gte": start_date.timestamp(),
                    "lte": end_date.timestamp()
                }
            }
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def matches_document(self, document_metadata: Dict[str, Any]) -> bool:
        """Check if a document matches all filter conditions"""
        for filter_spec in self.filters:
            if not self._matches_filter(document_metadata, filter_spec):
                return False
        return True
    
    def _matches_filter(self, metadata: Dict[str, Any], filter_spec: Dict[str, Any]) -> bool:
        """Check if metadata matches a single filter"""
        field = filter_spec["field"]
        value = filter_spec["value"]
        operator = filter_spec["operator"]
        
        meta_value = metadata.get(field)
        
        if operator == "equals":
            return meta_value == value
        elif operator == "contains":
            return str(value).lower() in str(meta_value).lower()
        elif operator == "gt":
            return meta_value > value
        elif operator == "lt":
            return meta_value < value
        elif operator == "gte":
            return meta_value >= value
        elif operator == "lte":
            return meta_value <= value
        elif operator == "in":
            return meta_value in value
        elif operator == "date_range":
            start_date, end_date = value
            if isinstance(meta_value, str):
                meta_value = datetime.fromisoformat(meta_value)
            return start_date <= meta_value <= end_date
        else:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize filters to dictionary"""
        return {"filters": self.filters}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MetadataFilter:
        """Deserialize filters from dictionary"""
        mf = cls()
        mf.filters = data.get("filters", [])
        return mf
