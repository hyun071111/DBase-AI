from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.associationproxy import association_proxy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(191), nullable=False)
    email = db.Column(db.String(191), unique=True, nullable=False)
    phone_number = db.Column(db.String(191), unique=True, nullable=True)
    address = db.Column(db.String(191), nullable=True)
    category = db.Column(db.String(191), nullable=False)  # role in TypeORM
    affiliation = db.Column(db.String(191), nullable=True)
    skills = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.BigInteger, nullable=False)

    company = db.relationship("UserCompany", backref="user", uselist=False, cascade="all, delete-orphan")
    experiences = db.relationship("Experience", backref="user", cascade="all, delete-orphan")
    applications = db.relationship("ApplicationStatus", backref="user", cascade="all, delete-orphan")

class UserCompany(db.Model):
    __tablename__ = 'user_company'
    id = db.Column(db.Integer, primary_key=True)
    # onDelete: 'CASCADE' 반영
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), unique=True)
    employment_status = db.Column(db.String(50))
    desired_position = db.Column(db.String(100))
    # onDelete: 'CASCADE' 반영
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id', ondelete='CASCADE'), nullable=True)
    # TypeORM의 'date' 타입과 nullable=true 속성 반영
    work_start_date = db.Column(db.Date, nullable=True)
    work_end_date = db.Column(db.Date, nullable=True)

    # TypeORM의 @ManyToOne 관계를 반영
    company = db.relationship("CompanyInformation", backref="user_companies")

class Experience(db.Model):
    __tablename__ = 'user_experience'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.String(50))
    date = db.Column(db.Date, nullable=True)
    name = db.Column(db.String(255))
    description = db.Column(db.Text)
    skills = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(1024), nullable=True)

class CompanyInformation(db.Model):
    __tablename__ = 'company_information'
    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer)
    company_name = db.Column(db.String(255), unique=True)
    deadline = db.Column(db.String(255), nullable=True)  # Changed to String to match TypeORM
    establishment_year = db.Column(db.Integer)
    business_type = db.Column(db.String(255))
    employee_count = db.Column(db.Integer)
    main_business = db.Column(db.Text)
    website = db.Column(db.String(512), nullable=True)
    address = db.Column(db.Text)
    ai_analysis = db.Column(db.Text)

    jobs = db.relationship('JobInformation', backref='company', cascade="all, delete-orphan")
    present = db.relationship('PresentCompany', backref='company', cascade="all, delete-orphan")
    # user_companies backref는 UserCompany의 relationship에 의해 자동 생성됩니다.

class JobInformation(db.Model):
    __tablename__ = 'job_information'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id'))
    job_title = db.Column(db.Text, nullable=True)
    recruitment_count = db.Column(db.Integer)
    job_description = db.Column(db.Text, nullable=True)
    qualifications = db.Column(db.Text)
    working_hours = db.Column(db.Text)
    work_type = db.Column(db.Text)
    internship_pay = db.Column(db.String(100))
    salary = db.Column(db.String(100))
    additional_requirements = db.Column(db.Text)

    applications = db.relationship("ApplicationStatus", backref="job", cascade="all, delete-orphan")

class ApplicationStatus(db.Model):
    __tablename__ = 'application_status'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job_information.id'))
    status = db.Column(db.String(50), default='미확인')
    feedback = db.Column(db.Text, nullable=True)  # Fixed typo from 'feedbac'

class PresentCompany(db.Model):
    __tablename__ = 'present_company'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id'))