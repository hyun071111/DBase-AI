from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.associationproxy import association_proxy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20))
    address = db.Column(db.String(255))
    category = db.Column(db.String(50))
    affiliation = db.Column(db.String(100))
    skills = db.Column(db.Text)

    company = db.relationship("UserCompany", backref="user", uselist=False, cascade="all, delete-orphan")
    token = db.relationship("Token", backref="user", uselist=False, cascade="all, delete-orphan")
    experiences = db.relationship("Experience", backref="user", cascade="all, delete-orphan")
    applications = db.relationship("ApplicationStatus", backref="user", cascade="all, delete-orphan")

class UserCompany(db.Model):
    __tablename__ = 'user_company'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    employment_status = db.Column(db.String(50))
    desired_position = db.Column(db.String(100))
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id'))
    work_start_date = db.Column(db.Date)
    work_end_date = db.Column(db.Date)

class Experience(db.Model):
    __tablename__ = 'experience'
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
    deadline = db.Column(db.Date)
    establishment_year = db.Column(db.Integer)
    business_type = db.Column(db.String(255))
    employee_count = db.Column(db.Integer)
    main_business = db.Column(db.Text)
    website = db.Column(db.String(512))
    address = db.Column(db.Text)
    ai_analysis = db.Column(db.Text)

    jobs = db.relationship('JobInformation', backref='company', cascade="all, delete-orphan")
    present = db.relationship('PresentCompany', backref='company', cascade="all, delete-orphan")

class JobInformation(db.Model):
    __tablename__ = 'job_information'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id'))
    job_title = db.Column(db.Text)
    recruitment_count = db.Column(db.Integer)
    job_description = db.Column(db.Text)
    qualifications = db.Column(db.Text)
    working_hours = db.Column(db.Text)
    work_type = db.Column(db.Text)
    required_documents = db.Column(db.Text) 
    internship_pay = db.Column(db.String(100))
    salary = db.Column(db.String(100))
    additional_requirements = db.Column(db.Text)

    applications = db.relationship("ApplicationStatus", backref="job", cascade="all, delete-orphan")

class ApplicationStatus(db.Model):
    __tablename__ = 'application_status'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    job_id = db.Column(db.Integer, db.ForeignKey('job_information.id'))
    status = db.Column(db.String(50))
    feedbac = db.Column(db.Text, nullable=True) # 'feedback'의 오타로 보이지만 일단 유지합니다.

class PresentCompany(db.Model):
    __tablename__ = 'present_company'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company_information.id'))
    address = association_proxy('company', 'address')