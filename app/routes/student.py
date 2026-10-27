import datetime
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.services.student_service import StudentService
from app.services.quiz_service import QuizService
from app.services.question_service import QuestionService
from app.services.result_service import ResultService
from app.database.repositories.attempt_repository import AttemptRepository

student_bp = Blueprint('student', __name__)

def student_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        student = AuthService.get_current_student()
        if not student:
            return redirect(url_for('auth.student_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@student_bp.route('/student/dashboard')
@student_required
def student_dashboard():
    student = AuthService.get_current_student()
    if not student:
        return redirect(url_for('auth.student_login_page'))
    data = StudentService.get_dashboard_data(student['id'])
    if not data:
        session.pop('student_id', None)
        session.pop('student', None)
        return redirect(url_for('auth.student_login_page'))
    return render_template('student/dashboard.html', **data)

@student_bp.route('/student/quiz/<quiz_id>')
@student_required
def student_quiz_engine(quiz_id):
    student = AuthService.get_current_student()
    quiz = QuizService.get_quiz(quiz_id)
    if not quiz:
        return render_template('student/quiz_error.html', message="Examination unit not found.")
    if not (quiz.get('is_published') or quiz.get('published')):
        return render_template('student/quiz_error.html', message="This examination has not been published by faculty yet.")
    return render_template('student/quiz.html', quiz=quiz, student=student)

@student_bp.route('/student/results/<attempt_id>')
def student_result_page(attempt_id):
    student = AuthService.get_current_student()
    faculty = AuthService.get_current_faculty()
    if not student and not faculty:
        return redirect(url_for('auth.student_login_page'))
    details = ResultService.get_attempt_details(attempt_id)
    if not details:
        return render_template('student/quiz_error.html', message="Scorecard record not found.")
    # If authenticated as student (and not faculty), enforce ownership
    if student and not faculty and str(details['student_id']) != str(student['id']):
        return render_template('student/quiz_error.html', message="Access denied: You do not have permission to view this scorecard.")
    return render_template('student/results.html', result=details)

@student_bp.route('/student/history')
@student_required
def student_history():
    student = AuthService.get_current_student()
    attempts = AttemptRepository.get_student_attempts(student['id'])
    completed = [a for a in attempts if a.get('status') != 'in_progress']
    return render_template('student/history.html', student=student, attempts=completed)

# ==================== STUDENT APIS ====================

@student_bp.route('/api/student/profile')
@student_bp.route('/api/student/me')
def api_student_me():
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    return jsonify({
        'success': True,
        'student': student,
        'session': student
    })

@student_bp.route('/api/student/quizzes')
def api_student_quizzes():
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    quizzes = QuizService.get_published_quizzes()
    return jsonify({'success': True, 'quizzes': quizzes})

@student_bp.route('/api/student/quizzes/<quiz_id>/start', methods=['POST'])
def api_start_quiz_by_path(quiz_id):
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Student authorization required.'}), 401
    quiz = QuizService.get_quiz(quiz_id)
    if not quiz:
        return jsonify({'success': False, 'message': 'Quiz not found.'}), 404
    if not (quiz.get('is_published') or quiz.get('published')):
        return jsonify({'success': False, 'message': 'This examination is currently not published.'}), 403
    attempt, is_completed = AttemptRepository.start_or_resume_attempt(quiz_id, student['id'])
    if is_completed:
        return jsonify({
            'success': True,
            'isCompleted': True,
            'attemptId': attempt['id'],
            'message': 'This quiz has already been submitted.'
        })
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    try:
        end_dt = datetime.datetime.fromisoformat(attempt['server_end_time'].replace('Z', '+00:00'))
        remaining_seconds = max(0, int((end_dt - now_dt).total_seconds()))
    except Exception:
        remaining_seconds = int((quiz.get('duration') or 15) * 60)
    questions = QuestionService.get_student_exam_questions(quiz_id)
    return jsonify({
        'success': True,
        'attempt': attempt,
        'quiz': quiz,
        'questions': questions,
        'remainingSeconds': remaining_seconds
    })

@student_bp.route('/api/student/attempts/<attempt_id>/submit', methods=['POST'])
def api_submit_quiz_by_path(attempt_id):
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = request.get_json(force=True) or {}
    answers = data.get('answers') or {}
    details = ResultService.get_attempt_details(attempt_id)
    if not details:
        return jsonify({'success': False, 'message': 'Attempt not found.'}), 404
    if str(details['student_id']) != str(student['id']):
        return jsonify({'success': False, 'message': 'Forbidden: Attempt does not belong to this student.'}), 403
    evaluated = ResultService.submit_quiz(attempt_id, answers)
    return jsonify({
        'success': True,
        'message': 'Examination submitted and evaluated successfully.',
        'attemptId': attempt_id,
        'result': evaluated
    })

@student_bp.route('/api/student/results')
def api_student_results_list():
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    attempts = AttemptRepository.get_student_attempts(student['id'])
    completed = [a for a in attempts if a.get('status') != 'in_progress']
    return jsonify({'success': True, 'results': completed})

@student_bp.route('/api/student/dashboard')
def api_student_dashboard():
    student = AuthService.get_current_student()
    if not student:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    data = StudentService.get_dashboard_data(student['id'])
    if not data:
        return jsonify({'success': False, 'message': 'Student profile not found'}), 404
    return jsonify({
        'success': True,
        **data
    })

@student_bp.route('/api/student/start-quiz', methods=['POST'])
def api_start_quiz():
    try:
        student = AuthService.get_current_student()
        if not student:
            return jsonify({'success': False, 'message': 'Student authorization required.'}), 401

        data = request.get_json(force=True) or {}
        quiz_id = str(data.get('quizId') or data.get('quiz_id') or '').strip()
        if not quiz_id:
            return jsonify({'success': False, 'message': 'Quiz ID is required.'}), 400

        quiz = QuizService.get_quiz(quiz_id)
        if not quiz:
            return jsonify({'success': False, 'message': 'Quiz not found.'}), 404

        if not (quiz.get('is_published') or quiz.get('published')):
            return jsonify({'success': False, 'message': 'This examination is currently not published.'}), 403

        # Start or resume attempt using verified student ID
        attempt, is_completed = AttemptRepository.start_or_resume_attempt(quiz_id, student['id'])

        if is_completed:
            return jsonify({
                'success': True,
                'isCompleted': True,
                'attemptId': attempt['id'],
                'message': 'This quiz has already been submitted.'
            })

        # Calculate remaining seconds based on server_end_time
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        try:
            end_dt = datetime.datetime.fromisoformat(attempt['server_end_time'].replace('Z', '+00:00'))
            remaining_seconds = max(0, int((end_dt - now_dt).total_seconds()))
        except Exception:
            remaining_seconds = int((quiz.get('duration') or 15) * 60)

        # Retrieve questions securely (no keys/explanations included!)
        questions = QuestionService.get_student_exam_questions(quiz_id)

        return jsonify({
            'success': True,
            'attempt': attempt,
            'quiz': quiz,
            'questions': questions,
            'remainingSeconds': remaining_seconds
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@student_bp.route('/api/student/submit-quiz', methods=['POST'])
def api_submit_quiz():
    try:
        student = AuthService.get_current_student()
        if not student:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401

        data = request.get_json(force=True) or {}
        attempt_id = str(data.get('attemptId') or data.get('attempt_id') or '').strip()
        answers = data.get('answers') or {}

        if not attempt_id:
            return jsonify({'success': False, 'message': 'Attempt ID is required.'}), 400

        # Verify attempt ownership
        details = ResultService.get_attempt_details(attempt_id)
        if not details:
            return jsonify({'success': False, 'message': 'Attempt not found.'}), 404

        if str(details['student_id']) != str(student['id']):
            return jsonify({'success': False, 'message': 'Forbidden: Attempt does not belong to this student.'}), 403

        # Evaluate and record submission
        evaluated = ResultService.submit_quiz(attempt_id, answers)

        return jsonify({
            'success': True,
            'message': 'Examination submitted and evaluated successfully.',
            'attemptId': attempt_id,
            'result': evaluated
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@student_bp.route('/api/student/results/<attempt_id>')
def api_get_result(attempt_id):
    student = AuthService.get_current_student()
    faculty = AuthService.get_current_faculty()
    if not (student or faculty):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    details = ResultService.get_attempt_details(attempt_id)
    if not details:
        return jsonify({'success': False, 'message': 'Result not found'}), 404

    # Enforce student cannot view others' results
    if student and not faculty and str(details['student_id']) != str(student['id']):
        return jsonify({'success': False, 'message': 'Forbidden'}), 403

    return jsonify({
        'success': True,
        'result': details
    })
