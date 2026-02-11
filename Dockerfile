FROM python:3.12-slim

# 2. 작업 폴더 설정
WORKDIR /app

# 3. 필수 시스템 패키지 설치 (git 등 혹시 모를 의존성 대비)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 4. [중요] 라이브러리 설치
# requirements.txt를 먼저 복사해서 설치해야 캐싱이 되어 빌드 속도가 빨라집니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 전체 복사 (app 폴더, run.py 등)
COPY . .

# 6. 포트 노출 (run.py 설정과 동일하게)
EXPOSE 8000

# 7. 실행 명령어 변경!
# 기존: CMD ["uvicorn", "main:app", ...]
# 변경: 이제 파이썬 파일(run.py)이 직접 서버를 켜므로 아래와 같이 바꿉니다.
CMD ["python", "run.py"]