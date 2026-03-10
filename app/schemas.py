# app/schemas.py
from pydantic import BaseModel
from typing import Optional, Dict, Any

class SearchQuery(BaseModel):
    query_text: str  # 검색어
    match_threshold: Optional[float] = 0.6
    match_count: Optional[int] = 50
    return_count: Optional[int] = 10
    filter: Optional[Dict[str, Any]] = {}