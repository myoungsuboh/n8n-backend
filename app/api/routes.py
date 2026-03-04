# app/api/routes.py
from fastapi import APIRouter, HTTPException
from app.schemas import SearchQuery
from app.service.retriever import search_logic, search_target_table, fetch_data_by_ids

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