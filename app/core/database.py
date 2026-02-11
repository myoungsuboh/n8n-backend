import google.generativeai as genai
import weaviate
from supabase import create_client, Client
from app.core.config import GOOGLE_API_KEY, SUPABASE_URL, SUPABASE_KEY

# 1. Google Gemini 설정
genai.configure(api_key=GOOGLE_API_KEY)

# 2. Supabase 클라이언트 생성
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 3. Weaviate 클라이언트 생성 (n8n 설정 정보 반영)
# n8n 이미지에서 확인된 192.168.0.210 주소와 포트를 사용합니다.
weaviate_client = weaviate.connect_to_local(
    host="192.168.0.210",
    port=28082,          # HTTP Port
    grpc_port=50051      # gRPC Port
)

# 서버 연결 상태 확인을 위한 헬스 체크 (선택 사항)
def check_db_connections():
    try:
        if weaviate_client.is_ready():
            print("✅ Weaviate is ready.")
        print("✅ Supabase is connected.")
    except Exception as e:
        print(f"❌ Connection error: {e}")