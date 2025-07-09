import os
from flask import Flask, request, jsonify
import requests
import json
from dotenv import load_dotenv
from flask_cors import CORS 

# .env 파일에서 환경 변수 로드
load_dotenv()

app = Flask(__name__)
CORS(app)

# 현재 스크립트 파일의 경로를 기준으로 'DBase-backend/roadmap_file' 디렉토리 찾기
SCRIPT_PATH = os.path.abspath(__file__)
AI_DIR = os.path.dirname(SCRIPT_PATH)
DBASE_ROOT_DIR = os.path.dirname(AI_DIR)
UPLOAD_BASE_DIR = os.path.join(DBASE_ROOT_DIR, 'DBase-backend', 'roadmap_file')

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# 각 직무에 해당하는 roadmap.sh 링크 매핑
ROADMAP_LINKS = {
    "ai-engineer": "[🔗 AI 엔지니어 로드맵](https://roadmap.sh/ai-engineer)",
    "app-android": "[🔗 Android 앱 개발자 로드맵](https://roadmap.sh/android)",
    "app-ios": "[🔗 IOS 앱 개발자 로드맵](https://roadmap.sh/ios)",
    "cyber-security": "[🔗 정보보안 로드맵](https://roadmap.sh/cyber-security)",
    "server-engineer": "[🔗 서버 엔지니어 로드맵](https://roadmap.sh/docker)", # 서버 엔지니어는 Docker 로드맵 사용
    "web-back": "[🔗 백엔드 개발자 로드맵](https://roadmap.sh/backend)",
    "web-front": "[🔗 프론트엔드 개발자 로드맵](https://roadmap.sh/frontend)",
}

def job_role_to_korean(job_role):
    """직무의 영어 이름을 한국어 이름으로 변환하여 프롬프트에 사용합니다."""
    mapping = {
        "ai-engineer": "AI 엔지니어",
        "app-android": "안드로이드 앱 개발",
        "app-ios": "iOS 앱 개발",
        "cyber-security": "정보보안",
        "server-engineer": "서버 엔지니어",
        "web-back": "웹 백엔드 개발",
        "web-front": "웹 프론트엔드 개발",
    }
    return mapping.get(job_role, job_role)

@app.route('/generate_roadmap', methods=['POST'])
def generate_roadmap():
    """
    POST 요청을 받아 AI 특성화고 학생을 위한 로드맵을 생성합니다.
    요청 본문에는 'job_role' (희망 직무)과 'duration' (학습 기간: 1, 3, 6개월)이 포함되어야 합니다.
    """
    job_role = request.json.get('job_role')
    duration = request.json.get('duration')

    # 필수 입력값 검증
    if not job_role or not duration:
        return jsonify({"error": "job_role과 duration은 필수 입력값입니다."}), 400

    # 유효한 직무 역할인지 검증
    if job_role not in ROADMAP_LINKS:
        return jsonify({"error": "유효하지 않은 job_role입니다. 유효한 값: ai-engineer, app-android, app-ios, cyber-security, server-engineer, web-back, web-front"}), 400

    try:
        # duration은 정수형이어야 합니다.
        int(duration)
    except ValueError:
        return jsonify({"error": "duration은 숫자여야 합니다 (예: 1, 3, 6)."}), 400

    # Gemini API 프롬프트
    prompt = f"""
    서울디지텍고등학교 학생을 위한 {job_role_to_korean(job_role)} {duration}개월 로드맵을 생성해줘.
    하나의 프로젝트를 주제로 삼고, 각 주차/개월별로 학습할 내용과 진행할 프로젝트 단계를 상세하게 작성해줘.
    로드맵 예시 파일이야.
    
    ---
    ## {job_role_to_korean(job_role)}: 추천 프로젝트 (사용 기술 스택)

    > 목표: 사용 기술 스택을 활용하여 추천 프로젝트를 개발하고, 프로젝트를 통해 배울 수 있는 내용을 학습합니다.

    ### 1주차: 1주차에 진행할 내용 (1개월 로드맵일 경우만)
    - 상세 내역 (- 로 리스트를 구분) 

    ### 3개월차: 3개월차에 진행할 내용 (3, 6개월 로드맵일 경우 개월별로 구분)
    - 상세 내역

    ### 최종: 프로젝트 마무리 및 배포 (로드맵의 마지막, 1개월 프로젝트는 4주차)
    - 코드 리팩토링 및 가독성 향상
    - 에러 핸들링 및 사용자 경험 개선 
    - 프로젝트 빌드 및 Netlify, Vercel 또는 GitHub Pages를 통한 배포
    - README.md 파일 작성 (프로젝트 설명, 사용 기술, 설치 및 실행 방법 등)
    - Git/GitHub를 통한 최종 코드 관리 및 포트폴리오 준비

    [🔗 {job_role_to_korean(job_role)} 로드맵](https://roadmap.sh/{job_role_to_korean(job_role)})
    ---
    
    예시 파일의 구조와 같이 Markdown 형식으로 제공하고, 마지막에는 {ROADMAP_LINKS[job_role]} 링크를 포함해줘.
    """

    headers = {
        'Content-Type': 'application/json',
    }
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "text/plain" 
        }
    }

    try:
        # Gemini API 호출
        response = requests.post(f"{GEMINI_API_URL}?key={GEMINI_API_KEY}", headers=headers, data=json.dumps(payload))
        response.raise_for_status() 
        gemini_response = response.json()

        # Gemini API 응답에서 생성된 텍스트를 추출
        if gemini_response and gemini_response.get('candidates'):
            generated_text = gemini_response['candidates'][0]['content']['parts'][0]['text']

            # Gemini가 로드맵 링크를 포함하지 않았을 경우 수동으로 추가
            if ROADMAP_LINKS[job_role] not in generated_text:
                generated_text += f"\n\n{ROADMAP_LINKS[job_role]}"

            # 생성된 로드맵 파일의 이름과 저장 경로를 정의
            filename = f"{duration}-{job_role}.md"
            save_path = os.path.join(UPLOAD_BASE_DIR, filename)

            # 생성된 로드맵 내용을 Markdown 파일로 저장
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(generated_text)

            # 성공 응답 반환
            return jsonify({
                "message": "로드맵이 성공적으로 생성되어 저장되었습니다.",
                "filename": filename,
                "path": save_path,
                "roadmap_content": generated_text 
            }), 200
        else:
            return jsonify({"error": "Gemini API 응답에서 로드맵을 생성할 수 없습니다. 응답 구조를 확인하세요."}), 500

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Gemini API 호출 중 오류 발생: {e}"}), 500
    except Exception as e:
        return jsonify({"error": f"로드맵 생성 중 예상치 못한 오류 발생: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
