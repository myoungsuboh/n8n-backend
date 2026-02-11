import uvicorn
import os
from dotenv import load_dotenv

# .env 파일 로드 (환경변수 설정)
load_dotenv()

if __name__ == "__main__":
    # 개발 모드인지 확인 (기본값: True)
    # 실제 운영 환경에서는 False로 두는 것이 좋습니다.
    is_dev = os.getenv("ENV", "development") == "development"

    print(f"🚀 Starting Server in {is_dev and 'Development' or 'Production'} mode...")

    # Uvicorn 서버 실행
    # "app.api.main:app" -> app 폴더 안 api 폴더 안 main.py 파일의 app 객체를 실행하라
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",   # 외부(n8n 등)에서 접속 가능하게 설정
        port=8000,        # 포트 번호
        reload=is_dev     # 코드 수정 시 자동 재시작 (개발 편의성)
    )