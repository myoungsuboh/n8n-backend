from fastmcp import FastMCP
from app.mcp.tools import search_knowledge_base_tool

# 1. MCP 서버 인스턴스 생성
supabase_mcp = FastMCP("supabase Retriever Agent")

@supabase_mcp.tool(name="query_knowledge_base")
async def query_knowledge_base(query: str) -> str:
    """
    [필수] 복리후생규정 지식 베이스(문서)를 검색합니다.
    사용자의 질문에 대한 구체적인 정보나 팩트를 찾아야 할 때 사용하세요.
    
    Args:
        query: 검색할 키워드나 질문 문장 (예: "학자금 지급대상이 누구야?")
    """
    return await search_knowledge_base_tool(query, db_type="supabase")