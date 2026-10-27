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
            'description': 'Linear and non-linear data structures, trees, graphs, sorting, and asymptotic analysis.',
            'created_at': '2026-01-01T00:00:00+00:00',
            'updated_at': '2026-01-01T00:00:00+00:00'
        },
        {
            'id': 'c0000000-0000-0000-0000-000000000002',
            'code': 'CS302',
            'name': 'Database Management Systems',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': 'Relational database architecture, SQL, relational calculus, normalization, and concurrency control.',
            'created_at': '2026-01-01T00:00:00+00:00',
            'updated_at': '2026-01-01T00:00:00+00:00'
        }
    ]

    @staticmethod
    def get_all():
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').order('name', desc=False).execute()
                rows = (res.data if res is not None and getattr(res, 'data', None) else []) or []
                if not rows:
                    SubjectRepository._seed_defaults_supabase(supabase)
                    res = supabase.table('subjects').select('*').order('name', desc=False).execute()
                    rows = (res.data if res is not None and getattr(res, 'data', None) else []) or []
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
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        inserted_count = 0
        failed_count = 0
        existing_count = 0

        try:
            for s in SubjectRepository.DEFAULT_SUBJECTS:
                try:
                    # Check if subject with this code or id already exists
                    existing_code = supabase.table('subjects').select('id, code').eq('code', s['code']).maybe_single().execute()
                    if existing_code is not None and getattr(existing_code, 'data', None):
                        existing_count += 1
                        continue
                    existing_id = supabase.table('subjects').select('id').eq('id', s['id']).maybe_single().execute()
                    if existing_id is not None and getattr(existing_id, 'data', None):
                        existing_count += 1
                        continue

                    # Exact columns matching public.subjects in Supabase PostgreSQL schema:
                    # id, code, name, department, class_name, description, created_at, updated_at
                    seed_item = {
                        'id': s['id'],
                        'code': s['code'],
                        'name': s['name'],
                        'department': s.get('department', 'Computer Engineering'),
                        'class_name': s.get('class_name', 'TE Computer'),
                        'description': s.get('description', ''),
                        'created_at': s.get('created_at') or now,
                        'updated_at': s.get('updated_at') or now
                    }
                    res = supabase.table('subjects').insert(seed_item).execute()
                    if res is not None and getattr(res, 'data', None):
                        inserted_count += 1
                    else:
                        # Double-check insertion
                        verify = supabase.table('subjects').select('id').eq('code', s['code']).maybe_single().execute()
                        if verify is not None and getattr(verify, 'data', None):
                            inserted_count += 1
                        else:
                            failed_count += 1
                            logger.error("Insert returned no data and verification failed for default subject %s", s.get('code'))
                except Exception as item_err:
                    failed_count += 1
                    logger.error("Could not auto-seed default subject %s in Supabase: %s", s.get('code'), item_err)
            
            if failed_count > 0:
                logger.error("Default subjects auto-seeding encountered %d failures (inserted: %d, existing: %d).", failed_count, inserted_count, existing_count)
            else:
                logger.info("Default subjects auto-seeding completed in Supabase (inserted: %d, existing: %d).", inserted_count, existing_count)
        except Exception as e:
            logger.error("Could not auto-seed default subjects in Supabase: %s", e)

    @staticmethod
    def _seed_defaults_local(cursor):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for s in SubjectRepository.DEFAULT_SUBJECTS:
            cursor.execute("""
            INSERT OR IGNORE INTO subjects (id, code, name, department, class_name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (s['id'], s['code'], s['name'], s['department'], s['class_name'], s['description'], s.get('created_at') or now, s.get('updated_at') or now))

    @staticmethod
    def get_by_id(subject_id):
        if not subject_id:
            return None
        clean_id = str(subject_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('subjects').select('*').eq('id', clean_id).maybe_single().execute()
                if res is not None and getattr(res, 'data', None):
                    return res.data
                return None
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
                if res is not None and getattr(res, 'data', None):
                    return res.data
                
                sub_id = str(uuid.uuid4())
                # Exact columns matching Supabase PostgreSQL schema:
                # id, code, name, department, class_name, description, created_at, updated_at
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
                if insert_res is not None and getattr(insert_res, 'data', None):
                    d = insert_res.data
                    if isinstance(d, list) and len(d) > 0:
                        return d[0]
                    elif isinstance(d, dict):
                        return d
                
                # If insert response data was empty, query by code
                verify_res = supabase.table('subjects').select('*').eq('code', clean_code).maybe_single().execute()
                if verify_res is not None and getattr(verify_res, 'data', None):
                    return verify_res.data
                return new_sub
            except Exception as e:
                logger.error("Supabase get_or_create subject error: %s", e)
                # Race condition / concurrent insert handling: check if created by another request
                try:
                    retry_res = supabase.table('subjects').select('*').eq('code', clean_code).maybe_single().execute()
                    if retry_res is not None and getattr(retry_res, 'data', None):
                        return retry_res.data
                except Exception as retry_err:
                    logger.debug("Retry lookup after error also failed: %s", retry_err)
                raise RuntimeError(f"Database error in subject lookup/creation: {e}")

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

    @staticmethod
    def update(subject_id, data):
        if not subject_id:
            return None
        clean_id = str(subject_id).strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        supabase = get_supabase_client()
        if supabase:
            try:
                update_fields = {'updated_at': now}
                if 'code' in data: update_fields['code'] = str(data['code']).strip().upper()
                if 'name' in data: update_fields['name'] = str(data['name']).strip()
                if 'department' in data: update_fields['department'] = str(data['department']).strip()
                if 'class_name' in data: update_fields['class_name'] = str(data['class_name']).strip()
                if 'description' in data: update_fields['description'] = str(data.get('description', '') or '').strip()
                
                res = supabase.table('subjects').update(update_fields).eq('id', clean_id).execute()
                if res and getattr(res, 'data', None):
                    d = res.data
                    return d[0] if isinstance(d, list) and len(d) > 0 else d
                return SubjectRepository.get_by_id(clean_id)
            except Exception as e:
                logger.error("Supabase update subject error: %s", e)
                raise RuntimeError(f"Database error updating subject: {e}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        set_clauses = ["updated_at = ?"]
        params = [now]
        if 'code' in data:
            set_clauses.append("code = ?")
            params.append(str(data['code']).strip().upper())
        if 'name' in data:
            set_clauses.append("name = ?")
            params.append(str(data['name']).strip())
        if 'department' in data:
            set_clauses.append("department = ?")
            params.append(str(data['department']).strip())
        if 'class_name' in data:
            set_clauses.append("class_name = ?")
            params.append(str(data['class_name']).strip())
        if 'description' in data:
            set_clauses.append("description = ?")
            params.append(str(data.get('description', '') or '').strip())
        params.append(clean_id)
        cursor.execute(f"UPDATE subjects SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return SubjectRepository.get_by_id(clean_id)
