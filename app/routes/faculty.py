from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.attempt_repository import AttemptRepository
from app.database.repositories.quiz_repository import QuizRepository
from config import Config

faculty_bp = Blueprint('faculty', __name__)

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fac = session.get('faculty')
        if not fac:
            return redirect(url_for('auth.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@faculty_bp.route('/admin/dashboard')
@faculty_required
def faculty_dashboard():
    fac = session.get('faculty')
    unit = request.args.get('unit', 0, type=int)
    stats = AttemptRepository.get_admin_dashboard_stats(unit)
    recent = AttemptRepository.get_admin_results_table()[:5]
    return render_template('faculty/dashboard.html', faculty=fac, stats=stats, recent_results=recent, current_unit=unit)

@faculty_bp.route('/admin/students')
@faculty_required
def faculty_students():
    fac = session.get('faculty')
    students = StudentRepository.get_all()
    # Enrich students with attempt counts and avg score
    enriched = []
    for s in students:
        attempts = AttemptRepository.get_student_attempts(s['id'])
        comp = [a for a in attempts if a.get('status') != 'in_progress']
        count = len(comp)
        avg = round(sum(float(a.get('obtained_marks', 0.0)) for a in comp) / count, 1) if count > 0 else 0.0
        pass_c = len([a for a in comp if a.get('status') == 'PASS'])
        s_copy = dict(s)
        s_copy['attempts_count'] = count
        s_copy['average_score'] = avg
        s_copy['pass_count'] = pass_c
        enriched.append(s_copy)
    return render_template('faculty/students.html', faculty=fac, students=enriched)

@faculty_bp.route('/admin/students/<student_id>')
@faculty_required
def faculty_student_detail(student_id):
    fac = session.get('faculty')
    student = StudentRepository.get_by_id(student_id)
    if not student:
        return redirect(url_for('faculty.faculty_students'))
    attempts = AttemptRepository.get_student_attempts(student_id)
    comp = [a for a in attempts if a.get('status') != 'in_progress']
    total_att = len(comp)
    avg_score = round(sum(float(a.get('obtained_marks', 0.0)) for a in comp) / total_att, 1) if total_att > 0 else 0.0
    pass_cnt = len([a for a in comp if a.get('status') == 'PASS'])
    fail_cnt = total_att - pass_cnt
    return render_template('faculty/student_detail.html', faculty=fac, student=student, attempts=comp,
                           total_attempts=total_att, avg_score=avg_score, pass_count=pass_cnt, fail_count=fail_cnt)

@faculty_bp.route('/admin/downloads')
@faculty_required
def faculty_downloads():
    fac = session.get('faculty')
    subjects = SubjectRepository.get_all()
    return render_template('faculty/downloads.html', faculty=fac, subjects=subjects, divisions=Config.DIVISIONS)

@faculty_bp.route('/admin/settings')
@faculty_required
def faculty_settings():
    fac = session.get('faculty')
    return render_template('faculty/settings.html', faculty=fac)

# ==================== FACULTY APIS ====================

@faculty_bp.route('/api/admin/stats')
def api_admin_stats():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    unit = request.args.get('unit', 0, type=int)
    stats = AttemptRepository.get_admin_dashboard_stats(unit)
    return jsonify({'success': True, 'stats': stats})

@faculty_bp.route('/api/admin/students')
def api_admin_students():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    students = StudentRepository.get_all()
    enriched = []
    for s in students:
        attempts = AttemptRepository.get_student_attempts(s['id'])
        comp = [a for a in attempts if a.get('status') != 'in_progress']
        count = len(comp)
        avg = round(sum(float(a.get('obtained_marks', 0.0)) for a in comp) / count, 1) if count > 0 else 0.0
        s_copy = dict(s)
        s_copy['attemptsCount'] = count
        s_copy['averageScore'] = avg
        enriched.append(s_copy)
    return jsonify({'success': True, 'students': enriched})

@faculty_bp.route('/api/admin/students/<student_id>')
def api_admin_student_detail(student_id):
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    student = StudentRepository.get_by_id(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    attempts = AttemptRepository.get_student_attempts(student_id)
    comp = [a for a in attempts if a.get('status') != 'in_progress']
    return jsonify({
        'success': True,
        'student': student,
        'attempts': comp
    })

@faculty_bp.route('/api/admin/subjects')
def api_admin_subjects():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    subjects = SubjectRepository.get_all()
    return jsonify({'success': True, 'subjects': subjects})
