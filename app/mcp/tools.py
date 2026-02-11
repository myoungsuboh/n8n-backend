# app/mcp/tools.py
from app.service.retriever import search_logic
from app.schemas import SearchQuery

async def search_knowledge_base_tool(query: str, db_type: str = "supabase") -> str:
    """
    실제 검색 로직을 수행하고 결과를 문자열로 반환하는 함수입니다.
    LLM이 이 함수를 호출하게 됩니다.
    """
    params = SearchQuery(
        query_text=query,
        match_threshold=0.6,
        match_count=10 
    )
    
    results = await search_logic(params, db_type)
    
    print(f"✅ [SEARCH DONE] Found: {len(results)} results from {db_type}")

    return str(results)