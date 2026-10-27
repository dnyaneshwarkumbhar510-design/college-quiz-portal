import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection

logger = logging.getLogger(__name__)

class QuizRepository:
    @staticmethod
    def get_all(subject_id=None):
        supabase = get_supabase_client()
        if supabase:
            try:
                query = supabase.table('quizzes').select('*, subjects(name)')
                if subject_id:
                    query = query.eq('subject_id', subject_id)
                res = query.order('created_at', desc=True).execute()
                rows = res.data or []
                
                # Fetch question counts for each quiz
                result = []
                for q in rows:
                    q_copy = dict(q)
                    sub = q_copy.get('subjects')
                    q_copy['subject_name'] = sub.get('name') if sub else (q_copy.get('subject') or 'General Subject')
                    
                    # Fetch count from quiz_questions
                    qq_res = supabase.table('quiz_questions').select('question_id', count='exact').eq('quiz_id', q_copy['id']).execute()
                    count = qq_res.count if qq_res.count is not None else (q_copy.get('total_questions') or 0)
                    q_copy['question_count'] = count
                    q_copy['total_questions'] = count
                    q_copy['is_published'] = bool(q_copy.get('published', False))
                    result.append(q_copy)
                return result
            except Exception as e:
                logger.error("Supabase get_all quizzes error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
        SELECT q.*, s.name as sub_name,
               (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id = q.id) as q_count,
               (SELECT COALESCE(SUM(ques.marks), 0) FROM quiz_questions qq JOIN questions ques ON qq.question_id = ques.id WHERE qq.quiz_id = q.id) as calc_marks
        FROM quizzes q
        LEFT JOIN subjects s ON q.subject_id = s.id
        """
        params = []
        if subject_id:
            sql += " WHERE q.subject_id = ?"
            params.append(subject_id)
        sql += " ORDER BY q.created_at DESC"
        
        cursor.execute(sql, params)
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            d['subject_name'] = d.get('sub_name') or d.get('subject') or 'General Subject'
            d['question_count'] = d.get('q_count', 0)
            d['total_questions'] = d.get('q_count', 0)
            if d.get('calc_marks', 0) > 0:
                d['total_marks'] = d['calc_marks']
            d['is_published'] = bool(d.get('published', 0))
            rows.append(d)
        conn.close()
        return rows

    @staticmethod
    def get_published(subject_id=None):
        all_quizzes = QuizRepository.get_all(subject_id)
        return [q for q in all_quizzes if q.get('is_published') or q.get('published')]

    @staticmethod
    def get_by_id(quiz_id):
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('quizzes').select('*, subjects(name)').eq('id', clean_id).maybe_single().execute()
                if not res.data:
                    return None
                q = dict(res.data)
                sub = q.get('subjects')
                q['subject_name'] = sub.get('name') if sub else (q.get('subject') or 'General Subject')
                
                qq_res = supabase.table('quiz_questions').select('question_id', count='exact').eq('quiz_id', clean_id).execute()
                count = qq_res.count if qq_res.count is not None else (q.get('total_questions') or 0)
                q['question_count'] = count
                q['total_questions'] = count
                q['is_published'] = bool(q.get('published', False))
                return q
            except Exception as e:
                logger.error("Supabase get quiz by id error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT q.*, s.name as sub_name,
               (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id = q.id) as q_count,
               (SELECT COALESCE(SUM(ques.marks), 0) FROM quiz_questions qq JOIN questions ques ON qq.question_id = ques.id WHERE qq.quiz_id = q.id) as calc_marks
        FROM quizzes q
        LEFT JOIN subjects s ON q.subject_id = s.id
        WHERE q.id = ?
        """, (clean_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d['subject_name'] = d.get('sub_name') or d.get('subject') or 'General Subject'
        d['question_count'] = d.get('q_count', 0)
        d['total_questions'] = d.get('q_count', 0)
        if d.get('calc_marks', 0) > 0:
            d['total_marks'] = d['calc_marks']
        d['is_published'] = bool(d.get('published', 0))
        return d

    @staticmethod
    def create_quiz(data):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        quiz_id = str(uuid.uuid4())
        
        # Ensure subject exists or is valid UUID if provided
        subject_id = data.get('subject_id')
        if subject_id and not isinstance(subject_id, str):
            subject_id = str(subject_id)
            
        is_pub = bool(data.get('is_published') if 'is_published' in data else data.get('published', False))
        payload = {
            'id': quiz_id,
            'title': str(data['title']).strip(),
            'description': str(data.get('description', '') or '').strip() or None,
            'subject_id': subject_id if subject_id and len(subject_id) == 36 else None,
            'subject': str(data.get('subject_name') or data.get('subject') or 'General Subject').strip(),
            'unit_number': int(data.get('unit_number', 1) or 1),
            'unit_title': str(data.get('unit_title', '') or '').strip() or f"Unit {data.get('unit_number', 1)}",
            'class_name': str(data.get('class_name', 'TE Computer')).strip(),
            'division': str(data.get('division', 'All')).strip(),
            'department': str(data.get('department', 'Computer Engineering')).strip(),
            'duration': int(data.get('duration_minutes') or data.get('duration') or 15),
            'total_questions': 0,
            'marks_per_question': float(data.get('marks_per_question', 1.0) or 1.0),
            'total_marks': float(data.get('total_marks', 0.0) or 0.0),
            'pass_percentage': float(data.get('passing_percentage') or data.get('pass_percentage') or 40.0),
            'created_by': data.get('created_by') or None,
            'status': 'published' if is_pub else (data.get('status') or 'draft'),
            'published': is_pub,
            'randomize_questions': bool(data.get('randomize_questions', False)),
            'randomize_options': bool(data.get('randomize_options', False)),
            'created_at': now,
            'updated_at': now
        }

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('quizzes').insert(payload).execute()
                if not res.data or len(res.data) == 0:
                    raise RuntimeError("Supabase returned empty response upon quiz creation")
                created = dict(res.data[0])
                created['is_published'] = is_pub
                created['question_count'] = 0
                return created
            except Exception as e:
                logger.error("Supabase create_quiz error: %s", e)
                raise RuntimeError(f"Database error creating quiz: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO quizzes (
            id, title, description, subject_id, subject, unit_number, unit_title,
            class_name, division, department, duration, total_questions,
            marks_per_question, total_marks, pass_percentage, created_by,
            status, published, randomize_questions, randomize_options,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            payload['id'], payload['title'], payload['description'],
            payload['subject_id'], payload['subject'], payload['unit_number'],
            payload['unit_title'], payload['class_name'], payload['division'],
            payload['department'], payload['duration'], payload['total_questions'],
            payload['marks_per_question'], payload['total_marks'], payload['pass_percentage'],
            payload['created_by'], payload['status'], 1 if is_pub else 0,
            1 if payload['randomize_questions'] else 0,
            1 if payload['randomize_options'] else 0,
            payload['created_at'], payload['updated_at']
        ))
        conn.commit()
        conn.close()
        
        payload['question_count'] = 0
        payload['is_published'] = False
        return payload

    @staticmethod
    def update_quiz(quiz_id, data):
        clean_id = str(quiz_id).strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        update_fields = {}
        if 'title' in data: update_fields['title'] = str(data['title']).strip()
        if 'description' in data: update_fields['description'] = str(data['description']).strip()
        if 'unit_number' in data: update_fields['unit_number'] = int(data['unit_number'])
        if 'unit_title' in data: update_fields['unit_title'] = str(data['unit_title']).strip()
        if 'duration' in data: update_fields['duration'] = int(data['duration'])
        if 'duration_minutes' in data: update_fields['duration'] = int(data['duration_minutes'])
        if 'pass_percentage' in data: update_fields['pass_percentage'] = float(data['pass_percentage'])
        if 'passing_percentage' in data: update_fields['pass_percentage'] = float(data['passing_percentage'])
        if 'randomize_questions' in data: update_fields['randomize_questions'] = bool(data['randomize_questions'])
        if 'randomize_options' in data: update_fields['randomize_options'] = bool(data['randomize_options'])
        update_fields['updated_at'] = now

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('quizzes').update(update_fields).eq('id', clean_id).execute()
                if not res.data or len(res.data) == 0:
                    raise RuntimeError(f"Quiz with ID {clean_id} not found in Supabase")
                return QuizRepository.get_by_id(clean_id)
            except Exception as e:
                logger.error("Supabase update_quiz error: %s", e)
                raise RuntimeError(f"Failed to update quiz in database: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        set_clauses = []
        params = []
        for k, v in update_fields.items():
            if k in ('randomize_questions', 'randomize_options'):
                set_clauses.append(f"{k} = ?")
                params.append(1 if v else 0)
            else:
                set_clauses.append(f"{k} = ?")
                params.append(v)
        
        params.append(clean_id)
        cursor.execute(f"UPDATE quizzes SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return QuizRepository.get_by_id(clean_id)

    @staticmethod
    def toggle_publish(quiz_id, publish_status):
        clean_id = str(quiz_id).strip()
        target_status = bool(publish_status)
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Check question count before publishing
        quiz = QuizRepository.get_by_id(clean_id)
        if not quiz:
            raise ValueError(f"Quiz with ID {clean_id} not found.")

        if target_status and quiz.get('question_count', 0) == 0:
            raise ValueError("This quiz cannot be published because it has 0 questions. Please add questions first.")

        status_text = 'published' if target_status else 'draft'

        supabase = get_supabase_client()
        if supabase:
            try:
                supabase.table('quizzes').update({
                    'published': target_status,
                    'status': status_text,
                    'updated_at': now
                }).eq('id', clean_id).execute()
                return QuizRepository.get_by_id(clean_id)
            except Exception as e:
                logger.error("Supabase toggle_publish error: %s", e)
                raise RuntimeError(f"Database error toggling publish state: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE quizzes
        SET published = ?, status = ?, updated_at = ?
        WHERE id = ?
        """, (1 if target_status else 0, status_text, now, clean_id))
        conn.commit()
        conn.close()
        return QuizRepository.get_by_id(clean_id)

    @staticmethod
    def delete_quiz(quiz_id):
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                # With ON DELETE CASCADE, deleting from quizzes cascades to quiz_questions and attempts
                supabase.table('quizzes').delete().eq('id', clean_id).execute()
                return True
            except Exception as e:
                logger.error("Supabase delete_quiz error: %s", e)
                raise RuntimeError(f"Database error deleting quiz: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quizzes WHERE id = ?", (clean_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def recalculate_totals(quiz_id):
        """
        Recalculates total_questions and total_marks based on authoritative quiz_questions join table.
        """
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                qq_res = supabase.table('quiz_questions')\
                    .select('question_id, questions(marks)')\
                    .eq('quiz_id', clean_id)\
                    .execute()
                
                rows = qq_res.data or []
                total_q = len(rows)
                total_m = sum(float(r.get('questions', {}).get('marks') or 1.0) for r in rows if r.get('questions'))
                
                update_payload = {
                    'total_questions': total_q,
                    'total_marks': total_m,
                    'updated_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
                if total_q == 0:
                    update_payload['published'] = False
                    update_payload['status'] = 'draft'
                
                supabase.table('quizzes').update(update_payload).eq('id', clean_id).execute()
                return total_q, total_m
            except Exception as e:
                logger.error("Supabase recalculate_totals error: %s", e)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
        SELECT COUNT(qq.id) as count, COALESCE(SUM(q.marks), 0) as total_marks
        FROM quiz_questions qq
        JOIN questions q ON qq.question_id = q.id
        WHERE qq.quiz_id = ?
        """, (clean_id,))
        row = cursor.fetchone()
        count = row['count'] if row else 0
        total_marks = row['total_marks'] if row else 0

        unpub = ", published = 0, status = 'draft'" if count == 0 else ""
        cursor.execute(f"""
        UPDATE quizzes
        SET total_questions = ?, total_marks = ?, updated_at = ? {unpub}
        WHERE id = ?
        """, (count, total_marks, datetime.datetime.now(datetime.timezone.utc).isoformat(), clean_id))
        conn.commit()
        conn.close()
        return count, total_marks
