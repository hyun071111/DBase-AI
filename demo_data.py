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

    # 회사 두 개 정의 (id 생략, 자동 생성 권장)
    company1 = CompanyInformation(
        year=2025,
        company_name="테스트 회사 1",
        deadline="2025-07-10",
        establishment_year=2025,
        business_type="소프트웨어 개발업",
        employee_count=5,
        main_business="알리콘",
        website="http://sdh.hs.kr",
        address="서울특별시 성동구 고산자로 14길 26, 아케이드동 엠엘-비엠층 103호 (행당동, 지웰홈스 왕십리)",
        ai_analysis="회사 테스트입니다.",
    )

    company2 = CompanyInformation(
        year=2025,
        company_name="테스트 회사 2",
        deadline="2025-07-10",
        establishment_year=2025,
        business_type="소프트웨어 개발업",
        employee_count=5,
        main_business="슈퍼무브",
        website="http://sdh.hs.kr",
        address="서울특별시 강남구 역삼동 826 36번지 10층",
        ai_analysis="회사 테스트입니다.",
    )

    # 유저
    user = User(
        name="테스트",
        email="sdh230000@sdh.hs.kr",
        phone_number="010-0000-0000",
        address="서울시 용산구",
        category="학생",
        affiliation="3학년 3반",
        skills="python, javascript, linux",
        created_at=int(time.time() * 1000),
    )

    # 회사 먼저 DB에 저장해서 id값 받아야함
    db.session.add_all([company1, company2, user])
    db.session.commit()

    # 회사 id가 자동 생성됐으므로 id 확인 가능
    # 구직정보 (company1 참조)
    job_info = JobInformation(
        company_id=company1.id,
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

    # 지원 상태
    application = ApplicationStatus(
        user_id=user.id,
        job_id=job_info.id,  # 아직 job_info는 DB에 없으므로 id는 None, 추후 커밋 후 할당 가능
        status="미확인",
    )

    # 현재 재직 회사 (company1, company2 참조)
    present_company1 = PresentCompany(
        company_id=company1.id,
    )

    present_company2 = PresentCompany(
        company_id=company2.id,
    )

    # 유저 회사 이력 (company1 참조)
    user_company = UserCompany(
        user_id=user.id,
        employment_status="취업 완료",
        desired_position="백엔드 개발자",
        company_id=company1.id,
        work_start_date=date(2025, 7, 1),
        work_end_date=None,
    )

    # 먼저 job_info를 추가해서 id 받아야 application에 쓸 수 있음
    db.session.add(job_info)
    db.session.commit()

    # application의 job_id 업데이트
    application.job_id = job_info.id
    db.session.add(application)

    # 나머지 항목들 세션에 추가
    db.session.add_all([
        present_company1,
        present_company2,
        user_company,
        # exp1, exp2, exp3 등 필요하면 추가
    ])

    db.session.commit()

    print("✅ 테스트 데이터가 성공적으로 삽입되었습니다.")
