import uuid
import datetime
import random
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection
from app.database.repositories.quiz_repository import QuizRepository

logger = logging.getLogger(__name__)

class QuestionRepository:
    @staticmethod
    def get_by_quiz(quiz_id):
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                # Query questions directly by quiz_id (authoritative Supabase schema)
                res = supabase.table('questions')\
                    .select('*')\
                    .eq('quiz_id', clean_id)\
                    .order('created_at', desc=False)\
                    .execute()
                
                rows = []
                for idx, q in enumerate(res.data or []):
                    q_copy = dict(q)
                    q_copy['quiz_id'] = clean_id
                    q_copy['question_order'] = idx + 1
                    rows.append(q_copy)
                return rows
            except Exception as e:
                logger.error("Supabase get questions for quiz %s error: %s", clean_id, e)
                raise RuntimeError(f"Database error loading questions: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if quiz_id column exists on questions table
        cursor.execute("PRAGMA table_info(questions)")
        q_cols = [c['name'] for c in cursor.fetchall()]
        
        if 'quiz_id' in q_cols:
            cursor.execute("""
            SELECT * FROM questions
            WHERE quiz_id = ?
            ORDER BY created_at ASC
            """, (clean_id,))
            rows = []
            for idx, r in enumerate(cursor.fetchall()):
                d = dict(r)
                d['quiz_id'] = clean_id
                d['question_order'] = idx + 1
                rows.append(d)
            conn.close()
            return rows
        else:
            cursor.execute("""
            SELECT q.*, qq.quiz_id, qq.question_order
            FROM questions q
            JOIN quiz_questions qq ON q.id = qq.question_id
            WHERE qq.quiz_id = ?
            ORDER BY qq.question_order ASC, q.created_at ASC
            """, (clean_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows

    get_questions_by_quiz_id = get_by_quiz

    @staticmethod
    def get_by_id(question_id):
        clean_id = str(question_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('questions').select('*').eq('id', clean_id).maybe_single().execute()
                return res.data
            except Exception as e:
                logger.error("Supabase get question by id error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM questions WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    @staticmethod
    def get_student_exam_questions(quiz_id):
        """
        Retrieves questions for active examination taking:
        - Security: Deliberately omits 'correct_answer' and 'explanation'
        - Supports randomization if quiz has randomize_questions enabled
        """
        clean_id = str(quiz_id).strip()
        quiz = QuizRepository.get_by_id(clean_id)
        if not quiz:
            raise ValueError(f"Quiz with ID {clean_id} not found.")

        questions = QuestionRepository.get_by_quiz(clean_id)

        # Randomize questions order if quiz configuration requests it
        if quiz.get('randomize_questions'):
            questions = list(questions)
            random.shuffle(questions)

        # Build sanitized student examination question objects
        exam_questions = []
        for q in questions:
            exam_q = {
                'id': q['id'],
                'quiz_id': clean_id,
                'question_text': q['question_text'],
                'option_a': q['option_a'],
                'option_b': q['option_b'],
                'option_c': q['option_c'],
                'option_d': q['option_d'],
                'marks': float(q.get('marks', 1.0) or 1.0)
            }
            exam_questions.append(exam_q)
        return exam_questions

    @staticmethod
    def create_question(data):
        clean_quiz_id = str(data['quiz_id']).strip()
        clean_text = str(data['question_text']).strip()
        clean_opt_a = str(data['option_a']).strip()
        clean_opt_b = str(data['option_b']).strip()
        clean_opt_c = str(data['option_c']).strip()
        clean_opt_d = str(data['option_d']).strip()
        clean_correct = str(data['correct_answer']).strip().upper()
        clean_marks = max(0.5, min(10.0, float(data.get('marks', 1.0) or 1.0)))
        clean_expl = str(data.get('explanation', '') or '').strip() or None
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not clean_quiz_id:
            raise ValueError("Target Quiz ID is required.")
        if not clean_text:
            raise ValueError("Question text is required.")
        if not (clean_opt_a and clean_opt_b and clean_opt_c and clean_opt_d):
            raise ValueError("All four options (A, B, C, D) are required.")
        if clean_correct not in ('A', 'B', 'C', 'D'):
            raise ValueError("Correct answer must be one of A, B, C, or D.")

        # Verify quiz exists
        quiz = QuizRepository.get_by_id(clean_quiz_id)
        if not quiz:
            raise ValueError(f"Target quiz with ID {clean_quiz_id} does not exist in the database.")

        question_id = str(uuid.uuid4())

        supabase = get_supabase_client()
        if supabase:
            # Standard Supabase questions payload matching 01_schema.sql
            supabase_q_payload = {
                'id': question_id,
                'quiz_id': clean_quiz_id,
                'question_text': clean_text,
                'option_a': clean_opt_a,
                'option_b': clean_opt_b,
                'option_c': clean_opt_c,
                'option_d': clean_opt_d,
                'correct_answer': clean_correct,
                'marks': clean_marks,
                'explanation': clean_expl,
                'created_at': now
            }

            try:
                q_res = supabase.table('questions').insert(supabase_q_payload).execute()
                if not q_res.data or len(q_res.data) == 0:
                    raise RuntimeError("Failed to insert question in Supabase.")

                # Recalculate totals on parent quiz
                QuizRepository.recalculate_totals(clean_quiz_id)

                inserted_q = dict(q_res.data[0])
                inserted_q['quiz_id'] = clean_quiz_id
                return inserted_q
            except Exception as e:
                logger.error("Supabase create_question error: %s", e)
                raise RuntimeError(f"Database error adding question: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(questions)")
        q_cols = [c['name'] for c in cursor.fetchall()]
        
        join_id = str(uuid.uuid4())
        
        if 'quiz_id' in q_cols:
            cursor.execute("""
            INSERT INTO questions (id, quiz_id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, marks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question_id, clean_quiz_id, clean_text,
                clean_opt_a, clean_opt_b, clean_opt_c, clean_opt_d,
                clean_correct, clean_expl, clean_marks, now, now
            ))
        else:
            cursor.execute("""
            INSERT INTO questions (id, question_text, option_a, option_b, option_c, option_d, correct_answer, explanation, marks, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                question_id, clean_text,
                clean_opt_a, clean_opt_b, clean_opt_c, clean_opt_d,
                clean_correct, clean_expl, clean_marks, now, now
            ))

        # Also insert into quiz_questions join table if table exists
        try:
            cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?", (clean_quiz_id,))
            order = cursor.fetchone()[0] + 1
            cursor.execute("""
            INSERT INTO quiz_questions (id, quiz_id, question_id, question_order, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (join_id, clean_quiz_id, question_id, order, now))
        except Exception:
            pass
        
        conn.commit()
        conn.close()

        QuizRepository.recalculate_totals(clean_quiz_id)

        return {
            'id': question_id,
            'quiz_id': clean_quiz_id,
            'question_text': clean_text,
            'option_a': clean_opt_a,
            'option_b': clean_opt_b,
            'option_c': clean_opt_c,
            'option_d': clean_opt_d,
            'correct_answer': clean_correct,
            'marks': clean_marks,
            'explanation': clean_expl,
            'created_at': now
        }

    @staticmethod
    def update_question(question_id, data):
        clean_id = str(question_id).strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        update_fields = {}
        if 'question_text' in data: update_fields['question_text'] = str(data['question_text']).strip()
        if 'option_a' in data: update_fields['option_a'] = str(data['option_a']).strip()
        if 'option_b' in data: update_fields['option_b'] = str(data['option_b']).strip()
        if 'option_c' in data: update_fields['option_c'] = str(data['option_c']).strip()
        if 'option_d' in data: update_fields['option_d'] = str(data['option_d']).strip()
        if 'correct_answer' in data: update_fields['correct_answer'] = str(data['correct_answer']).strip().upper()
        if 'marks' in data: update_fields['marks'] = max(0.5, min(10.0, float(data['marks'])))
        if 'explanation' in data: update_fields['explanation'] = str(data['explanation'] or '').strip() or None

        supabase = get_supabase_client()
        if supabase:
            try:
                res = supabase.table('questions').update(update_fields).eq('id', clean_id).execute()
                if not res.data or len(res.data) == 0:
                    raise RuntimeError("Question not found in database.")

                # Recalculate totals for parent quiz
                updated_q = res.data[0]
                if updated_q.get('quiz_id'):
                    QuizRepository.recalculate_totals(updated_q['quiz_id'])

                return QuestionRepository.get_by_id(clean_id)
            except Exception as e:
                logger.error("Supabase update_question error: %s", e)
                raise RuntimeError(f"Database error updating question: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        set_clauses = ["updated_at = ?"]
        params = [now]
        for k, v in update_fields.items():
            set_clauses.append(f"{k} = ?")
            params.append(v)
        params.append(clean_id)

        cursor.execute(f"UPDATE questions SET {', '.join(set_clauses)} WHERE id = ?", params)
        
        # Get affected quiz
        cursor.execute("SELECT quiz_id FROM questions WHERE id = ?", (clean_id,))
        row = cursor.fetchone()
        quiz_id = row['quiz_id'] if row and 'quiz_id' in row.keys() else None
        
        conn.commit()
        conn.close()

        if quiz_id:
            QuizRepository.recalculate_totals(quiz_id)

        return QuestionRepository.get_by_id(clean_id)

    @staticmethod
    def delete_question(question_id, quiz_id=None):
        clean_qid = str(question_id).strip()
        clean_quiz_id = str(quiz_id).strip() if quiz_id else None

        supabase = get_supabase_client()
        if supabase:
            try:
                # If quiz_id not provided, look it up first
                if not clean_quiz_id:
                    q_res = supabase.table('questions').select('quiz_id').eq('id', clean_qid).maybe_single().execute()
                    if q_res.data:
                        clean_quiz_id = q_res.data.get('quiz_id')

                supabase.table('questions').delete().eq('id', clean_qid).execute()

                if clean_quiz_id:
                    QuizRepository.recalculate_totals(clean_quiz_id)
                return True
            except Exception as e:
                logger.error("Supabase delete_question error: %s", e)
                raise RuntimeError(f"Database error deleting question: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        if not clean_quiz_id:
            cursor.execute("SELECT quiz_id FROM questions WHERE id = ?", (clean_qid,))
            row = cursor.fetchone()
            if row and 'quiz_id' in row.keys() and row['quiz_id']:
                clean_quiz_id = row['quiz_id']
            else:
                cursor.execute("SELECT quiz_id FROM quiz_questions WHERE question_id = ?", (clean_qid,))
                row2 = cursor.fetchone()
                if row2:
                    clean_quiz_id = row2[0]

        try:
            cursor.execute("DELETE FROM quiz_questions WHERE question_id = ?", (clean_qid,))
        except Exception:
            pass

        cursor.execute("DELETE FROM questions WHERE id = ?", (clean_qid,))
        conn.commit()
        conn.close()

        if clean_quiz_id:
            QuizRepository.recalculate_totals(clean_quiz_id)

        return True
