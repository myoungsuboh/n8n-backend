from pydantic import BaseModel
from typing import Optional, Dict, Any

# 1. 기존 DB (Weaviate / Supabase) 전용 스키마
class SearchQuery(BaseModel):
    query_text: str  # 검색어
    match_threshold: Optional[float] = 0.6
    match_count: Optional[int] = 50
    return_count: Optional[int] = 10
    filter: Optional[Dict[str, Any]] = {}
    
# 2. 신규 Graph DB (Neo4j) 전용 스키마
class Neo4jSearchQuery(BaseModel):
    query_text: str
    match_threshold: float = 0.6
    match_count: int = 5
    category: Optional[str] = None
    file_name: Optional[str] = None