# app/mcp/tools.py
from typing import Optional
from app.schemas import SearchQuery
from app.schemas import Neo4jSearchQuery
from app.service.retriever import search_logic, search_target_table, fetch_data_by_ids, embedding_query, search_neo4j_graph

async def query_knowledge_base(query: str, db_type: str = "supabase") -> str:
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

async def get_search_data(query_text: str) -> str:
    """
    실제 검색 로직을 수행하고 결과를 문자열로 반환하는 함수입니다.
    """
    
    # 1. 검색 파라미터 세팅
    params = SearchQuery(
        query_text=query_text,
        match_threshold=0.6,
        match_count=3 # 최종적으로 Agent에게 넘겨줄 문서 개수
    )
    
    # 2. 질문과 유사한 데이터를 테이블별로 1차 검색
    raw_candidates = await search_target_table(params)
    
    # 결과가 아예 없거나, 1등 후보의 유사도가 match_threshold 이하인 경우 필터링
    if not raw_candidates or raw_candidates[0].get('similarity', 0) < params.match_threshold:
        print(f"⚠️ 유사도 미달 또는 결과 없음 (최고 점수: {raw_candidates[0]['similarity'] if raw_candidates else 0:.4f})")
        return "관련된 사내 데이터를 찾을 수 없습니다."
    
    # 3. 각 문서의 ID를 추출하여 fetch_data_by_ids 함수에 전달
    ids = [doc['id'] for doc in raw_candidates]
    detailed_results = await fetch_data_by_ids(raw_candidates[0]['collection'], ids)

    # 4. LLM(Agent)이 읽고 요약하기 가장 좋은 형태로 문자열(String) 포장
    formatted_output = "다음은 사내 데이터베이스 검색 결과 및 연관 데이터입니다. 이를 바탕으로 답변하세요.\n\n"

    for idx, doc in enumerate(detailed_results, 1):
        # 새로 정의된 키값들에 맞춰서 데이터 추출
        table_name = doc.get('table', '알 수 없음')
        file_name = doc.get('fileName', '알 수 없음')
        content = doc.get('content', '')
        cross_ref = doc.get('cross_reference', '')
        
        # 1. 문서 헤더 (어디서 가져왔는지 명확히 명시)
        formatted_output += f"### 후보 {idx} (출처: {table_name} / 파일명: {file_name})\n"
        
        # 2. 메인 데이터
        formatted_output += f"[본문 내용]\n{content}\n"
        
        # 3. 관계도 데이터
        # cross_ref 값이 존재할 때만 출력하도록 처리
        if cross_ref:
            formatted_output += f"\n[연관 참조 데이터]\n{cross_ref}\n"
            
        # 구분선 추가로 AI가 문맥을 헷갈리지 않게 처리
        formatted_output += "-" * 40 + "\n\n"

    return formatted_output


async def get_search_data(query_text: str, category: Optional[str] = None, file_name: Optional[str] = None) -> str:
    """
    Agent의 요청을 받아 임베딩 -> Neo4j 하이브리드 검색 -> 문자열 포맷팅을 수행합니다.
    """
    print(f"🔍 [SEARCH START] Query: '{query_text}', Category: '{category}', File: '{file_name}'")
    
    # 1. 전달받은 인자들로 신규 Neo4jSearchQuery 객체(DTO) 생성
    params = Neo4jSearchQuery(
        query_text=query_text,
        category=category,
        file_name=file_name,
        match_threshold=0.8,
        match_count=5 
    )
    
    # 2. 컴포넌트 재사용: 질문 임베딩 (객체 전달)
    try:
        query_vector = embedding_query(params)
    except Exception as e:
        print(f"[EMBEDDING ERROR] {e}")
        return "오류: 검색어 임베딩 처리 중 문제가 발생했습니다."

    # 3. Neo4j 검색 로직 호출 (객체 + 벡터 전달)
    raw_candidates = await search_neo4j_graph(params=params, vector=query_vector)
    
    # 4. 결과 검증 및 필터링
    # 결과가 아예 없거나, 1등 후보의 유사도가 match_threshold 이하인 경우 컷팅
    if not raw_candidates or raw_candidates[0].get('score', 0) < params.match_threshold:
        print(f"유사도 미달 또는 결과 없음 (최고 점수: {raw_candidates[0].get('score', 0) if raw_candidates else 0:.4f})")
        return "관련된 사내 데이터를 찾을 수 없습니다."

    # 5. Agent가 읽기 좋게 문자열(String) 포장 (수정된 부분)
    formatted_output = "다음은 사내 데이터베이스 검색 결과입니다. 이를 바탕으로 답변하세요.\n\n"
    
    for idx, doc in enumerate(raw_candidates, 1):
        # 쿼리에서 category 반환을 생략했다면 '분류없음'으로 기본 처리
        c_name = doc.get('category', '분류없음') 
        f_name = doc.get('fileName', '알 수 없음')
        score = doc.get('score', 0.0)
        
        # 새롭게 바뀐 리스트 형태의 데이터 추출
        primary_content_list = doc.get('primaryContent', [])
        supplemental_context = doc.get('supplementalContext', [])
        
        # 핵심 내용 배열을 하나의 텍스트로 결합 (줄바꿈 또는 띄어쓰기)
        if isinstance(primary_content_list, list):
            primary_text = " ".join(primary_content_list)
        else:
            primary_text = str(primary_content_list)

        formatted_output += f"### 후보 {idx} (유사도: {score:.4f})\n"
        formatted_output += f"- [출처]: 파일명 '{f_name}'\n"
        formatted_output += f"- [핵심 내용]:\n  {primary_text}\n"
        
        # 연관 문서 배열 파싱 (리스트 안의 리스트 구조 해제)
        if supplemental_context:
            formatted_output += "- [연관 내용]:\n"
            for doc_chunks in supplemental_context:
                if isinstance(doc_chunks, list):
                    for chunk in doc_chunks:
                        source = chunk.get('source', '알 수 없음')
                        text = chunk.get('text', '')
                        formatted_output += f"  * [출처: {source}] {text}\n"
                # 혹시 1차원 딕셔너리로 들어올 경우 대비
                elif isinstance(doc_chunks, dict):
                    source = doc_chunks.get('source', '알 수 없음')
                    text = doc_chunks.get('text', '')
                    formatted_output += f"  * [출처: {source}] {text}\n"
                    
        formatted_output += "\n"
        
    print(f"✅ [SEARCH DONE] Found: {len(raw_candidates)} results.")
    return formatted_output