from flask import Blueprint, request, jsonify, render_template, redirect, url_for, session
from app.database.repositories.attempt_repository import AttemptRepository

analytics_bp = Blueprint('analytics', __name__)

def faculty_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        fac = session.get('faculty')
        if not fac:
            return redirect(url_for('auth.admin_login_page'))
        return f(*args, **kwargs)
    return decorated_function

@analytics_bp.route('/admin/analytics')
@faculty_required
def analytics_page():
    fac = session.get('faculty')
    unit = request.args.get('unit', 0, type=int)
    stats = AttemptRepository.get_admin_dashboard_stats(unit)
    return render_template('faculty/analytics.html', faculty=fac, stats=stats, current_unit=unit)

@analytics_bp.route('/api/admin/stats')
@analytics_bp.route('/api/admin/analytics')
@analytics_bp.route('/api/faculty/analytics')
def api_faculty_analytics():
    from app.services.auth_service import AuthService
    fac = AuthService.get_current_faculty()
    if not fac:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    unit = request.args.get('unit', 0, type=int)
    stats = AttemptRepository.get_admin_dashboard_stats(unit)
    return jsonify({'success': True, 'stats': stats, 'analytics': stats})
