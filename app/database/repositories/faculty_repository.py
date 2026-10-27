import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection
from config import Config

logger = logging.getLogger(__name__)

class FacultyRepository:
    @staticmethod
    def get_by_email(email):
        clean_email = str(email).strip().lower()
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('faculty').select('*').eq('email', clean_email).maybe_single().execute()
                return res.data
            except Exception as e:
                logger.error("Supabase get faculty by email error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM faculty WHERE LOWER(email) = LOWER(?)", (clean_email,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def authenticate(email, password):
        clean_email = str(email).strip().lower()
        
        # Check against faculty environment / default credentials
        if clean_email == Config.FACULTY_EMAIL and password == Config.FACULTY_PASSWORD:
            fac = FacultyRepository.get_by_email(clean_email)
            if not fac:
                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                fac = {
                    'id': str(uuid.uuid4()),
                    'full_name': Config.FACULTY_NAME,
                    'email': Config.FACULTY_EMAIL,
                    'department': 'Computer Engineering',
                    'created_at': now,
                    'updated_at': now
                }
            return fac

        # Check legacy admin credentials
        if clean_email == Config.LEGACY_ADMIN_EMAIL.lower() and password == Config.LEGACY_ADMIN_PASSWORD:
            return {
                'id': 'admin-legacy-001',
                'full_name': Config.LEGACY_ADMIN_NAME,
                'email': Config.LEGACY_ADMIN_EMAIL,
                'department': 'Examination Authority'
            }

        # Check Supabase Auth if configured
        supabase = get_supabase_client()
        if supabase:
            try:
                auth_res = supabase.auth.sign_in_with_password({
                    'email': clean_email,
                    'password': password
                })
                if auth_res and auth_res.user:
                    fac = FacultyRepository.get_by_email(clean_email)
                    if fac:
                        return fac
                    return {
                        'id': auth_res.user.id,
                        'email': auth_res.user.email,
                        'full_name': auth_res.user.user_metadata.get('full_name', 'Faculty Member'),
                        'department': 'Computer Engineering'
                    }
            except Exception as e:
                logger.warning("Supabase auth check failed: %s", e)

        # Check database password_hash if present
        fac = FacultyRepository.get_by_email(clean_email)
        if fac and fac.get('password_hash') and fac['password_hash'] == password:
            return fac

        return None
