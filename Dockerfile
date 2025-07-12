# 1. 베이스 이미지 설정
# 공식 파이썬 런타임을 부모 이미지로 사용합니다.
FROM python:3.11-slim

# 2. 환경 변수 설정
# .pyc 파일 생성을 방지하고, print() 출력이 바로 터미널에 나타나도록 합니다.
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 3. 작업 디렉토리 설정
# 컨테이너 내에서 코드가 위치하고 실행될 기본 폴더를 설정합니다.
WORKDIR /app

# 4. 의존성 설치
# requirements.txt만 먼저 복사하여 Docker 캐시를 활용, 빌드 속도를 높입니다.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
# 현재 폴더(DBase-AI)의 모든 파일을 컨테이너의 /app 폴더로 복사합니다.
COPY . .

# 6. 포트 노출
# 애플리케이션이 컨테이너 내부에서 3000번 포트를 사용함을 명시합니다.
EXPOSE 3000

# 7. 애플리케이션 실행
# Gunicorn을 사용하여 앱을 실행합니다. 'app:create_app()'은
# app.py 파일의 create_app() 팩토리 함수를 찾아 실행하라는 의미입니다.
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "app:create_app()"]