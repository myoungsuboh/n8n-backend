from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastmcp import FastMCP
from fastmcp.server.http import create_streamable_http_app
from app.api.routes import router as api_router
from app.mcp.supabaseServer import supabase_mcp
from app.mcp.weaviateServer import weaviate_mcp

# 1. 수동으로 MCP 전용 앱 생성 (버그 우회 방식 그대로 유지)
supabase_app = create_streamable_http_app(
    server=supabase_mcp,
    streamable_http_path="/sse",
    debug=True
)

weaviate_app = create_streamable_http_app(
    server=weaviate_mcp,
    streamable_http_path="/sse",
    debug=True
)


# 2. FastAPI 수명주기
@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    # 1. 시작 로그
    print("✅ System Started: API & MCP are ready.")
    
    # 2. MCP의 lifespan 실행 (context manager 호출)
    async with supabase_app.lifespan(app):
        async with weaviate_app.lifespan(app):
            yield
        
    # 3. 종료 로그
    print("🛑 System Stopped")

app = FastAPI(lifespan=combined_lifespan)

# 3. CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=["https://pills-edit-enlargement-gem.trycloudflare.com/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. REST API 라우터 연결
app.include_router(api_router)

# 5. MCP 앱을 /mcp 경로에 마운트
app.mount("/supabase/mcp", supabase_app) # 외부 VB
app.mount("/weaviate/mcp", weaviate_app) # 사내 VB