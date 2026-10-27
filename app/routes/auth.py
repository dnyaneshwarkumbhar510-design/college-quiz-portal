from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.faculty_repository import FacultyRepository
from config import Config

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login/student', methods=['GET', 'POST'])
def student_login_page():
    # If already logged in as student, redirect to student dashboard
    if session.get('student'):
        return redirect(url_for('student.student_dashboard'))
    return render_template('auth/student_login.html', divisions=Config.DIVISIONS)

@auth_bp.route('/login/admin', methods=['GET', 'POST'])
def admin_login_page():
    # If already logged in as faculty, redirect to admin dashboard
    if session.get('faculty'):
        return redirect(url_for('faculty.faculty_dashboard'))
    return render_template('auth/faculty_login.html')

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    AuthService.logout()
    return redirect(url_for('home'))

# API Endpoints
@auth_bp.route('/api/auth/student-login', methods=['POST'])
def api_student_login():
    try:
        data = request.get_json(force=True) or {}
        if not data.get('full_name') or not data.get('roll_number') or not data.get('division'):
            return jsonify({'success': False, 'message': 'Full name, roll number, and division are required.'}), 400

        # Validate division
        div = str(data['division']).strip().upper()
        if div not in Config.DIVISIONS:
            return jsonify({'success': False, 'message': f"Division must be one of {', '.join(Config.DIVISIONS)}"}), 400

        student = StudentRepository.create_or_login(data)
        AuthService.login_student(student)

        return jsonify({
            'success': True,
            'student': student,
            'message': 'Student authenticated successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@auth_bp.route('/api/auth/admin-login', methods=['POST'])
def api_admin_login():
    try:
        data = request.get_json(force=True) or {}
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', '')).strip()

        if not email or not password:
            return jsonify({'success': False, 'message': 'Institutional email and password are required.'}), 400

        faculty = FacultyRepository.authenticate(email, password)
        if not faculty:
            return jsonify({'success': False, 'message': 'Invalid faculty credentials. Please check your email and password.'}), 401

        AuthService.login_faculty(faculty)
        safe_faculty = {
            'id': faculty.get('id'),
            'full_name': faculty.get('full_name', 'Faculty Member'),
            'department': faculty.get('department', 'Computer Engineering'),
            'role': 'faculty'
        }
        return jsonify({
            'success': True,
            'faculty': safe_faculty,
            'message': 'Faculty authenticated successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@auth_bp.route('/api/auth/login', methods=['POST'])
def api_generic_login():
    data = request.get_json(force=True) or {}
    if 'email' in data and 'password' in data and not data.get('roll_number'):
        return api_admin_login()
    return api_student_login()

@auth_bp.route('/api/auth/logout', methods=['POST'])
def api_logout():
    AuthService.logout()
    return jsonify({'success': True, 'message': 'Signed out successfully'})

@auth_bp.route('/api/auth/me', methods=['GET'])
def api_me():
    student = AuthService.get_current_student()
    faculty = AuthService.get_current_faculty()
    return jsonify({
        'success': True,
        'student': student,
        'faculty': faculty,
        'isAuthenticated': bool(student or faculty)
    })
