import google.generativeai as genai
import re
import weaviate.classes as wvc
from app.core.database import supabase, weaviate_client
from app.core.config import GOOGLE_API_KEY
from app.schemas import SearchQuery
from typing import List, Dict, Any

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

async def search_logic(params: SearchQuery, db_type: str = "supabase") -> List[Dict[str, Any]]:
    
    if GOOGLE_API_KEY:
        genai.configure(api_key=GOOGLE_API_KEY)
        
    embedding_result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=params.query_text,
        task_type="retrieval_query"
    )

    vector = embedding_result['embedding']

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