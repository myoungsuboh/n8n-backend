# app/api/routes.py
from fastapi import APIRouter, HTTPException
from app.schemas import SearchQuery
from app.service.retriever import search_logic, search_target_table

router = APIRouter()

@router.post("/search-docs")
async def search_documents(payload: SearchQuery):
    try:
        # 하나하나 풀어서 넣을 필요 없이 payload 통째로 전달!
        results = await search_logic(payload)
        
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    
@router.post("/search_company_knowledge")
async def search_company_knowledge(payload: SearchQuery):
    try:
        results = await search_target_table(payload.query_text)
        
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))