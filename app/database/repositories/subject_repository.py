import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection

logger = logging.getLogger(__name__)

class SubjectRepository:
    DEFAULT_SUBJECTS = [
        {
            'id': 'c0000000-0000-0000-0000-000000000001',
            'code': 'CS301',
            'name': 'Data Structures & Algorithms',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': 'Linear and non-linear data structures, trees, graphs, sorting, and asymptotic analysis.'
        },
        {
            'id': 'c0000000-0000-0000-0000-000000000002',
            'code': 'CS302',
            'name': 'Database Management Systems',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': 'Relational database architecture, SQL, relational calculus, normalization, and concurrency control.'
        }
    ]

    @staticmethod
    def get_all():
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').order('name', desc=False).execute()
                rows = res.data or []
                if not rows:
                    SubjectRepository._seed_defaults_supabase(supabase)
                    res = supabase.table('subjects').select('*').order('name', desc=False).execute()
                    rows = res.data or []
                return rows
            except Exception as e:
                logger.error("Supabase get_all subjects error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subjects ORDER BY name ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        if not rows:
            SubjectRepository._seed_defaults_local(cursor)
            conn.commit()
            cursor.execute("SELECT * FROM subjects ORDER BY name ASC")
            rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def _seed_defaults_supabase(supabase):
        try:
            for s in SubjectRepository.DEFAULT_SUBJECTS:
                supabase.table('subjects').upsert(s).execute()
            logger.info("Default subjects seeded successfully in Supabase.")
        except Exception as e:
            logger.warning("Could not auto-seed default subjects in Supabase: %s", e)

    @staticmethod
    def _seed_defaults_local(cursor):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for s in SubjectRepository.DEFAULT_SUBJECTS:
            cursor.execute("""
            INSERT OR IGNORE INTO subjects (id, code, name, department, class_name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (s['id'], s['code'], s['name'], s['department'], s['class_name'], s['description'], now, now))

    @staticmethod
    def get_by_id(subject_id):
        if not subject_id:
            return None
        clean_id = str(subject_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').eq('id', clean_id).maybe_single().execute()
                return res.data
            except Exception as e:
                logger.error("Supabase get subject by id error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM subjects WHERE id = ?", (clean_id,))
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
                # Exact columns matching Supabase PostgreSQL schema (without updated_at)
                new_sub = {
                    'id': sub_id,
                    'code': clean_code,
                    'name': clean_name,
                    'department': department,
                    'class_name': class_name,
                    'description': description
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
