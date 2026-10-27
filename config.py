import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'college-quiz-portal-secure-secret-key-2026')
    DEBUG = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    # Supabase Configuration (supports both standard and Next.js / Vercel deployment variables)
    SUPABASE_URL = (
        os.environ.get('SUPABASE_URL') or
        os.environ.get('NEXT_PUBLIC_SUPABASE_URL') or
        ''
    ).strip()
    SUPABASE_KEY = (
        os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or
        os.environ.get('SUPABASE_KEY') or
        os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY') or
        os.environ.get('SUPABASE_ANON_KEY') or
        ''
    ).strip()
    DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()

    # Local SQLite fallback for offline development / verification (uses strict relational foreign keys)
    SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'college_quiz.db')

    # Session Configuration for Persistent Logins
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME_SECONDS', 60 * 60 * 24 * 14)) # 14 days
    SESSION_COOKIE_NAME = 'college_quiz_session'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

    # Faculty Authorized Credentials
    FACULTY_EMAIL = os.environ.get('FACULTY_EMAIL', 'ankita.gadekar@nmiet.edu.in').strip().lower()
    FACULTY_PASSWORD = os.environ.get('FACULTY_PASSWORD', 'nmiet@45')
    FACULTY_NAME = os.environ.get('FACULTY_NAME', 'Prof. Ankita Gadekar')
    
    # Admin Aliases
    ADMIN_EMAIL = FACULTY_EMAIL
    ADMIN_PASSWORD = FACULTY_PASSWORD
    ADMIN_NAME = FACULTY_NAME
    
    # Legacy Admin Credentials (optional)
    LEGACY_ADMIN_EMAIL = 'admin@college.edu'
    LEGACY_ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Admin@12345')
    LEGACY_ADMIN_NAME = 'Prof. Head of Examination'

    # Institutional Standard Divisions (A through Q)
    DIVISIONS = (
        'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q'
    )
