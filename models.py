from flask_sqlalchemy import SQLAlchemy

# db 객체를 먼저 생성합니다. 애플리케이션과 나중에 연결됩니다.
db = SQLAlchemy()

# 회사 정보를 저장하는 테이블 모델
class Company(db.Model):
    __tablename__ = 'Company Information'
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(256), nullable=False, unique=True)
    established = db.Column(db.String(20))
    business_type = db.Column(db.String(256))
    num_employees = db.Column(db.Integer)
    main_business = db.Column(db.Text)
    website = db.Column(db.String(512))
    location = db.Column(db.Text)
    ai_analysis = db.Column(db.Text)
    search_summary = db.Column(db.Text)
    # JobPosting 모델과의 관계 설정 (1:N)
    job_postings = db.relationship('JobPosting', backref='company', lazy=True, cascade="all, delete-orphan")

# 채용 공고 정보를 저장하는 테이블 모델
class JobPosting(db.Model):
    __tablename__ = 'Job information'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('Company Information.id'), nullable=False)
    recruitment_year = db.Column(db.String(10))
    application_deadline = db.Column(db.String(50))
    job_category = db.Column(db.String(256))
    positions = db.Column(db.Integer)
    job_description = db.Column(db.Text)
    qualifications = db.Column(db.Text)
    work_hours = db.Column(db.Text)
    employment_type = db.Column(db.Text)
    required_documents = db.Column(db.Text)
    intern_stipend = db.Column(db.String(100))
    salary = db.Column(db.String(100))
    other_requirements = db.Column(db.Text)