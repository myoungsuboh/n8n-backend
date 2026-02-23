import re
import os
import json
import weaviate.classes as wvc
import google.generativeai as genai
from dotenv import load_dotenv
from typing import List, Dict, Any, Union
from app.schemas import SearchQuery
from app.core.config import GOOGLE_API_KEY
from app.core.database import supabase, weaviate_client

load_dotenv()

raw_env = os.getenv("RELATIONS_MAP", "{}")

RELATIONS_MAP = json.loads(raw_env)

async def fetch_vector_candidates(db_type: str, vector: List[float], params: SearchQuery, limit: int) -> List[Dict[str, Any]]:
    """
    지정된 DB에서 벡터 유사도 기반으로 후보군을 가져옵니다.
    """
    if db_type.lower() == "supabase":
        response = supabase.rpc('match_documents', {
            'query_embedding': vector,
            'match_threshold': 0.2,
            'match_count': limit,
            'filter': params.filter
        }).execute()
        return response.data
    
    # 2. Weaviate 로직 추가
    elif db_type == "weaviate":
        collection_name = "Welfare_Doc" 
        collection = weaviate_client.collections.get(collection_name)
        
        # 벡터 검색 실행
        result = collection.query.near_vector(
            near_vector=vector,
            limit=limit,
            return_metadata=wvc.query.MetadataQuery(distance=True)
        )
        
        # Supabase와 동일한 인터페이스로 데이터 변환
        # similarity는 (1 - distance)로 계산하여 0~1 사이 값으로 맞춥니다.
        formatted_results = []
        for obj in result.objects:
            formatted_results.append({
                "content": obj.properties.get("content", ""),
                "metadata": obj.properties.get("metadata", {}),
                "similarity": 1 - (obj.metadata.distance if obj.metadata.distance is not None else 0)
            })
        return formatted_results
    
    return []

def get_ngrams(text: str) -> set:
    # JS: text.replace(/[^\wㄱ-ㅎ가-힣]/g, '')
    # Python: 영문(a-z), 숫자(0-9), 밑줄(_), 한글(ㄱ-ㅎ, 가-힣)을 제외하고 모두 제거
    clean_text = re.sub(r'[^a-zA-Z0-9_ㄱ-ㅎ가-힣]', '', text)
    
    grams = set()
    # 2글자씩 자르기
    for i in range(len(clean_text) - 1):
        grams.add(clean_text[i:i+2])
    return grams

def embedding_query(params: SearchQuery) -> List[float]:
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        
    embedding_result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=params.query_text,
        task_type="retrieval_query"
    )

    return embedding_result['embedding']


async def search_logic(params: SearchQuery, db_type: str = "supabase") -> List[Dict[str, Any]]:
    
    vector = embedding_query(params)

    CANDIDATE_LIMIT = 200
    
    raw_results = await fetch_vector_candidates(db_type, vector, params, CANDIDATE_LIMIT)

    if not raw_results:
        return []

    query_text = params.query_text
    
    # 키워드 (2글자 이상, 공백 기준 분리)
    query_keywords = [w for w in query_text.split() if len(w) >= 2]
    
    # 2-gram (함수 사용)
    query_grams = get_ngrams(query_text)

    # 최종 컷트라인
    FINAL_THRESHOLD = 0.6
    ranked_results = []

    # 정밀 채점
    for doc in raw_results:
        content = doc.get('content', '') or ""
        
        # 기본 점수 (벡터 유사도)
        # JS의 cosineSimilarity(queryVector, docVector)와 동일
        score = doc.get('similarity', 0)
        
        # [로직 A] 키워드 매칭 (+0.1)
        # JS: queryKeywords.forEach(word => { if (content.includes(word)) score += 0.1; });
        for word in query_keywords:
            if word in content:
                score += 0.1
        
        # [로직 B] 2-gram 매칭 (+0.02)
        # JS: queryGrams.forEach(gram => { if (content.includes(gram)) gramMatchCount++; });
        gram_match_count = 0
        for gram in query_grams:
            if gram in content:
                gram_match_count += 1
        
        score += (gram_match_count * 0.02)

        # 최종 필터링
        if score > FINAL_THRESHOLD:
            doc['final_score'] = score
            ranked_results.append(doc)

    # 점수 높은 순 정렬 (JS: b.score - a.score)
    ranked_results.sort(key=lambda x: x['final_score'], reverse=True)

    # 개수 제한 (JS: getCount)
    return ranked_results[:params.return_count]


