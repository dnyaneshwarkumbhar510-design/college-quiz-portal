from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.services.quiz_service import QuizService
from app.services.question_service import QuestionService
from app.database.repositories.subject_repository import SubjectRepository
from config import Config

quizzes_bp = Blueprint('quizzes', __name__)

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fac = session.get('faculty')
        if not fac:
            return redirect(url_for('auth.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@quizzes_bp.route('/admin/quizzes')
@faculty_required
def quizzes_page():
    fac = session.get('faculty')
    quizzes = QuizService.get_quizzes()
    subjects = SubjectRepository.get_all()
    return render_template('faculty/quizzes.html', faculty=fac, quizzes=quizzes, subjects=subjects)

@quizzes_bp.route('/admin/quizzes/new')
@faculty_required
def new_quiz_page():
    fac = session.get('faculty')
    subjects = SubjectRepository.get_all()
    return render_template('faculty/quiz_new.html', faculty=fac, subjects=subjects, divisions=Config.DIVISIONS)

@quizzes_bp.route('/admin/preview/<quiz_id>')
@faculty_required
def quiz_preview_page(quiz_id):
    fac = session.get('faculty')
    quiz = QuizService.get_quiz(quiz_id)
    if not quiz:
        return redirect(url_for('quizzes.quizzes_page'))
    questions = QuestionService.get_questions_for_quiz(quiz_id)
    return render_template('faculty/preview.html', faculty=fac, quiz=quiz, questions=questions)

# ==================== QUIZ APIS ====================

@quizzes_bp.route('/api/admin/quizzes', methods=['GET', 'POST'])
@quizzes_bp.route('/api/faculty/quizzes', methods=['GET', 'POST'])
def api_quizzes():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        subject_id = request.args.get('subjectId') or request.args.get('subject_id')
        quizzes = QuizService.get_quizzes(subject_id)
        subjects = SubjectRepository.get_all()
        return jsonify({'success': True, 'quizzes': quizzes, 'subjects': subjects})

    # POST - Create Quiz
    try:
        data = request.get_json(force=True) or {}
        if not data.get('title'):
            return jsonify({'success': False, 'message': 'Quiz Title is required.'}), 400

        data['created_by'] = fac.get('id')
        created = QuizService.create_quiz(data)

        return jsonify({
            'success': True,
            'quiz': created,
            'message': 'Quiz created successfully'
        }), 201
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Failed to create quiz: %s", e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 400

@quizzes_bp.route('/api/admin/quizzes/<quiz_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
@quizzes_bp.route('/api/faculty/quizzes/<quiz_id>', methods=['GET', 'PUT', 'PATCH', 'DELETE'])
def api_quiz_detail(quiz_id):
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        quiz = QuizService.get_quiz(quiz_id)
        if not quiz:
            return jsonify({'success': False, 'message': 'Quiz not found'}), 404
        questions = QuestionService.get_questions_for_quiz(quiz_id)
        return jsonify({'success': True, 'quiz': quiz, 'questions': questions})

    if request.method in ('PUT', 'PATCH'):
        try:
            data = request.get_json(force=True) or {}
            if 'is_published' in data or 'published' in data:
                target_pub = bool(data.get('is_published') if 'is_published' in data else data.get('published'))
                updated = QuizService.toggle_publish(quiz_id, target_pub)
                status_label = 'published' if target_pub else 'unpublished'
                return jsonify({
                    'success': True,
                    'quiz': updated,
                    'message': f"Quiz {status_label} successfully."
                })
            
            updated = QuizService.update_quiz(quiz_id, data)
            return jsonify({'success': True, 'quiz': updated, 'message': 'Quiz updated successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    if request.method == 'DELETE':
        try:
            QuizService.delete_quiz(quiz_id)
            return jsonify({'success': True, 'message': 'Quiz deleted successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

@quizzes_bp.route('/api/faculty/quizzes/<quiz_id>/questions', methods=['GET', 'POST'])
def api_faculty_quiz_questions(quiz_id):
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        questions = QuestionService.get_questions_for_quiz(quiz_id)
        return jsonify({'success': True, 'questions': questions})

    try:
        data = request.get_json(force=True) or {}
        data['created_by'] = fac.get('id')
        data['quiz_id'] = quiz_id
        created = QuestionService.create_question(data)
        return jsonify({'success': True, 'question': created, 'message': 'Question added successfully.'}), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400
