from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.services.quiz_service import QuizService
from app.services.question_service import QuestionService
from app.database.repositories.subject_repository import SubjectRepository

questions_bp = Blueprint('questions', __name__)

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fac = session.get('faculty')
        if not fac:
            return redirect(url_for('auth.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@questions_bp.route('/admin/questions')
@faculty_required
def questions_page():
    fac = session.get('faculty')
    initial_quiz_id = request.args.get('quizId') or ''
    quizzes = QuizService.get_quizzes()
    subjects = SubjectRepository.get_all()
    
    selected_quiz = None
    if initial_quiz_id:
        selected_quiz = next((q for q in quizzes if str(q['id']) == initial_quiz_id), None)
    if not selected_quiz and len(quizzes) > 0:
        selected_quiz = quizzes[0]
        initial_quiz_id = str(selected_quiz['id'])

    questions = QuestionService.get_questions_for_quiz(initial_quiz_id) if initial_quiz_id else []
    
    return render_template('faculty/questions.html',
                           faculty=fac,
                           quizzes=quizzes,
                           subjects=subjects,
                           selected_quiz=selected_quiz,
                           initial_quiz_id=initial_quiz_id,
                           questions=questions)

# ==================== QUESTIONS APIS ====================

@questions_bp.route('/api/admin/questions', methods=['GET', 'POST'])
def api_questions():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        quiz_id = request.args.get('quizId') or request.args.get('quiz_id')
        if not quiz_id:
            return jsonify({'success': False, 'message': 'quizId parameter is required.'}), 400
        questions = QuestionService.get_questions_for_quiz(quiz_id)
        return jsonify({'success': True, 'questions': questions})

    # POST - Create Question
    try:
        data = request.get_json(force=True) or {}
        data['created_by'] = fac.get('id')
        created = QuestionService.create_question(data)
        return jsonify({
            'success': True,
            'question': created,
            'message': 'Question added successfully.'
        }), 201
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@questions_bp.route('/api/admin/questions/<question_id>', methods=['GET', 'PUT', 'DELETE'])
@questions_bp.route('/api/faculty/questions/<question_id>', methods=['GET', 'PUT', 'DELETE'])
def api_question_detail(question_id):
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    if request.method == 'GET':
        from app.database.repositories.question_repository import QuestionRepository
        q = QuestionRepository.get_by_id(question_id)
        if not q:
            return jsonify({'success': False, 'message': 'Question not found'}), 404
        return jsonify({'success': True, 'question': q})

    if request.method == 'PUT':
        try:
            data = request.get_json(force=True) or {}
            updated = QuestionService.update_question(question_id, data)
            return jsonify({'success': True, 'question': updated, 'message': 'Question updated successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    if request.method == 'DELETE':
        try:
            quiz_id = request.args.get('quizId') or request.args.get('quiz_id')
            QuestionService.delete_question(question_id, quiz_id)
            return jsonify({'success': True, 'message': 'Question deleted successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400
