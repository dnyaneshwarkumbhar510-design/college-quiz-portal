from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.services.auth_service import AuthService
from app.services.result_service import ResultService
from app.services.quiz_service import QuizService
from app.database.repositories.subject_repository import SubjectRepository
from config import Config

results_bp = Blueprint('results', __name__)

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fac = session.get('faculty')
        if not fac:
            return redirect(url_for('auth.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@results_bp.route('/admin/results')
@faculty_required
def results_page():
    fac = session.get('faculty')
    subjects = SubjectRepository.get_all()
    quizzes = QuizService.get_quizzes()
    results = ResultService.get_admin_results()
    overall = ResultService.get_overall_rankings()
    return render_template('faculty/results.html',
                           faculty=fac,
                           subjects=subjects,
                           quizzes=quizzes,
                           results=results,
                           overall_rankings=overall,
                           divisions=Config.DIVISIONS)

# ==================== RESULTS APIS ====================

@results_bp.route('/api/admin/results')
@results_bp.route('/api/faculty/results')
def api_admin_results():
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401

    res_type = request.args.get('type')
    subject_id = request.args.get('subjectId') or request.args.get('subject_id')
    quiz_id = request.args.get('quizId') or request.args.get('quiz_id')

    if res_type == 'overall-ranking':
        rankings = ResultService.get_overall_rankings(subject_id)
        return jsonify({'success': True, 'overallRankings': rankings})

    if res_type == 'unit-ranking':
        rankings = ResultService.get_unit_rankings(quiz_id)
        return jsonify({'success': True, 'unitRankings': rankings})

    filters = {
        'search': request.args.get('search'),
        'division': request.args.get('division'),
        'unitNumber': request.args.get('unitNumber', type=int),
        'quiz_id': quiz_id,
        'status': request.args.get('status')
    }
    rows = ResultService.get_admin_results(filters)
    return jsonify({'success': True, 'rows': rows})
