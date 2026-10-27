import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.question_repository import QuestionRepository
from app.database.repositories.student_repository import StudentRepository

logger = logging.getLogger(__name__)

class AttemptRepository:
    @staticmethod
    def start_or_resume_attempt(quiz_id, student_id):
        clean_quiz_id = str(quiz_id).strip()
        clean_student_id = str(student_id).strip()

        quiz = QuizRepository.get_by_id(clean_quiz_id)
        if not quiz:
            raise ValueError(f"Quiz with ID {clean_quiz_id} not found.")

        if not (quiz.get('is_published') or quiz.get('published')):
            raise ValueError("This quiz has not been published by faculty yet.")

        questions = QuestionRepository.get_by_quiz(clean_quiz_id)
        if len(questions) == 0:
            raise ValueError("This quiz cannot be attempted because no questions have been added yet.")

        supabase = get_supabase_client()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        if supabase:
            try:
                # 1. Check for completed attempt
                comp_res = supabase.table('attempts')\
                    .select('*')\
                    .eq('quiz_id', clean_quiz_id)\
                    .eq('student_id', clean_student_id)\
                    .neq('status', 'in_progress')\
                    .order('created_at', desc=True)\
                    .limit(1)\
                    .execute()
                if comp_res.data and len(comp_res.data) > 0:
                    return comp_res.data[0], True

                # 2. Check for active in-progress attempt
                act_res = supabase.table('attempts')\
                    .select('*')\
                    .eq('quiz_id', clean_quiz_id)\
                    .eq('student_id', clean_student_id)\
                    .eq('status', 'in_progress')\
                    .order('created_at', desc=True)\
                    .limit(1)\
                    .execute()
                if act_res.data and len(act_res.data) > 0:
                    return act_res.data[0], False

                # 3. Create new attempt session with server-calculated end time
                duration_mins = int(quiz.get('duration') or quiz.get('duration_minutes') or 15)
                server_end_dt = now_dt + datetime.timedelta(minutes=duration_mins)
                total_marks = sum(float(q.get('marks', 1.0) or 1.0) for q in questions) or float(quiz.get('total_marks') or len(questions))

                attempt_id = str(uuid.uuid4())
                payload = {
                    'id': attempt_id,
                    'quiz_id': clean_quiz_id,
                    'student_id': clean_student_id,
                    'started_at': now_iso,
                    'server_end_time': server_end_dt.isoformat(),
                    'total_questions': len(questions),
                    'attempted_questions': 0,
                    'correct_answers': 0,
                    'wrong_answers': 0,
                    'unattempted': len(questions),
                    'total_marks': total_marks,
                    'obtained_marks': 0.0,
                    'percentage': 0.0,
                    'status': 'in_progress',
                    'created_at': now_iso
                }
                insert_res = supabase.table('attempts').insert(payload).execute()
                if not insert_res.data or len(insert_res.data) == 0:
                    raise RuntimeError("Failed to create attempt in Supabase.")
                return insert_res.data[0], False
            except Exception as e:
                logger.error("Supabase start_attempt error: %s", e)
                raise RuntimeError(f"Database error starting quiz attempt: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. Check completed
        cursor.execute("""
        SELECT * FROM attempts
        WHERE quiz_id = ? AND student_id = ? AND status != 'in_progress'
        ORDER BY created_at DESC LIMIT 1
        """, (clean_quiz_id, clean_student_id))
        completed = cursor.fetchone()
        if completed:
            conn.close()
            return dict(completed), True

        # 2. Check active
        cursor.execute("""
        SELECT * FROM attempts
        WHERE quiz_id = ? AND student_id = ? AND status = 'in_progress'
        ORDER BY created_at DESC LIMIT 1
        """, (clean_quiz_id, clean_student_id))
        active = cursor.fetchone()
        if active:
            conn.close()
            return dict(active), False

        # 3. Create new
        duration_mins = int(quiz.get('duration') or quiz.get('duration_minutes') or 15)
        server_end_dt = now_dt + datetime.timedelta(minutes=duration_mins)
        total_marks = sum(float(q.get('marks', 1.0) or 1.0) for q in questions) or float(quiz.get('total_marks') or len(questions))
        attempt_id = str(uuid.uuid4())

        cursor.execute("""
        INSERT INTO attempts (
            id, quiz_id, student_id, started_at, server_end_time,
            total_questions, attempted_questions, correct_answers, wrong_answers,
            unattempted, total_marks, obtained_marks, percentage, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            attempt_id, clean_quiz_id, clean_student_id, now_iso, server_end_dt.isoformat(),
            len(questions), 0, 0, 0, len(questions), total_marks, 0.0, 0.0, 'in_progress', now_iso
        ))
        conn.commit()

        cursor.execute("SELECT * FROM attempts WHERE id = ?", (attempt_id,))
        new_row = dict(cursor.fetchone())
        conn.close()
        return new_row, False

    @staticmethod
    def submit_attempt(attempt_id, answers_dict):
        """
        Finalizes an exam attempt:
        - Auto-evaluates candidate choices against authoritative database question keys
        - Stores individual answers in answers table
        - Updates attempts record with PASS/FAIL, percentages, marks, and timestamps
        """
        clean_att_id = str(attempt_id).strip()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        supabase = get_supabase_client()
        attempt = None
        if supabase:
            try:
                res = supabase.table('attempts').select('*').eq('id', clean_att_id).maybe_single().execute()
                attempt = res.data
            except Exception as e:
                logger.error("Supabase fetch attempt error: %s", e)

        if not attempt:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attempts WHERE id = ?", (clean_att_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                attempt = dict(row)

        if not attempt:
            raise ValueError(f"Attempt with ID {clean_att_id} not found.")

        # If already submitted, return details directly
        if attempt.get('status') != 'in_progress':
            return AttemptRepository.get_attempt_details(clean_att_id)

        quiz = QuizRepository.get_by_id(attempt['quiz_id'])
        questions = QuestionRepository.get_by_quiz(attempt['quiz_id'])

        correct_count = 0
        wrong_count = 0
        attempted_count = 0
        obtained_marks = 0.0
        total_marks = sum(float(q.get('marks', 1.0) or 1.0) for q in questions) or float(quiz.get('total_marks') or len(questions))

        answers_to_insert = []
        for q in questions:
            qid = q['id']
            user_choice = answers_dict.get(qid)
            is_correct = False
            marks_awarded = 0.0

            if user_choice:
                user_choice = str(user_choice).strip().upper()
                attempted_count += 1
                if user_choice == str(q['correct_answer']).strip().upper():
                    is_correct = True
                    q_marks = float(q.get('marks', 1.0) or 1.0)
                    marks_awarded = q_marks
                    correct_count += 1
                    obtained_marks += q_marks
                else:
                    wrong_count += 1
            else:
                user_choice = None

            ans_record = {
                'id': str(uuid.uuid4()),
                'attempt_id': clean_att_id,
                'question_id': qid,
                'selected_answer': user_choice,
                'is_correct': is_correct,
                'marks_awarded': marks_awarded,
                'created_at': now_iso
            }
            answers_to_insert.append(ans_record)

        unattempted = len(questions) - attempted_count
        percentage = round((obtained_marks / total_marks) * 100.0, 2) if total_marks > 0 else 0.0
        pass_pct = float(quiz.get('pass_percentage') or quiz.get('passing_percentage') or 40.0)
        status = 'PASS' if percentage >= pass_pct else 'FAIL'

        if supabase:
            try:
                # Delete any existing partial answers
                supabase.table('answers').delete().eq('attempt_id', clean_att_id).execute()
                # Insert evaluated answers
                supabase.table('answers').insert(answers_to_insert).execute()
                # Update attempt record
                supabase.table('attempts').update({
                    'submitted_at': now_iso,
                    'total_questions': len(questions),
                    'attempted_questions': attempted_count,
                    'correct_answers': correct_count,
                    'wrong_answers': wrong_count,
                    'unattempted': unattempted,
                    'total_marks': total_marks,
                    'obtained_marks': obtained_marks,
                    'percentage': percentage,
                    'status': status
                }).eq('id', clean_att_id).execute()
                return AttemptRepository.get_attempt_details(clean_att_id)
            except Exception as e:
                logger.error("Supabase submit_attempt error: %s", e)
                raise RuntimeError(f"Database error recording exam submission: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Clear old answers
        cursor.execute("DELETE FROM answers WHERE attempt_id = ?", (clean_att_id,))
        
        # Insert evaluated answers
        for ans in answers_to_insert:
            cursor.execute("""
            INSERT INTO answers (id, attempt_id, question_id, selected_answer, is_correct, marks_awarded, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ans['id'], ans['attempt_id'], ans['question_id'], ans['selected_answer'], 1 if ans['is_correct'] else 0, ans['marks_awarded'], ans['created_at']))

        # Update attempt
        cursor.execute("""
        UPDATE attempts
        SET submitted_at = ?, total_questions = ?, attempted_questions = ?,
            correct_answers = ?, wrong_answers = ?, unattempted = ?,
            total_marks = ?, obtained_marks = ?, percentage = ?, status = ?
        WHERE id = ?
        """, (now_iso, len(questions), attempted_count, correct_count, wrong_count, unattempted, total_marks, obtained_marks, percentage, status, clean_att_id))
        
        conn.commit()
        conn.close()

        return AttemptRepository.get_attempt_details(clean_att_id)

    @staticmethod
    def get_attempt_details(attempt_id):
        clean_att_id = str(attempt_id).strip()
        supabase = get_supabase_client()
        attempt = None
        answers_list = []

        if supabase:
            try:
                att_res = supabase.table('attempts').select('*').eq('id', clean_att_id).maybe_single().execute()
                attempt = att_res.data
                if attempt:
                    ans_res = supabase.table('answers').select('*').eq('attempt_id', clean_att_id).execute()
                    answers_list = ans_res.data or []
            except Exception as e:
                logger.error("Supabase get_attempt_details error: %s", e)

        if not attempt:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attempts WHERE id = ?", (clean_att_id,))
            row = cursor.fetchone()
            if row:
                attempt = dict(row)
                cursor.execute("SELECT * FROM answers WHERE attempt_id = ?", (clean_att_id,))
                answers_list = [dict(a) for a in cursor.fetchall()]
            conn.close()

        if not attempt:
            return None

        student = StudentRepository.get_by_id(attempt['student_id'])
        quiz = QuizRepository.get_by_id(attempt['quiz_id'])
        questions = QuestionRepository.get_by_quiz(attempt['quiz_id'])

        # Build reviews list
        reviews = []
        for q in questions:
            matched_ans = next((a for a in answers_list if a['question_id'] == q['id']), None)
            user_choice = matched_ans.get('selected_answer') if matched_ans else None
            is_corr = bool(matched_ans.get('is_correct')) if matched_ans else False
            awarded = float(matched_ans.get('marks_awarded', 0.0)) if matched_ans else 0.0

            reviews.append({
                'question_id': q['id'],
                'question_text': q['question_text'],
                'option_a': q['option_a'],
                'option_b': q['option_b'],
                'option_c': q['option_c'],
                'option_d': q['option_d'],
                'selected_answer': user_choice,
                'selected_option': user_choice,
                'correct_answer': q['correct_answer'],
                'is_correct': is_corr,
                'marks_awarded': awarded,
                'max_marks': float(q.get('marks', 1.0) or 1.0),
                'explanation': q.get('explanation')
            })

        attempt_copy = dict(attempt)
        attempt_copy['student'] = student
        attempt_copy['quiz'] = quiz
        attempt_copy['reviews'] = reviews
        attempt_copy['answers'] = reviews
        attempt_copy['correct_count'] = attempt_copy.get('correct_answers', 0)
        attempt_copy['wrong_count'] = attempt_copy.get('wrong_answers', 0)
        attempt_copy['unattempted_count'] = attempt_copy.get('unattempted', 0)
        return attempt_copy

    @staticmethod
    def get_student_attempts(student_id):
        clean_sid = str(student_id).strip()
        supabase = get_supabase_client()
        attempts = []

        if supabase:
            try:
                res = supabase.table('attempts')\
                    .select('*, quizzes(*, subjects(name))')\
                    .eq('student_id', clean_sid)\
                    .order('created_at', desc=True)\
                    .execute()
                for a in (res.data or []):
                    item = dict(a)
                    q = item.get('quizzes')
                    if q:
                        q_copy = dict(q)
                        sub = q_copy.get('subjects')
                        q_copy['subject_name'] = sub.get('name') if sub else (q_copy.get('subject') or 'General Subject')
                        item['quiz'] = q_copy
                    attempts.append(item)
                return attempts
            except Exception as e:
                logger.error("Supabase get_student_attempts error: %s", e)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attempts WHERE student_id = ? ORDER BY created_at DESC", (clean_sid,))
        for r in cursor.fetchall():
            item = dict(r)
            item['quiz'] = QuizRepository.get_by_id(item['quiz_id'])
            attempts.append(item)
        conn.close()
        return attempts

    @staticmethod
    def get_admin_results_table(filters=None):
        filters = filters or {}
        supabase = get_supabase_client()
        rows = []

        if supabase:
            try:
                query = supabase.table('attempts')\
                    .select('*, students(*), quizzes(*, subjects(name))')\
                    .neq('status', 'in_progress')\
                    .order('obtained_marks', desc=True)

                if filters.get('quiz_id') and filters['quiz_id'] != 'ALL':
                    query = query.eq('quiz_id', filters['quiz_id'])

                if filters.get('status') and filters['status'] != 'ALL':
                    query = query.eq('status', filters['status'])

                res = query.execute()

                for att in (res.data or []):
                    s = att.get('students') or {}
                    q = att.get('quizzes') or {}
                    sub = q.get('subjects') or {}

                    rows.append({
                        'id': att['id'],
                        'attemptId': att['id'],
                        'studentId': att['student_id'],
                        'studentName': s.get('full_name') or 'Candidate',
                        'rollNumber': s.get('roll_number') or '-',
                        'division': s.get('division') or '-',
                        'className': s.get('class_name') or '-',
                        'department': s.get('department') or '-',
                        'quizId': att['quiz_id'],
                        'quizTitle': q.get('title') or 'Unit Examination',
                        'subjectName': (
                            sub.get('name')
                            or q.get('subject')
                            or 'General Subject'
                        ),
                        'unitNumber': q.get('unit_number') or 1,
                        'marks': float(att.get('obtained_marks', 0.0)),
                        'totalMarks': float(att.get('total_marks', 0.0)),
                        'percentage': float(att.get('percentage', 0.0)),
                        'correct': int(att.get('correct_answers', 0)),
                        'wrong': int(att.get('wrong_answers', 0)),
                        'unattempted': int(att.get('unattempted', 0)),
                        'status': att['status'],
                        'submittedAt': (
                            att.get('submitted_at')
                            or att.get('created_at')
                        )
                    })

            except Exception as e:
                logger.exception(
                    "Supabase get_admin_results_table error"
                )
                raise RuntimeError(
                    f"Database error loading admin results: {e}"
                )

        else:
            # SQLite is used only when Supabase is unavailable.
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
            SELECT
                a.*,
                s.full_name as student_name,
                s.roll_number,
                s.division,
                s.class_name,
                s.department,
                q.title as quiz_title,
                q.unit_number,
                q.subject as quiz_subject,
                subj.name as sub_name
            FROM attempts a
            JOIN students s ON a.student_id = s.id
            JOIN quizzes q ON a.quiz_id = q.id
            LEFT JOIN subjects subj ON q.subject_id = subj.id
            WHERE a.status != 'in_progress'
            ORDER BY a.obtained_marks DESC, a.percentage DESC
            """)

            for r in cursor.fetchall():
                d = dict(r)

                rows.append({
                    'id': d['id'],
                    'attemptId': d['id'],
                    'studentId': d['student_id'],
                    'studentName': d.get('student_name') or 'Candidate',
                    'rollNumber': d.get('roll_number') or '-',
                    'division': d.get('division') or '-',
                    'className': d.get('class_name') or '-',
                    'department': d.get('department') or '-',
                    'quizId': d['quiz_id'],
                    'quizTitle': d.get('quiz_title') or 'Unit Examination',
                    'subjectName': (
                        d.get('sub_name')
                        or d.get('quiz_subject')
                        or 'General Subject'
                    ),
                    'unitNumber': d.get('unit_number') or 1,
                    'marks': float(d.get('obtained_marks', 0.0)),
                    'totalMarks': float(d.get('total_marks', 0.0)),
                    'percentage': float(d.get('percentage', 0.0)),
                    'correct': int(d.get('correct_answers', 0)),
                    'wrong': int(d.get('wrong_answers', 0)),
                    'unattempted': int(d.get('unattempted', 0)),
                    'status': d['status'],
                    'submittedAt': (
                        d.get('submitted_at')
                        or d.get('created_at')
                    )
                })

            conn.close()

        # Apply in-memory filtering
        if filters.get('search'):
            q_str = str(filters['search']).lower().strip()
            rows = [
                r for r in rows
                if q_str in r['studentName'].lower()
                or q_str in r['rollNumber'].lower()
                or q_str in r['quizTitle'].lower()
            ]

        if filters.get('division') and filters['division'] != 'ALL':
            div_val = str(filters['division']).upper().strip()
            rows = [
                r for r in rows
                if r['division'].upper() == div_val
            ]

        if filters.get('unitNumber') and int(filters['unitNumber']) > 0:
            u_num = int(filters['unitNumber'])
            rows = [
                r for r in rows
                if r['unitNumber'] == u_num
            ]

        if filters.get('quiz_id') and filters['quiz_id'] != 'ALL':
            q_val = str(filters['quiz_id']).strip()
            rows = [
                r for r in rows
                if str(r['quizId']) == q_val
            ]

        if filters.get('class_name') and filters['class_name'] != 'ALL':
            c_val = str(filters['class_name']).strip().lower()
            rows = [
                r for r in rows
                if r['className'].strip().lower() == c_val
            ]

        if filters.get('status') and filters['status'] != 'ALL':
            st_val = str(filters['status']).strip().upper()
            rows = [
                r for r in rows
                if r['status'].upper() == st_val
            ]

        rows.sort(
            key=lambda x: (x['marks'], x['percentage']),
            reverse=True
        )

        ranked_rows = []
        cur_rank = 1

        for idx, row in enumerate(rows):
            if idx > 0 and row['marks'] < rows[idx - 1]['marks']:
                cur_rank = idx + 1

            row_copy = dict(row)
            row_copy['rank'] = cur_rank
            ranked_rows.append(row_copy)

        return ranked_rows

    @staticmethod
    def get_admin_dashboard_stats(unit_filter=None):
        unit_filter = int(unit_filter) if unit_filter and int(unit_filter) > 0 else 0
        all_quizzes = QuizRepository.get_all()
        all_students = StudentRepository.get_all()
        
        filtered_results = AttemptRepository.get_admin_results_table(
            {'unitNumber': unit_filter} if unit_filter > 0 else None
        )

        total_students = len(all_students)
        relevant_quizzes = [q for q in all_quizzes if q.get('unit_number') == unit_filter] if unit_filter > 0 else all_quizzes
        total_quizzes = len(relevant_quizzes)
        total_attempts = len(filtered_results)

        avg_score = 0.0
        high_score = 0.0
        low_score = 0.0
        pass_count = 0
        fail_count = 0
        total_correct = 0
        total_wrong = 0
        total_unattempted = 0

        distribution = {
            '0-20%': 0,
            '21-40%': 0,
            '41-60%': 0,
            '61-80%': 0,
            '81-100%': 0
        }

        if total_attempts > 0:
            sum_pct = sum(r['percentage'] for r in filtered_results)
            avg_score = round(sum_pct / total_attempts, 1)
            high_score = max(r['marks'] for r in filtered_results)
            low_score = min(r['marks'] for r in filtered_results)

            for r in filtered_results:
                if r['status'] == 'PASS':
                    pass_count += 1
                else:
                    fail_count += 1
                
                total_correct += r['correct']
                total_wrong += r['wrong']
                total_unattempted += r['unattempted']

                pct = r['percentage']
                if pct <= 20: distribution['0-20%'] += 1
                elif pct <= 40: distribution['21-40%'] += 1
                elif pct <= 60: distribution['41-60%'] += 1
                elif pct <= 80: distribution['61-80%'] += 1
                else: distribution['81-100%'] += 1

        pass_percentage = round((pass_count / total_attempts) * 100.0, 1) if total_attempts > 0 else 0.0
        fail_percentage = round((fail_count / total_attempts) * 100.0, 1) if total_attempts > 0 else 0.0

        # Division-wise performance breakdown
        division_performance = {}
        for r in filtered_results:
            div = (r.get('division') or 'Unknown').strip().upper()
            if div not in division_performance:
                division_performance[div] = {'attempts': 0, 'sum_pct': 0.0, 'pass_count': 0}
            division_performance[div]['attempts'] += 1
            division_performance[div]['sum_pct'] += r['percentage']
            if r['status'] == 'PASS':
                division_performance[div]['pass_count'] += 1

        division_stats = []
        for div_name in sorted(division_performance.keys()):
            d_data = division_performance[div_name]
            d_count = d_data['attempts']
            d_avg = round(d_data['sum_pct'] / d_count, 1) if d_count > 0 else 0.0
            d_pass_rate = round((d_data['pass_count'] / d_count) * 100.0, 1) if d_count > 0 else 0.0
            division_stats.append({
                'division': div_name,
                'attempts': d_count,
                'averagePercentage': d_avg,
                'passPercentage': d_pass_rate
            })

        # Quiz-wise performance breakdown
        quiz_performance = {}
        for r in filtered_results:
            q_id = r.get('quizId')
            q_title = r.get('quizTitle') or 'Unit Quiz'
            if q_id not in quiz_performance:
                quiz_performance[q_id] = {'title': q_title, 'attempts': 0, 'sum_marks': 0.0, 'sum_pct': 0.0}
            quiz_performance[q_id]['attempts'] += 1
            quiz_performance[q_id]['sum_marks'] += r['marks']
            quiz_performance[q_id]['sum_pct'] += r['percentage']

        quiz_stats = []
        for q_id, q_data in quiz_performance.items():
            q_count = q_data['attempts']
            quiz_stats.append({
                'quizId': q_id,
                'title': q_data['title'],
                'attempts': q_count,
                'averageMarks': round(q_data['sum_marks'] / q_count, 1) if q_count > 0 else 0.0,
                'averagePercentage': round(q_data['sum_pct'] / q_count, 1) if q_count > 0 else 0.0
            })

        # Unit comparison across units 1, 2, 3, 4
        unit_comparison = []
        for u in (1, 2, 3, 4):
            u_results = [r for r in filtered_results if r['unitNumber'] == u] if unit_filter == 0 else (filtered_results if unit_filter == u else [])
            u_quizzes = [q for q in all_quizzes if q.get('unit_number') == u]
            u_title = u_quizzes[0].get('unit_title') if u_quizzes else f"Unit {u}"
            u_max_marks = float(u_quizzes[0].get('total_marks', 15.0)) if u_quizzes else 15.0

            u_avg_marks = round(sum(r['marks'] for r in u_results) / len(u_results), 1) if u_results else 0.0
            u_avg_pct = round(sum(r['percentage'] for r in u_results) / len(u_results), 1) if u_results else 0.0

            unit_comparison.append({
                'unit': f"Unit {u}",
                'unit_title': u_title,
                'averageMarks': u_avg_marks,
                'maxMarks': u_max_marks,
                'averagePercentage': u_avg_pct,
                'attemptsCount': len(u_results)
            })

        return {
            'totalStudents': total_students,
            'total_students': total_students,
            'totalQuizzes': total_quizzes,
            'total_quizzes': total_quizzes,
            'totalAttempts': total_attempts,
            'total_attempts': total_attempts,
            'averageClassScore': avg_score,
            'average_score': avg_score,
            'average_percentage': avg_score,
            'highestScore': high_score,
            'highest_score': high_score,
            'lowestScore': low_score,
            'lowest_score': low_score,
            'passPercentage': pass_percentage,
            'pass_percentage': pass_percentage,
            'failPercentage': fail_percentage,
            'fail_percentage': fail_percentage,
            'passed_count': pass_count,
            'failed_count': fail_count,
            'total_correct': total_correct,
            'total_wrong': total_wrong,
            'total_unattempted': total_unattempted,
            'divisionStats': division_stats,
            'quizStats': quiz_stats,
            'scoreDistribution': [
                {'range': '0–20%', 'count': distribution['0-20%']},
                {'range': '21–40%', 'count': distribution['21-40%']},
                {'range': '41–60%', 'count': distribution['41-60%']},
                {'range': '61–80%', 'count': distribution['61-80%']},
                {'range': '81–100%', 'count': distribution['81-100%']}
            ],
            'passFailData': [
                {'name': 'Passed', 'value': pass_count, 'color': '#16a34a'},
                {'name': 'Failed', 'value': fail_count, 'color': '#dc2626'}
            ],
            'correctWrongData': [
                {'name': 'Correct', 'value': total_correct, 'color': '#2563eb'},
                {'name': 'Wrong', 'value': total_wrong, 'color': '#ef4444'},
                {'name': 'Unattempted', 'value': total_unattempted, 'color': '#94a3b8'}
            ],
            'unitComparison': unit_comparison
        }

    @staticmethod
    def get_overall_rankings(subject_id=None):
        results = AttemptRepository.get_admin_results_table()
        students = StudentRepository.get_all()

        student_scores = {}
        for r in results:
            sid = r['studentId']
            if sid not in student_scores:
                student_scores[sid] = {
                    'student_id': sid,
                    'student_name': r['studentName'],
                    'roll_number': r['rollNumber'],
                    'division': r['division'],
                    'class_name': r['className'],
                    'department': r['department'],
                    'unit1_marks': 0.0,
                    'unit2_marks': 0.0,
                    'unit3_marks': 0.0,
                    'unit4_marks': 0.0,
                    'total_marks': 0.0,
                    'completed_units': set()
                }
            u = r['unitNumber']
            m = r['marks']
            if u == 1: student_scores[sid]['unit1_marks'] = max(student_scores[sid]['unit1_marks'], m)
            elif u == 2: student_scores[sid]['unit2_marks'] = max(student_scores[sid]['unit2_marks'], m)
            elif u == 3: student_scores[sid]['unit3_marks'] = max(student_scores[sid]['unit3_marks'], m)
            elif u == 4: student_scores[sid]['unit4_marks'] = max(student_scores[sid]['unit4_marks'], m)
            student_scores[sid]['completed_units'].add(u)

        leaderboard = []
        for s in student_scores.values():
            tot = s['unit1_marks'] + s['unit2_marks'] + s['unit3_marks'] + s['unit4_marks']
            pct = round((tot / 60.0) * 100.0, 2)
            status = 'Pass' if pct >= 40.0 else ('Incomplete' if len(s['completed_units']) < 4 else 'Fail')
            leaderboard.append({
                'student_id': s['student_id'],
                'student_name': s['student_name'],
                'roll_number': s['roll_number'],
                'division': s['division'],
                'class_name': s['class_name'],
                'department': s['department'],
                'unit1_marks': s['unit1_marks'],
                'unit2_marks': s['unit2_marks'],
                'unit3_marks': s['unit3_marks'],
                'unit4_marks': s['unit4_marks'],
                'total_marks': tot,
                'percentage': pct,
                'overall_status': status
            })

        leaderboard.sort(key=lambda x: x['total_marks'], reverse=True)
        cur_rank = 1
        for idx, item in enumerate(leaderboard):
            if idx > 0 and item['total_marks'] < leaderboard[idx - 1]['total_marks']:
                cur_rank = idx + 1
            item['rank'] = cur_rank

        return leaderboard

    @staticmethod
    def get_unit_rankings(quiz_id):
        results = AttemptRepository.get_admin_results_table({'quiz_id': quiz_id})
        return results
