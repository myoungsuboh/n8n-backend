from fastmcp import FastMCP
from app.mcp.tools import get_search_data, query_knowledge_base

# 1. MCP 서버 인스턴스 생성
weaviate_mcp = FastMCP("weaviate Retriever Agent")

@weaviate_mcp.tool(name="search_company_knowledge")
async def search_company_knowledge(query_text: str) -> str:
    """
    회사에 공용 파일 정보 지식인 '사내 업무 지원 정보(사내 벡터 DB)를 검색합니다.
    사내 지식 베이스에서 규정, 영수증, CEO 메시지 등을 검색합니다.
    사용자의 질문에 대한 구체적인 정보나 팩트를 찾아야 할 때 사용하세요.
    
    Args:
        query_text: 사용자의 질문에서 추출한 핵심 검색 키워드 또는 문장. 
        (예: '야근 식대 한도', '2026년 신년사', '경조사 지원금')
    """
    
    return await get_search_data(query_text)


