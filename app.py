import os
import pymupdf as fitz
import requests
import re
import pprint
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from models import db, CompanyInformation, JobInformation

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

DB_URL = os.getenv("DATABASE_URL")
SERPER_KEY = os.getenv("SERPER_API_KEY")
MODEL_ID = os.getenv("MODEL_ID", "sh2orc/Llama-3.1-Korean-8B-Instruct")
SERPER_URL = "https://google.serper.dev/search"

SCRIPT_PATH = os.path.abspath(__file__)
AI_DIR = os.path.dirname(SCRIPT_PATH)
DBASE_ROOT_DIR = os.path.dirname(AI_DIR)
UPLOAD_JOB_INFO_ROOT = os.path.join(DBASE_ROOT_DIR, "DBase-backend", "uploads")


# ---------- 유틸리티 함수 ----------


def extract_text(path):
    """PDF 파일 경로를 받아 텍스트를 추출합니다."""
    return "".join(page.get_text() for page in fitz.open(path))


def google_search(query, num=5):
    """주어진 쿼리로 Google 검색을 수행하고 결과를 반환합니다."""
    if not query or not SERPER_KEY:
        return []
    headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(SERPER_URL, json={"q": query, "num": num}, headers=headers)
        r.raise_for_status()
        return [
            f"제목: {i.get('title', 'N/A')}\n링크: {i.get('link', 'N/A')}\n내용: {i.get('snippet', '내용 없음')}"
            for i in r.json().get("organic", [])
        ]
    except requests.exceptions.RequestException as e:
        print(f"--- ERROR: Google 검색 실패: {e}")
        return []


def extract_info(text):
    """정규식을 사용하여 PDF 텍스트에서 구조화된 정보를 추출합니다."""
    info = {}
    patterns = {
        "company_name": r"회사명\s*(.*?)\s*사업자번호",
        "established": r"설립\s*일자\s*([\d\.\s]+)",
        "upte": r"업태\s*([^\n]+)",
        "jongmok": r"종목\s*([^\n]+)",
        "num_employees": r"상시근로자\s*수\s*(\d+)",
        "main_business": r"주요\s*사업\s*내용\s*([\s\S]+?)(?:홈페이지|대표자명)",
        "website": r"홈페이지\s*(https?://\S+)",
        "location": r"소재지\s*([\s\S]+?)\s*대표자명",
        "application_deadline": r"요청일:\s*([^\n]+)",
        "job_category": r"모집직종\s*([^\n]+)",
        "positions": r"모집인원\s*(\d+)\s*명",
        "job_description": r"직무내용\s*\(구체적\)\s*([\s\S]+?)\s*근무\s*형태",
        "qualifications": r"자격요건\s*\(우대자격\)\s*([\s\S]+?)\s*근무\s*시간",
        "employment_type": r"근무\s*형태\s*([\s\S]+?)\s*자격요건",
        "work_hours": r"근무\s*시간\s*([\s\S]+?)\s*접수\s*서류",
        "intern_stipend": r"실습\s*수당\s*\(현장실습\s*시\)\s*(.*?)(?:\n|$)",
        "salary": r"급여\s*\(정규직\s*채용\s*시\)\s*(.*?)(?:\n|$)",
        "other_requirements": r"기타\s*요구사항\s*([\s\S]+?)\s*요청일",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.DOTALL)
        info[key] = match.group(1).strip().replace("\n", " ") if match else None

    info["business_type"] = (
        f"{info['upte']} / {info['jongmok']}"
        if info.get("upte") and info.get("jongmok")
        else (info.get("upte") or info.get("jongmok"))
    )

    if info.get("num_employees"):
        try:
            info["num_employees"] = int(info["num_employees"])
        except (ValueError, TypeError):
            info["num_employees"] = None

    return info


