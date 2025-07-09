import os
import fitz
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# models.py에서 db 객체 임포트
from models import db, Company, JobPosting

# Optional: Hugging Face Transformers 라이브러리 임포트
torch_import = True
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
except ImportError:
    torch_import = False
    print("Warning: torch or transformers not found. LLM features will be disabled.")


# ---------- 전역 확장 및 설정 변수 ----------
migrate = Migrate()
llm_pipeline = None

# 환경 변수에서 설정 값 로드
DB_URL = os.getenv("DATABASE_URL")
SERPER_KEY = os.getenv("SERPER_API_KEY")
MODEL_ID = os.getenv("MODEL_ID", "sh2orc/Llama-3.1-Korean-8B-Instruct") # 기본값 설정
SERPER_URL = "https://google.serper.dev/search"

# 파일 경로 동적 설정
SCRIPT_PATH = os.path.abspath(__file__)
AI_DIR = os.path.dirname(SCRIPT_PATH)
DBASE_ROOT_DIR = os.path.dirname(AI_DIR)
UPLOAD_BASE_DIR = os.path.join(DBASE_ROOT_DIR, 'DBase-backend', 'uploads')


# ---------- 유틸리티 함수 (변경 없음) ----------
def extract_text(path):
    """PDF 파일 경로를 받아 텍스트를 추출합니다."""
    return "".join(page.get_text() for page in fitz.open(path))

def google_search(query):
    """주어진 쿼리로 Google 검색을 수행하고 결과를 반환합니다."""
    if not query or not SERPER_KEY: return []
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(SERPER_URL, json={"q": query}, headers=headers)
        r.raise_for_status()
        return [f"제목: {i.get('title', 'N/A')}\n링크: {i.get('link', 'N/A')}\n내용: {i.get('snippet', '내용 없음')}" for i in r.json().get("organic", [])]
    except requests.exceptions.RequestException as e:
        print(f"--- ERROR: Google 검색 실패: {e}")
        return []

