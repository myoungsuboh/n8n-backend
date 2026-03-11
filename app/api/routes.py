# app/api/routes.py
import os
import httpx
from dotenv import load_dotenv
from app.schemas import SearchQuery, Neo4jSearchQuery
from fastapi import APIRouter, HTTPException, Request
from app.service.retriever import search_logic, search_target_table, fetch_data_by_ids, search_neo4j_graph, embedding_query

load_dotenv()

NCP_CLOVA_URL = os.getenv("NCP_CLOVA_URL")

NCP_CLOVA_TOKEN = os.getenv("NCP_CLOVA_TOKEN")

NCP_CLOVA_REQUEST_ID = os.getenv("NCP_CLOVA_REQUEST_ID")

router = APIRouter()

@router.post("/search-docs")
async def search_documents(payload: SearchQuery):
    try:
        # 하나하나 풀어서 넣을 필요 없이 payload 통째로 전달!
        results = await search_logic(payload)
        
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/search_table")
async def search_table(payload: SearchQuery):
    try:
        # 1. 검색 파라미터 세팅
        params = SearchQuery(
            query_text=payload.query_text,
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

        return {"results": formatted_output}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search-neo4j")
async def search_neo4j(payload: Neo4jSearchQuery):
    """
    Neo4j Graph DB를 검색하는 API 엔드포인트입니다.
    """
    try:
        # 1. 질문 임베딩 (Gemini)
        vector = embedding_query(payload)
        
        # 2. Neo4j 검색 수행
        results = await search_neo4j_graph(payload, vector)
        
        # 3. 결과 반환
        return {
            "status": "success",
            "count": len(results),
            "data": results
        }
        
    except Exception as e:
        print(f"❌ [NEO4J API ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# ==========================================
# n8n 인증 모델 리스트 반환 API
# ==========================================
@router.get("/v1/models")
async def dummy_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "HCX-005",
                "object": "model",
                "created": 1677610602,
                "owned_by": "naver-cloud"
            }
        ]
    }
    
# ==========================================
# NCP - n8n 통역사 (Proxy) API
# ==========================================
@router.post("/v1/chat/completions")
async def proxy_to_clova(request: Request):
    try:
        # 1. n8n (OpenAI Chat Model 노드)에서 넘어온 JSON 데이터 받기
        openai_data = await request.json()
        
        # 2. NCP HCX-005 규격으로 페이로드 변환 (Mapping)
        ncp_payload = {
            "messages": openai_data.get("messages", []),
            "topP": openai_data.get("top_p", 0.8),
            "temperature": openai_data.get("temperature", 0.5)
        }
        
        # n8n이 MCP Tool(함수) 정보를 보냈다면 NCP 포맷에 맞춰 추가
        if "tools" in openai_data:
            ncp_payload["tools"] = openai_data["tools"]

        NCP_HEADERS = {
            "Authorization": f"Bearer {NCP_CLOVA_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-NCP-CLOVASTUDIO-REQUEST-ID": NCP_CLOVA_REQUEST_ID
        }

        # 3. NCP 서버로 실제 요청 쏘기 (응답 대기시간 30초 넉넉히 설정)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(NCP_CLOVA_URL, headers=NCP_HEADERS, json=ncp_payload)
            
            # 클로바 서버에서 에러를 뱉었을 경우 디버깅을 위해 예외 처리
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"NCP API Error: {response.text}")
                
            ncp_result = response.json()

        # 4. NCP의 응답을 다시 OpenAI 규격으로 포장해서 n8n에 리턴
        clova_message = ncp_result.get("result", {}).get("message", {})
        
        # 💡 핵심: 클로바가 일반 대답을 한 건지, 아니면 '툴을 써라'고 지시한 건지 상태값 매핑
        finish_reason = "stop"
        if "tool_calls" in clova_message:
            finish_reason = "tool_calls"
        
        # OpenAI 표준 포맷으로 최종 조립
        openai_response = {
            "id": "chatcmpl-" + ncp_result.get("result", {}).get("id", "clova-proxy"),
            "object": "chat.completion",
            "model": openai_data.get("model", "HCX-005"),
            "choices": [
                {
                    "index": 0,
                    "message": clova_message,
                    "finish_reason": finish_reason
                }
            ]
        }
        
        return openai_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))