# ---------- 애플리케이션 팩토리 함수 ----------
def create_app():
    """Flask 애플리케이션 인스턴스를 생성하고 설정합니다."""
    app = Flask(__name__)

    if not DB_URL or not SERPER_KEY:
        raise ValueError(
            "필수 환경 변수(DATABASE_URL, SERPER_API_KEY)가 .env 파일에 설정되지 않았습니다."
        )

    app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    CORS(app)

    db.init_app(app)
    migrate.init_app(app, db)

    global llm_pipeline
    if torch_import and SERPER_KEY:
        try:
            tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_ID,
                device_map="auto" if torch.cuda.is_available() else "cpu",
                torch_dtype=(
                    torch.float16 if torch.cuda.is_available() else torch.float32
                ),
                low_cpu_mem_usage=True,
            )
            llm_pipeline = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=1024,
                do_sample=True,
                temperature=0.5,
            )
            print("--- INFO: LLM 파이프라인 로딩 성공.")
        except Exception as e:
            print(f"--- ERROR: LLM 파이프라인 로딩 실패: {e}")
            llm_pipeline = None

    @app.route("/api/process-pdf", methods=["POST"])
    def process_pdf_api():
        """PDF 파일을 처리하여 회사 및 채용 정보를 추출하고 DB에 저장합니다."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] === [START] /api/process-pdf 요청 수신 ===")

        if not request.is_json:
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": "요청 본문은 JSON 형식이어야 합니다.",
                    }
                ),
                400,
            )

        data = request.get_json()
        file_name = data.get("fileName")

        print(
            f"[{timestamp}] [INFO] 요청 데이터: fileName='{file_name}'"
        )

        if not file_name:
            return (
                jsonify(
                    {"status": "error", "message": "fileName은 필수입니다."}
                ),
                400,
            )

        file_path = os.path.join(UPLOAD_JOB_INFO_ROOT, file_name)
        print(f"[{timestamp}] [INFO] 접근할 파일 경로: {file_path}")

        if not os.path.exists(file_path):
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"지정된 경로에 파일이 없습니다: {file_path}",
                    }
                ),
                404,
            )

        try:
            text = extract_text(file_path)
            if not text.strip():
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": f"'{file_name}'에서 텍스트를 추출할 수 없습니다.",
                        }
                    ),
                    500,
                )

            info = extract_info(text)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] --- [DEBUG] PDF에서 추출된 정보 (info) ---")
            pprint.pprint(info)
            print(f"[{timestamp}] ------------------------------------------")

            if not info.get("company_name"):
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "PDF에서 회사명을 추출할 수 없습니다.",
                        }
                    ),
                    422,
                )

            search_results = google_search(info.get("company_name"))
            search_summary = (
                "\n\n".join(search_results[:5]) if search_results else "검색 결과 없음"
            )

            ai_analysis_result = "LLM 미설정 또는 회사명 누락으로 AI 분석을 건너뜁니다."
            print(info.get("company_name"))
            if llm_pipeline and info.get("company_name"):
                llm_prompt = f"다음 정보를 바탕으로 '{info['company_name']}'의 기업 분석 보고서를 작성해줘. 회사의 주력 사업, 사용하는 기술, 성장 가능성에 초점을 맞춰 전문가 관점에서 간결하게 요약해줘(200자 내외). 불필요한 인사말이나 **마크다운 문법** 제외하고 핵심 내용만 포함해줘.\n\n## 웹 검색 결과 요약:\n{search_summary}\n\n## 기업 분석 보고서:"
                ai_result = llm_pipeline(llm_prompt, return_full_text=False)
                ai_analysis_result = ai_result[0]["generated_text"].strip()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] --- [DEBUG] AI 분석 결과 ---")
            print(ai_analysis_result)
            print(f"[{timestamp}] ----------------------------")

            company = CompanyInformation.query.filter_by(
                company_name=info["company_name"]
            ).first()
            if not company:
                company = CompanyInformation(company_name=info["company_name"])
                db.session.add(company)

            company.year = datetime.now().year

            deadline_str = info.get("application_deadline")
            if deadline_str:
                try:
                    date_match = re.search(
                        r"(\d{4}년\s*\d{1,2}월\s*\d{1,2}일)", deadline_str
                    )
                    if date_match:
                        clean_deadline_str = date_match.group(1).replace(" ", "")
                        company.deadline = datetime.strptime(
                            clean_deadline_str, "%Y년%m월%d일"
                        ).date()
                    else:
                        company.deadline = None
                except ValueError:
                    company.deadline = None
            else:
                company.deadline = None

            try:
                company.establishment_year = (
                    int(info.get("established").split(".")[0])
                    if info.get("established")
                    else None
                )
            except (ValueError, TypeError, IndexError, AttributeError):
                company.establishment_year = None

            company.business_type = info.get("business_type")
            company.employee_count = info.get("num_employees")
            company.main_business = info.get("main_business")
            company.website = info.get("website")
            company.address = info.get("location")
            company.ai_analysis = ai_analysis_result

            job_posting = JobInformation(
                company=company,
                job_title=info.get("job_category"),
                recruitment_count=info.get("positions"),
                job_description=info.get("job_description"),
                qualifications=info.get("qualifications"),
                working_hours=info.get("work_hours"),
                work_type=info.get("employment_type"),
                internship_pay=info.get("intern_stipend"),
                salary=info.get("salary"),
                additional_requirements=info.get("other_requirements"),
            )
            db.session.add(job_posting)

            # --- [중요] DB 저장 직전 데이터 로깅 ---
            company_data_to_save = {
                k: v for k, v in company.__dict__.items() if not k.startswith("_")
            }
            job_data_to_save = {
                k: v for k, v in job_posting.__dict__.items() if not k.startswith("_")
            }

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] --- [COMMIT] 데이터베이스에 저장될 최종 데이터 ---")
            print("\n[COMMIT] CompanyInformation:")
            pprint.pprint(company_data_to_save)
            print("\n[COMMIT] JobInformation:")
            pprint.pprint(job_data_to_save)
            print(f"[{timestamp}] --------------------------------------------------")

            db.session.commit()

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] === [SUCCESS] '{file_name}' 처리 및 DB 저장 완료 ===")

            return (
                jsonify(
                    {
                        "status": "success",
                        "message": f"'{file_name}' 파일이 성공적으로 처리되어 데이터베이스에 저장되었습니다.",
                    }
                ),
                201,
            )

        except Exception as e:
            db.session.rollback()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] !!! [ERROR] '{file_name}' 처리 중 예외 발생: {e} !!!")
            import traceback

            traceback.print_exc()
            return (
                jsonify(
                    {
                        "status": "error",
                        "message": f"예상치 못한 오류가 발생했습니다: {str(e)}",
                    }
                ),
                500,
            )

    return app


# ---------- 애플리케이션 실행 ----------
if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=3000)
