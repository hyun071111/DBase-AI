from flask import Flask
from sqlalchemy import text
from models import (
    db,
    User,
    UserCompany,
    Experience,
    CompanyInformation,
    JobInformation,
    ApplicationStatus,
    PresentCompany,
)
from datetime import date
from dotenv import load_dotenv
import os
import time

load_dotenv()

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    # Create tables if they don't exist
    db.create_all()

    company = CompanyInformation(
        id=0,
        year=2025,
        company_name="테스트 회사",
        deadline="2025-07-10",
        establishment_year=2025,
        business_type="소프트웨어 개발업",
        employee_count=5,
        main_business="서울디지텍고등학교",
        website="http://sdh.hs.kr",
        address="서울시 용산구 회나무로12길 27",
        ai_analysis="회사 테스트입니다.",
    )

    job_info = JobInformation(
        id=0,
        company_id=0,
        job_title="풀스택",
        recruitment_count=1,
        job_description="테스트",
        qualifications="서울디지텍고등학교 재학생",
        working_hours="9-6",
        work_type="정규직",
        internship_pay="시급 5000",
        salary="연봉 2500만",
        additional_requirements="테스트입니다",
    )

    application = ApplicationStatus(id=0, user_id=0, job_id=0, status="미확인")

    # User
    user = User(
        id=0,
        name="테스트",
        email="sdh230000@sdh.hs.kr",
        phone_number="010-0000-0000",
        address="서울시 용산구",
        category="학생",
        affiliation="3학년 3반",
        skills="python, javascript, linux",
        created_at=int(time.time() * 1000),
    )

    present_company = PresentCompany(
        id=0,
        company_id=company.id,
    )

    user_company = UserCompany(
        id=0,
        user_id=0,
        employment_status="취업 완료",
        desired_position="백엔드 개발자",
        company_id=0,
        # Date 타입에 맞게 date 객체로 수정
        work_start_date=date(2025, 7, 1),
        # Date 타입에 저장할 수 없는 문자열 "없음"을 None으로 수정
        work_end_date=None,
    )

    # exp1 = Experience(
    #     id=0,
    #     user_id=0,
    #     type="project",
    #     name="프로젝트 테스트",
    #     description="테스트",
    #     skills="react, nestjs, flask",
    #     url="http://127.0.0.1",
    # )
    # exp2 = Experience(
    #     id=1,
    #     user_id=0,
    #     type="experience",
    #     date=date(2025, 7, 10),
    #     name="서울디지텍고 해커톤",
    #     description="테스트",
    # )
    # exp3 = Experience(
    #     id=2,
    #     user_id=0,
    #     type="award",
    #     date=date(2025, 7, 10),
    #     name="서울디지텍고 해커톤 - 대상",
    #     description="서울디지텍고등학교",
    # )

    db.session.add_all(
        [
            company,
            user,
            user_company,
            # exp1,
            # exp2,
            # exp3,
            job_info,
            application,
            present_company,
        ]
    )
    db.session.commit()

    print("✅ 테스트 데이터가 성공적으로 삽입되었습니다.")