def extract_info(text):
    """정규식을 사용하여 텍스트에서 구조화된 정보를 추출합니다."""
    info = {}
    patterns = {
        'company_name': r'회사명\s*(.*?)\s*사업자번호', 'established': r'설립\s*일자\s*([\d\.\s]+)',
        'upte': r'업태\s*([^\n]+)', 'jongmok': r'종목\s*([^\n]+)', 'num_employees': r'상시근로자\s*수\s*(\d+)',
        'main_business': r'주요\s*사업\s*내용\s*([\s\S]+?)(?:홈페이지|대표자명)', 'website': r'홈페이지\s*(https?://\S+)',
        'location': r'소재지\s*([\s\S]+?)\s*대표자명', 'recruitment_year': r'요청일:\s*(\d{4})년',
        'application_deadline': r'요청일:\s*([^\n]+)', 'job_category': r'모집직종\s*([^\n]+)',
        'positions': r'모집인원\s*(\d+)\s*명',
        'job_description': r'직무내용\s*\(구체적\)\s*([\s\S]+?)\s*근무\s*형태',
        'qualifications': r'자격요건\s*\(우대자격\)\s*([\s\S]+?)\s*근무\s*시간',
        'employment_type': r'근무\s*형태\s*([\s\S]+?)\s*자격요건', 'work_hours': r'근무\s*시간\s*([\s\S]+?)\s*접수\s*서류',
        'required_documents': r'접수\s*서류\s*([\s\S]+?)\s*4대\s*사회보험',
        'intern_stipend': r'실습\s*수당\s*\(현장실습\s*시\)\s*(.*?)(?:\n|$)',
        'salary': r'급여\s*\(정규직\s*채용\s*시\)\s*(.*?)(?:\n|$)',
        'other_requirements': r'기타\s*요구사항\s*([\s\S]+?)\s*요청일'
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        info[key] = match.group(1).strip().replace('\n', ' ') if match else None
    
    info['business_type'] = f"{info['upte']} / {info['jongmok']}" if info.get('upte') and info.get('jongmok') else (info.get('upte') or info.get('jongmok'))
    if info.get('num_employees'): info['num_employees'] = int(info['num_employees'])
    
    return info


# ---------- 애플리케이션 팩토리 함수 ----------
def create_app():
    """Flask 애플리케이션 인스턴스를 생성하고 설정합니다."""
    app = Flask(__name__)
    
    # 1. 설정
    if not DB_URL or not SERPER_KEY:
        raise ValueError("필수 환경 변수(DATABASE_URL, SERPER_API_KEY)가 .env 파일에 설정되지 않았습니다.")
        
    app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 모든 라우트에 대해 CORS를 허용하여 API 테스트를 용이하게 함
    CORS(app)

    # 2. 확장 초기화
    db.init_app(app)
    migrate.init_app(app, db)

    # 3. LLM 파이프라인 초기화
    global llm_pipeline
    if torch_import and SERPER_KEY:
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID, device_map="auto" if torch.cuda.is_available() else "cpu",
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                low_cpu_mem_usage=True,
            )
            llm_pipeline = pipeline(
                "text-generation", model=model, tokenizer=tokenizer,
                max_new_tokens=400, do_sample=True, temperature=0.6,
            )
            print("--- INFO: LLM 파이프라인 로딩 성공.")
        except Exception as e:
            print(f"--- ERROR: LLM 파이프라인 로딩 실패: {e}")
            llm_pipeline = None

    # 4. API 라우트 등록
    # 함수 내에서 라우트를 정의하거나 블루프린트를 등록합니다.
    @app.route('/api/process-pdf', methods=['POST'])
    def process_pdf_api():
        # 1. 요청 유효성 검사
        if not request.is_json:
            return jsonify({"status": "error", "message": "요청 본문은 JSON 형식이어야 합니다."}), 400
        data = request.get_json()
        filename = data.get('filename')
        if not filename:
            return jsonify({"status": "error", "message": "JSON 본문에 'filename' 키가 없습니다."}), 400

        # 2. 파일 경로 확인
        file_path = os.path.join(UPLOAD_BASE_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": f"지정된 경로에 파일이 없습니다: {file_path}"}), 404

        try:
            # 3. PDF 처리 및 정보 추출
            text = extract_text(file_path)
            if not text.strip():
                return jsonify({"status": "error", "message": f"'{filename}'에서 텍스트를 추출할 수 없습니다."}), 500

            info = extract_info(text)
            if not info.get('company_name'):
                return jsonify({"status": "error", "message": "PDF에서 회사명을 추출할 수 없습니다."}), 422

            # 4. 외부 검색 및 AI 분석
            search_results = google_search(info.get('company_name'))
            info['search_summary'] = "\n\n".join(search_results[:5]) if search_results else "검색 결과 없음"
            if llm_pipeline and info.get('company_name'):
                llm_prompt = (
                    f"다음 정보를 바탕으로 '{info['company_name']}'의 기업 분석 보고서를 작성해줘. "
                    "회사의 주력 사업, 사용하는 기술, 성장 가능성에 초점을 맞춰 전문가 관점에서 간결하게 400자 내외로 요약해줘. "
                    "불필요한 인사말이나 서론은 제외하고 핵심 내용만 포함해줘.\n\n"
                    f"## 추출 정보:\n- 주요 사업: {info.get('main_business', 'N/A')}\n"
                    f"- 모집 직종: {info.get('job_category', 'N/A')}\n"
                    f"- 필요 기술/자격: {info.get('qualifications', 'N/A')}\n\n"
                    f"## 웹 검색 결과 요약:\n{info['search_summary']}\n\n"
                    "## 기업 분석 보고서:"
                )
                ai_result = llm_pipeline(llm_prompt, return_full_text=False)
                info['ai_analysis'] = ai_result[0]['generated_text'].strip()
            else:
                info['ai_analysis'] = "LLM 미설정 또는 회사명 누락으로 AI 분석을 건너뜁니다."

            # 5. 데이터베이스 트랜잭션 및 응답 반환
            company = Company.query.filter_by(company_name=info['company_name']).first()
            if not company:
                company = Company(company_name=info['company_name'])
                db.session.add(company)
            
            # 회사 정보 업데이트 (가독성을 위해 여러 줄로 분리)
            company.established = info.get('established')
            company.business_type = info.get('business_type')
            company.num_employees = info.get('num_employees')
            company.main_business = info.get('main_business')
            company.website = info.get('website')
            company.location = info.get('location')
            company.search_summary = info.get('search_summary')
            company.ai_analysis = info.get('ai_analysis')
            
            # 채용 공고 정보 추가
            job_posting = JobPosting(
                company=company,
                recruitment_year=info.get('recruitment_year'),
                application_deadline=info.get('application_deadline'),
                job_category=info.get('job_category'),
                positions=info.get('positions'),
                job_description=info.get('job_description'),
                qualifications=info.get('qualifications'),
                work_hours=info.get('work_hours'),
                employment_type=info.get('employment_type'),
                required_documents=info.get('required_documents'),
                intern_stipend=info.get('intern_stipend'),
                salary=info.get('salary'),
                other_requirements=info.get('other_requirements')
            )
            db.session.add(job_posting)
            db.session.commit()

            return jsonify({
                "status": "success",
                "message": f"'{filename}' 파일이 성공적으로 처리되어 데이터베이스에 저장되었습니다.",
                "data": { "company_id": company.id, "job_posting_id": job_posting.id }
            }), 201

        except Exception as e:
            db.session.rollback()
            print(f"--- ERROR: '{filename}' 처리 중 예외 발생: {e}")
            return jsonify({"status": "error", "message": f"예상치 못한 오류가 발생했습니다: {str(e)}"}), 500

    return app

# ---------- 애플리케이션 실행 ----------
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=3000)