import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection

logger = logging.getLogger(__name__)

class StudentRepository:
    @staticmethod
    def get_all():
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('students').select('*').order('roll_number', desc=False).execute()
                return res.data or []
            except Exception as e:
                logger.error("Supabase get_all students error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students ORDER BY CAST(roll_number AS INTEGER) ASC, roll_number ASC")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    @staticmethod
    def get_by_id(student_id):
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('students').select('*').eq('id', student_id).maybe_single().execute()
                return res.data
            except Exception as e:
                logger.error("Supabase get student by id error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_by_roll(roll_number, class_name, division):
        clean_roll = str(roll_number).strip()
        clean_class = str(class_name).strip()
        clean_div = str(division).strip().upper()

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('students')\
                    .select('*')\
                    .eq('roll_number', clean_roll)\
                    .eq('division', clean_div)\
                    .execute()
                if res.data and len(res.data) > 0:
                    exact = next((s for s in res.data if str(s.get('class_name', '')).strip().lower() == clean_class.lower()), res.data[0])
                    return exact
                return None
            except Exception as e:
                logger.error("Supabase get student by roll error: %s", e)
                raise
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM students WHERE LOWER(roll_number) = LOWER(?) AND UPPER(division) = UPPER(?)",
            (clean_roll, clean_div)
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        if rows:
            exact = next((s for s in rows if str(s.get('class_name', '')).strip().lower() == clean_class.lower()), rows[0])
            return exact
        return None

    @staticmethod
    def create_or_login(data):
        clean_roll = str(data['roll_number']).strip()
        clean_class = str(data['class_name']).strip()
        clean_div = str(data['division']).strip().upper()
        clean_name = str(data['full_name']).strip()
        clean_dept = str(data['department']).strip()
        clean_email = str(data.get('email', '') or '').strip() or None
        clean_id_num = str(data.get('student_id_number', '') or '').strip() or None
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        existing = StudentRepository.get_by_roll(clean_roll, clean_class, clean_div)
        if existing:
            # Update existing student profile information
            supabase = get_supabase_client()
            if supabase:
                try:
                    update_data = {
                        'full_name': clean_name,
                        'class_name': clean_class,
                        'department': clean_dept,
                        'updated_at': now
                    }
                    if clean_email:
                        update_data['email'] = clean_email
                    if clean_id_num:
                        update_data['student_id_number'] = clean_id_num
                    res = supabase.table('students').update(update_data).eq('id', existing['id']).execute()
                    if res.data and len(res.data) > 0:
                        return res.data[0]
                    return existing
                except Exception as e:
                    logger.error("Supabase update student error: %s", e)
                    raise
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE students
            SET full_name = ?, class_name = ?, department = ?, email = COALESCE(?, email), student_id_number = COALESCE(?, student_id_number), updated_at = ?
            WHERE id = ?
            """, (clean_name, clean_class, clean_dept, clean_email, clean_id_num, now, existing['id']))
            conn.commit()
            conn.close()
            existing['full_name'] = clean_name
            existing['class_name'] = clean_class
            existing['department'] = clean_dept
            if clean_email:
                existing['email'] = clean_email
            if clean_id_num:
                existing['student_id_number'] = clean_id_num
            return existing

        # Create new student record
        new_id = str(uuid.uuid4())
        payload = {
            'id': new_id,
            'full_name': clean_name,
            'roll_number': clean_roll,
            'division': clean_div,
            'class_name': clean_class,
            'department': clean_dept,
            'email': clean_email,
            'student_id_number': clean_id_num,
            'status': 'active',
            'created_at': now,
            'updated_at': now
        }

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('students').insert(payload).execute()
                if not res.data or len(res.data) == 0:
                    raise RuntimeError("Student insertion in Supabase returned no data")
                return res.data[0]
            except Exception as e:
                logger.error("Supabase student insert error: %s", e)
                # Re-check in case of race condition / unique constraint
                recheck = StudentRepository.get_by_roll(clean_roll, clean_class, clean_div)
                if recheck:
                    return recheck
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO students (id, full_name, roll_number, division, class_name, department, email, student_id_number, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload['id'], payload['full_name'], payload['roll_number'],
            payload['division'], payload['class_name'], payload['department'],
            payload['email'], payload['student_id_number'], payload['status'],
            payload['created_at'], payload['updated_at']
        ))
        conn.commit()
        conn.close()
        return payload
