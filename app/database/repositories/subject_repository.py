import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection

logger = logging.getLogger(__name__)

class SubjectRepository:
    @staticmethod
    def get_all():
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').order('name', desc=False).execute()
                return res.data or []
            except Exception as e:
                logger.error("Supabase get_all subjects error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subjects ORDER BY name ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_by_id(subject_id):
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').eq('id', subject_id).maybe_single().execute()
                return res.data
            except Exception as e:
                logger.error("Supabase get subject by id error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def create(data):
        return SubjectRepository.get_or_create(
            code=data.get('code', 'SUB'),
            name=data.get('name', 'Subject'),
            department=data.get('department', 'Computer Engineering'),
            class_name=data.get('class_name', 'TE Computer'),
            description=data.get('description', '')
        )

    @staticmethod
    def get_or_create(code, name, department='Computer Engineering', class_name='TE Computer', description=''):
        clean_code = str(code).strip().upper()
        clean_name = str(name).strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').eq('code', clean_code).maybe_single().execute()
                if res.data:
                    return res.data
                
                sub_id = str(uuid.uuid4())
                new_sub = {
                    'id': sub_id,
                    'code': clean_code,
                    'name': clean_name,
                    'department': department,
                    'class_name': class_name,
                    'description': description,
                    'created_at': now,
                    'updated_at': now
                }
                insert_res = supabase.table('subjects').insert(new_sub).execute()
                if insert_res.data and len(insert_res.data) > 0:
                    return insert_res.data[0]
                return new_sub
            except Exception as e:
                logger.error("Supabase get_or_create subject error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subjects WHERE UPPER(code) = UPPER(?)", (clean_code,))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

        sub_id = str(uuid.uuid4())
        cursor.execute("""
        INSERT INTO subjects (id, code, name, department, class_name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_id, clean_code, clean_name, department, class_name, description, now, now))
        conn.commit()
        conn.close()
        return {
            'id': sub_id,
            'code': clean_code,
            'name': clean_name,
            'department': department,
            'class_name': class_name,
            'description': description,
            'created_at': now,
            'updated_at': now
        }
