import os
from app import create_app
from models import db, User, UserCompany, Experience, CompanyInformation, JobInformation, ApplicationStatus, PresentCompany

app = create_app()

def init_database():
    """데이터베이스의 모든 테이블을 삭제하고 다시 생성합니다."""
    with app.app_context():
        print("데이터베이스 초기화를 시작합니다...")
        
        print("기존의 모든 테이블을 삭제합니다.")
        db.drop_all()
        
        print("새로운 테이블을 생성합니다.")
        db.create_all()
        
        print("데이터베이스 초기화가 완료되었습니다.")

if __name__ == '__main__':
    confirm = input("경고: 이 스크립트는 데이터베이스의 모든 데이터를 삭제하고 스키마를 재생성합니다.\n계속하시겠습니까? (yes/no): ")
    if confirm.lower() == 'yes':
        init_database()
    else:
        print("초기화가 취소되었습니다.")