async def search_target_table(params: SearchQuery) -> List[Dict[str, Any]]:
    # 1. 사용자 질문을 벡터로 변환 (Gemini 임베딩)
    vector = embedding_query(params)
    
    # 2. 검색할 8개 테이블 목록
    target_collections = [
        "Welfare_Doc", "Receipt", "Company", "Ceo_message", 
        "General", "Resource", "Mutual_aid", "Etc"
    ]
    
    limit_per_table = 3
    
    # 💡 [변경 포인트] 전체를 합치지 않고, 테이블별로 결과를 보관할 딕셔너리 준비
    table_results = {}
    table_max_scores = {}

    # 3. 각 테이블을 돌면서 벡터 검색 실행
    for collection_name in target_collections:
        try:
            collection = weaviate_client.collections.get(collection_name)
            
            result = collection.query.near_vector(
                near_vector=vector,
                limit=limit_per_table,
                return_metadata=wvc.query.MetadataQuery(distance=True)
            )
            
            candidates = []
            max_similarity = 0 # 이 테이블의 1등 점수
            
            # 4. 데이터 변환 및 이 테이블의 '최고 유사도' 찾기
            for obj in result.objects:
                distance = obj.metadata.distance if obj.metadata.distance is not None else 0
                similarity = 1 - distance
                
                candidates.append({
                    "id": str(obj.uuid),
                    "collection": collection_name, # 💡 나중에 출처를 밝히기 위해 테이블명 기록
                    "content": obj.properties.get("content", ""),
                    "fileName": obj.properties.get("fileName", ""), # 파일명도 꼭 가져오세요
                    "similarity": similarity
                })
                
                # 가장 높은 유사도 갱신
                if similarity > max_similarity:
                    max_similarity = similarity
            
            # 검색 결과가 1개라도 있다면 딕셔너리에 저장
            if candidates:
                table_results[collection_name] = candidates
                table_max_scores[collection_name] = max_similarity

        except Exception as e:
            # 특정 테이블이 아직 생성되지 않았거나 에러가 발생해도 멈추지 않고 패스
            print(f"⚠️ [Weaviate] {collection_name} 테이블 조회 중 에러 발생: {e}")
            continue

    # 5. [핵심 로직] 가장 높은 최고 점수를 제출한 테이블 찾기
    if not table_max_scores:
        print("⚠️ 모든 테이블에서 검색 결과를 찾을 수 없습니다.")
        return []

    best_table = max(table_max_scores, key=table_max_scores.get)
    best_score = table_max_scores[best_table]

    print(f"✅ [SEARCH DONE] 1등 테이블 선정: {best_table} (최고 유사도: {best_score:.4f})")
    
    # 6. 다른 테이블 결과는 전부 무시하고, 1등 테이블의 데이터만 가져옴
    best_candidates = table_results[best_table]
    
    # 확실하게 유사도 순으로 한 번 더 정렬
    best_candidates.sort(key=lambda x: x["similarity"], reverse=True)
    
    # 7. 설정된 match_count(없으면 기본값 3)만큼 잘라서 최종 리턴
    final_count = params.match_count if hasattr(params, 'match_count') else 3
    top_results = best_candidates[:final_count]
    
    return top_results

async def fetch_data_by_ids(table_name: str, ids: Union[str, List[str]]) -> List[Dict[str, Any]]:
    """
    1차 검색에서 찾은 IDs를 바탕으로 실제 데이터와 '연결된 관계도 데이터'를 한 번에 조회합니다.
    """
    # 단일 ID(문자열)가 들어와도 리스트로 변환하여 에러 방지
    if isinstance(ids, str):
        ids = [ids]
        
    try:
        collection = weaviate_client.collections.get(table_name)
        
        # 1. 이 테이블에 설정된 관계도(Edge) 이름 가져오기
        edge_name = RELATIONS_MAP.get(table_name)
        
        # 2. 관계도가 존재한다면, 부모/자식 데이터도 같이 가져오도록 세팅 (핵심 💡)
        return_references = []
        
        wq = wvc.query
        
        if edge_name:
            return_references.append(
                wq.QueryReference(
                    link_on=edge_name,
                    return_properties=["content", "fileName"] # 연결된 문서의 내용과 파일명
                )
            )
        
        # 3. ID 배열로 데이터 조회 (GraphQL의 ContainsAny 역할)
        result = collection.query.fetch_objects(
            filters=wq.Filter.by_id().contains_any(ids),
            return_references=return_references if return_references else None
        )
        
        final_results = []
        
        # 4. Agent가 읽기 좋게 원본 내용과 관계도 내용을 하나로 합치기
        for obj in result.objects:
            main_content = obj.properties.get("content", "")
            file_name = obj.properties.get("fileName", "")
            
            cross_ref_content = ""
            
            # 연결된 데이터가 있다면 텍스트로 풀어주기
            if edge_name and obj.references and edge_name in obj.references:
                for ref_obj in obj.references[edge_name].objects:
                    ref_text = ref_obj.properties.get("content", "")
                    ref_file = ref_obj.properties.get("fileName", "")
                    cross_ref_content += f"\n[참조 문서: {ref_file}] {ref_text}"
            
            final_results.append({
                "id": str(obj.uuid),
                "table": table_name,
                "fileName": file_name,
                "content": main_content,
                "cross_reference": cross_ref_content.strip() # AI 판단을 돕는 뒷배경 지식
            })
            
        return final_results
        
    except Exception as e:
        print(f"⚠️ [{table_name}] ID 기반 데이터 조회 중 에러 발생: {e}")
        return []