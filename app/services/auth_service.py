import json
from flask import session, request
from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.faculty_repository import FacultyRepository

class AuthService:
    @staticmethod
    def get_current_student():
        student_id = session.get('student_id')
        if not student_id:
            student_data = session.get('student')
            if student_data and isinstance(student_data, dict):
                student_id = student_data.get('id')
        if not student_id:
            return None
        student = StudentRepository.get_by_id(student_id)
        if student:
            # Sync session dict with database to guarantee up-to-date values
            session['student'] = {
                'id': student['id'],
                'full_name': student['full_name'],
                'roll_number': student['roll_number'],
                'division': student['division'],
                'class_name': student['class_name'],
                'department': student['department'],
                'email': student.get('email')
            }
            session['student_id'] = student['id']
            session.permanent = True
            return student
        return session.get('student')

    @staticmethod
    def get_current_faculty():
        faculty_id = session.get('faculty_id')
        faculty_data = session.get('faculty')
        if not faculty_id and not faculty_data:
            return None
        # Return faculty session identity without exposing any sensitive credentials
        return faculty_data

    @staticmethod
    def login_student(student):
        session['student_id'] = student['id']
        session['student'] = {
            'id': student['id'],
            'full_name': student['full_name'],
            'roll_number': student['roll_number'],
            'division': student['division'],
            'class_name': student['class_name'],
            'department': student['department'],
            'email': student.get('email')
        }
        session.permanent = True

    @staticmethod
    def login_faculty(faculty):
        fac_id = str(faculty.get('id', 'admin-01'))
        fac_name = faculty.get('full_name') or 'Prof. Head of Examination'
        fac_dept = faculty.get('department') or 'Computer Engineering'
        session['faculty_id'] = fac_id
        session['faculty'] = {
            'id': fac_id,
            'full_name': fac_name,
            'department': fac_dept,
            'role': 'faculty'
        }
        session.permanent = True

    @staticmethod
    def logout():
        session.pop('student_id', None)
        session.pop('student', None)
        session.pop('faculty_id', None)
        session.pop('faculty', None)
        session.clear()
