import os
import pymupdf as fitz
import requests
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from datetime import datetime

# .env 파일에서 환경 변수 로드
load_dotenv()

# models.py에서 db 객체 임포트
from models import db, CompanyInformation, JobInformation

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
UPLOAD_JOB_INFO_ROOT = os.path.join(DBASE_ROOT_DIR, 'DBase-backend', 'uploads', 'jobInformation')


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
        'application_deadline': r'요청일:\s*([^\n]+)', 
        'job_category': r'모집직종\s*([^\n]+)',
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
    
    # PDF에서 추출한 인원 수가 문자열일 수 있으므로 정수로 변환 시도
    if info.get('num_employees'):
        try:
            info['num_employees'] = int(info['num_employees'])
        except (ValueError, TypeError):
            info['num_employees'] = None


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
    @app.route('/api/process-pdf', methods=['POST'])
    def process_pdf_api():
        if not request.is_json:
            return jsonify({"status": "error", "message": "요청 본문은 JSON 형식이어야 합니다."}), 400
        
        data = request.get_json()
        folder_id = data.get('folderId')
        file_name = data.get('fileName')

        if not folder_id:
            return jsonify({"status": "error", "message": "JSON 본문에 'folderId' 키가 없습니다."}), 400
        if not file_name:
            return jsonify({"status": "error", "message": "JSON 본문에 'fileName' 키가 없습니다."}), 400
            
        # os.path.join을 사용하여 안전하고 명확하게 전체 파일 경로를 구성합니다.
        # UPLOAD_JOB_INFO_ROOT가 './DBase-backend/uploads/jobInformation'와 같은 경로를 가리킵니다.
        # 여기에 전달받은 folder_id와 file_name을 순서대로 합쳐줍니다.
        # folder_id를 문자열로 변환하여 예기치 않은 타입 오류를 방지합니다.
        file_path = os.path.join(UPLOAD_JOB_INFO_ROOT, str(folder_id), file_name)
        
        # (디버깅용) 실제 구성된 경로를 서버 로그에 출력하여 확인할 수 있습니다.
        print(f"--- INFO: Accessing file at path: {file_path}")

        if not os.path.exists(file_path):
            # 파일이 존재하지 않을 경우, 계산된 경로를 에러 메시지에 포함하여 디버깅을 돕습니다.
            return jsonify({"status": "error", "message": f"지정된 경로에 파일이 없습니다: {file_path}"}), 404

        try:
            # --- 이후 로직은 기존과 동일 ---
            text = extract_text(file_path)
            if not text.strip():
                return jsonify({"status": "error", "message": f"'{file_name}'에서 텍스트를 추출할 수 없습니다."}), 500

            info = extract_info(text)
            if not info.get('company_name'):
                return jsonify({"status": "error", "message": "PDF에서 회사명을 추출할 수 없습니다."}), 422

            search_results = google_search(info.get('company_name'))
            search_summary = "\n\n".join(search_results[:5]) if search_results else "검색 결과 없음"
            
            ai_analysis_result = "LLM 미설정 또는 회사명 누락으로 AI 분석을 건너뜁니다."
            if llm_pipeline and info.get('company_name'):
                llm_prompt = (
                    f"다음 정보를 바탕으로 '{info['company_name']}'의 기업 분석 보고서를 작성해줘. "
                    "회사의 주력 사업, 사용하는 기술, 성장 가능성에 초점을 맞춰 전문가 관점에서 간결하게 400자 내외로 요약해줘. "
                    "불필요한 인사말이나 서론은 제외하고 핵심 내용만 포함해줘.\n\n"
                    f"## 추출 정보:\n- 주요 사업: {info.get('main_business', 'N/A')}\n"
                    f"- 모집 직종: {info.get('job_category', 'N/A')}\n"
                    f"- 필요 기술/자격: {info.get('qualifications', 'N/A')}\n\n"
                    f"## 웹 검색 결과 요약:\n{search_summary}\n\n"
                    "## 기업 분석 보고서:"
                )
                ai_result = llm_pipeline(llm_prompt, return_full_text=False)
                ai_analysis_result = ai_result[0]['generated_text'].strip()

            company = CompanyInformation.query.filter_by(company_name=info['company_name']).first()
            if not company:
                company = CompanyInformation(company_name=info['company_name'])
                db.session.add(company)

            try:
                company.year = int(info.get('recruitment_year')) if info.get('recruitment_year') else None
            except (ValueError, TypeError):
                company.year = None
                
            try:
                company.establishment_year = int(info.get('established').split('.')[0]) if info.get('established') else None
            except (ValueError, TypeError, IndexError, AttributeError):
                company.establishment_year = None
            
            deadline_str = info.get('application_deadline')
            if deadline_str:
                try:
                    clean_deadline_str = deadline_str.replace(" ", "")
                    company.deadline = datetime.strptime(clean_deadline_str, '%Y년%m월%d일').date()
                except ValueError:
                    company.deadline = None
            else:
                company.deadline = None
            
            company.business_type = info.get('business_type')
            company.employee_count = info.get('num_employees')
            company.main_business = info.get('main_business')
            company.website = info.get('website')
            company.address = info.get('location')
            company.ai_analysis = ai_analysis_result
            
            # JobInformation 객체에 데이터 매핑
            job_posting = JobInformation(
                company=company,
                job_title=info.get('job_category'),
                recruitment_count=info.get('positions'),
                job_description=info.get('job_description'),
                qualifications=info.get('qualifications'),
                working_hours=info.get('work_hours'),
                work_type=info.get('employment_type'),
                required_documents=info.get('required_documents'),
                internship_pay=info.get('intern_stipend'),
                salary=info.get('salary'),
                additional_requirements=info.get('other_requirements')
            )
            db.session.add(job_posting)
            db.session.commit()

            return jsonify({
                "status": "success",
                "message": f"'{file_name}' 파일이 성공적으로 처리되어 데이터베이스에 저장되었습니다.",
            }), 201

        except Exception as e:
            db.session.rollback()
            print(f"--- ERROR: '{file_name}' 처리 중 예외 발생: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"예상치 못한 오류가 발생했습니다: {str(e)}"}), 500

    return app

# ---------- 애플리케이션 실행 ----------
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=3000)