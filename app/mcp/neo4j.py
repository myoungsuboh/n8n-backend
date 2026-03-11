# app/mcp/neo4j.py
from fastmcp import FastMCP
from typing import Optional
from app.mcp.tools import get_search_data

neo4j_mcp = FastMCP("neo4j Retriever Agent")

@neo4j_mcp.tool(name="search_company_knowledge")
async def search_company_knowledge(
    query_text: str, 
    category: str = "",
    file_name: str = ""
) -> str:
    """
    회사에 공용 파일 정보 지식인 '사내 업무 지원 정보 neo4j(Graph DB)'를 검색합니다.
    사용자의 질문에 대한 구체적인 정보나 팩트를 찾아야 할 때 사용하세요.
    
    Args:
        query_text (str): 사용자의 질문에서 추출한 핵심 검색 키워드 또는 문장. (예: '야근 식대 한도', '2026년 신년사')
        category (str, optional): 질문 의도에 맞는 카테고리 영문명. 명확할 때만 사용하고 불확실하면 비워두세요. (예: 'Welfare_Doc', 'Receipt', 'Ai')
        file_name (str, optional): 이전 대화에서 언급된 특정 문서 내에서만 검색을 제한할 때 파일명을 입력하세요. (예: 'AI_바우처_신청가이드.pdf')
    """
    
    return await get_search_data(
        query_text=query_text, 
        category=category, 
        file_name=file_name
    )