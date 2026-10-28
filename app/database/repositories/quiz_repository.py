import uuid
import datetime
import logging
from app.database.supabase_client import get_supabase_client, get_db_connection
from app.database.repositories.subject_repository import SubjectRepository

logger = logging.getLogger(__name__)

class QuizRepository:
    @staticmethod
    def _normalize_quiz(q_dict):
        """Ensures all field aliases are available across both SQLite and Supabase schemas."""
        if not q_dict:
            return None
        d = dict(q_dict)
        dur = d.get('duration') if d.get('duration') is not None else d.get('duration_minutes')
        if dur is None:
            dur = 15
        d['duration'] = int(dur)
        d['duration_minutes'] = int(dur)

        cnt = d.get('question_count') if d.get('question_count') is not None else (d.get('total_questions') or 0)
        d['question_count'] = int(cnt)
        d['total_questions'] = int(cnt)

        passing = d.get('pass_percentage') if d.get('pass_percentage') is not None else d.get('passing_percentage')
        if passing is None:
            passing = 40.0
        d['passing_percentage'] = float(passing)
        d['pass_percentage'] = float(passing)

        is_pub = bool(d.get('is_published') or d.get('published'))
        d['is_published'] = is_pub
        d['published'] = is_pub
        d['randomize_questions'] = bool(d.get('randomize_questions'))
        d['randomize_options'] = bool(d.get('randomize_options'))

        sub = d.get('subjects')
        if isinstance(sub, dict):
            d['subject_name'] = sub.get('name') or d.get('subject') or 'General Subject'
        elif sub:
            d['subject_name'] = str(sub)
        else:
            d['subject_name'] = d.get('sub_name') or d.get('subject') or 'General Subject'
        d['subject'] = d['subject_name']

        return d

    @staticmethod
    def get_all(subject_id=None):
        supabase = get_supabase_client()
        if supabase:
            try:
                try:
                    query = supabase.table('quizzes').select('*, subjects(name)')
                    if subject_id:
                        query = query.eq('subject_id', str(subject_id).strip())
                    res = query.order('created_at', desc=True).execute()
                    rows = (res.data if res is not None and getattr(res, 'data', None) else []) or []
                except Exception as join_err:
                    logger.warning("Supabase quizzes join with subjects failed, falling back to select('*'): %s", join_err)
                    query = supabase.table('quizzes').select('*')
                    if subject_id:
                        query = query.eq('subject_id', str(subject_id).strip())
                    res = query.order('created_at', desc=True).execute()
                    rows = (res.data if res is not None and getattr(res, 'data', None) else []) or []

                # Build subject name lookup if any quiz is missing joined subject name
                sub_map = {}
                for q in rows:
                    if not q.get('subjects') and q.get('subject_id'):
                        if not sub_map:
                            try:
                                for s in SubjectRepository.get_all():
                                    sub_map[s['id']] = s.get('name')
                            except Exception:
                                pass
                        if q.get('subject_id') in sub_map:
                            q['sub_name'] = sub_map[q['subject_id']]

                result = []
                for q in rows:
                    q_norm = QuizRepository._normalize_quiz(q)
                    # Fetch live question count from quiz_questions table (authoritative in Supabase schema)
                    try:
                        q_res = supabase.table('quiz_questions').select('id', count='exact', head=True).eq('quiz_id', q_norm['id']).execute()
                        if q_res is not None and getattr(q_res, 'count', None) is not None:
                            q_norm['question_count'] = q_res.count
                            q_norm['total_questions'] = q_res.count
                    except Exception as count_err:
                        try:
                            q_res = supabase.table('questions').select('id', count='exact', head=True).eq('quiz_id', q_norm['id']).execute()
                            if q_res is not None and getattr(q_res, 'count', None) is not None:
                                q_norm['question_count'] = q_res.count
                                q_norm['total_questions'] = q_res.count
                        except Exception:
                            logger.debug("Count lookup on quiz_questions failed, using quiz row count: %s", count_err)
                    
                    result.append(q_norm)
                return result
            except Exception as e:
                logger.error("Supabase get_all quizzes error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='quiz_questions'")
        has_qq = cursor.fetchone()[0] > 0
        
        if has_qq:
            sql = """
            SELECT q.*, s.name as sub_name,
                   (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id = q.id) as q_count,
                   (SELECT COALESCE(SUM(ques.marks), 0) FROM questions ques JOIN quiz_questions qq ON ques.id = qq.question_id WHERE qq.quiz_id = q.id) as calc_marks
            FROM quizzes q
            LEFT JOIN subjects s ON q.subject_id = s.id
            """
        else:
            sql = """
            SELECT q.*, s.name as sub_name,
                   (SELECT COUNT(*) FROM questions ques WHERE ques.quiz_id = q.id) as q_count,
                   (SELECT COALESCE(SUM(ques.marks), 0) FROM questions ques WHERE ques.quiz_id = q.id) as calc_marks
            FROM quizzes q
            LEFT JOIN subjects s ON q.subject_id = s.id
            """
        params = []
        if subject_id:
            sql += " WHERE q.subject_id = ?"
            params.append(str(subject_id).strip())
        sql += " ORDER BY q.created_at DESC"
        
        cursor.execute(sql, params)
        rows = []
        for r in cursor.fetchall():
            d = dict(r)
            if d.get('q_count') is not None:
                d['question_count'] = d['q_count']
                d['total_questions'] = d['q_count']
            if d.get('calc_marks', 0) > 0:
                d['total_marks'] = d['calc_marks']
            rows.append(QuizRepository._normalize_quiz(d))
        conn.close()
        return rows

    @staticmethod
    def get_published(subject_id=None):
        all_quizzes = QuizRepository.get_all(subject_id)
        return [q for q in all_quizzes if q.get('is_published') or q.get('published')]

    @staticmethod
    def get_by_id(quiz_id):
        if not quiz_id:
            return None
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                try:
                    res = supabase.table('quizzes').select('*, subjects(name)').eq('id', clean_id).maybe_single().execute()
                except Exception as join_err:
                    logger.warning("Supabase quiz get_by_id join failed, falling back to select('*'): %s", join_err)
                    res = supabase.table('quizzes').select('*').eq('id', clean_id).maybe_single().execute()

                if not res or not getattr(res, 'data', None):
                    return None
                q_norm = QuizRepository._normalize_quiz(res.data)
                if q_norm.get('subject_name') == 'General Subject' and q_norm.get('subject_id'):
                    sub_row = SubjectRepository.get_by_id(q_norm['subject_id'])
                    if sub_row and sub_row.get('name'):
                        q_norm['subject_name'] = sub_row['name']
                        q_norm['subject'] = sub_row['name']

                try:
                    q_res = supabase.table('quiz_questions').select('id', count='exact', head=True).eq('quiz_id', clean_id).execute()
                    if q_res is not None and getattr(q_res, 'count', None) is not None:
                        q_norm['question_count'] = q_res.count
                        q_norm['total_questions'] = q_res.count
                except Exception as count_err:
                    try:
                        q_res = supabase.table('questions').select('id', count='exact', head=True).eq('quiz_id', clean_id).execute()
                        if q_res is not None and getattr(q_res, 'count', None) is not None:
                            q_norm['question_count'] = q_res.count
                            q_norm['total_questions'] = q_res.count
                    except Exception:
                        logger.debug("Count lookup on quiz_questions failed: %s", count_err)
                return q_norm
            except Exception as e:
                logger.error("Supabase get quiz by id error: %s", e)
                raise

        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='quiz_questions'")
        has_qq = cursor.fetchone()[0] > 0
        
        if has_qq:
            sql = """
            SELECT q.*, s.name as sub_name,
                   (SELECT COUNT(*) FROM quiz_questions qq WHERE qq.quiz_id = q.id) as q_count,
                   (SELECT COALESCE(SUM(ques.marks), 0) FROM questions ques JOIN quiz_questions qq ON ques.id = qq.question_id WHERE qq.quiz_id = q.id) as calc_marks
            FROM quizzes q
            LEFT JOIN subjects s ON q.subject_id = s.id
            WHERE q.id = ?
            """
        else:
            sql = """
            SELECT q.*, s.name as sub_name,
                   (SELECT COUNT(*) FROM questions ques WHERE ques.quiz_id = q.id) as q_count,
                   (SELECT COALESCE(SUM(ques.marks), 0) FROM questions ques WHERE ques.quiz_id = q.id) as calc_marks
            FROM quizzes q
            LEFT JOIN subjects s ON q.subject_id = s.id
            WHERE q.id = ?
            """
        cursor.execute(sql, (clean_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        if d.get('q_count') is not None:
            d['question_count'] = d['q_count']
            d['total_questions'] = d['q_count']
        if d.get('calc_marks', 0) > 0:
            d['total_marks'] = d['calc_marks']
        return QuizRepository._normalize_quiz(d)

    @staticmethod
    def _insert_supabase_quiz(supabase, base_payload, is_pub, rand_q, rand_opt):
        """
        Attempts to insert into Supabase quizzes table, adapting boolean/integer
        flag columns (published, randomize_questions, randomize_options) to match
        the PostgreSQL column definitions (whether INTEGER or BOOLEAN).
        """
        flag_variations = [
            # Var 1: Integer flags (0/1) - primary for production schema where False caused 22P02
            {
                'published': 1 if is_pub else 0,
                'randomize_questions': 1 if rand_q else 0,
                'randomize_options': 1 if rand_opt else 0
            },
            # Var 2: Published boolean, randomize integer
            {
                'published': is_pub,
                'randomize_questions': 1 if rand_q else 0,
                'randomize_options': 1 if rand_opt else 0
            },
            # Var 3: Published integer, randomize boolean
            {
                'published': 1 if is_pub else 0,
                'randomize_questions': rand_q,
                'randomize_options': rand_opt
            },
            # Var 4: All boolean flags
            {
                'published': is_pub,
                'randomize_questions': rand_q,
                'randomize_options': rand_opt
            }
        ]

        last_error = None
        for flags in flag_variations:
            payload = dict(base_payload)
            payload.update(flags)
            try:
                res = supabase.table('quizzes').insert(payload).execute()
                if not res or not getattr(res, 'data', None) or len(res.data) == 0:
                    raise RuntimeError("Supabase returned empty response upon quiz creation")
                return res.data[0]
            except Exception as e:
                err_str = str(e).lower()
                last_error = e
                # Check for 22P02 (invalid input syntax for type integer: "false") or 42804 (boolean/integer mismatch)
                if any(k in err_str for k in ('invalid input syntax for type integer', 'type boolean', '22p02', '42804')):
                    logger.warning("Quiz insertion flag type attempt failed (%s), trying alternate flag types...", e)
                    continue
                # For non-type errors (e.g. constraints or network), re-raise immediately
                raise

        logger.error("Supabase create_quiz error after all flag type variations: %s", last_error)
        raise RuntimeError(f"Database error creating quiz: {last_error}")

    @staticmethod
    def _update_supabase_quiz(supabase, clean_id, base_update, has_pub=False, pub_val=False, has_rand_q=False, rand_q_val=False, has_rand_opt=False, rand_opt_val=False):
        """
        Attempts to update Supabase quizzes table, adapting boolean/integer
        flag columns to match the PostgreSQL column definitions (whether INTEGER or BOOLEAN).
        """
        flag_variations = [
            # Var 1: Integer flags
            {
                **({'published': 1 if pub_val else 0} if has_pub else {}),
                **({'randomize_questions': 1 if rand_q_val else 0} if has_rand_q else {}),
                **({'randomize_options': 1 if rand_opt_val else 0} if has_rand_opt else {})
            },
            # Var 2: Published boolean, randomize integer
            {
                **({'published': pub_val} if has_pub else {}),
                **({'randomize_questions': 1 if rand_q_val else 0} if has_rand_q else {}),
                **({'randomize_options': 1 if rand_opt_val else 0} if has_rand_opt else {})
            },
            # Var 3: Published integer, randomize boolean
            {
                **({'published': 1 if pub_val else 0} if has_pub else {}),
                **({'randomize_questions': rand_q_val} if has_rand_q else {}),
                **({'randomize_options': rand_opt_val} if has_rand_opt else {})
            },
            # Var 4: All boolean
            {
                **({'published': pub_val} if has_pub else {}),
                **({'randomize_questions': rand_q_val} if has_rand_q else {}),
                **({'randomize_options': rand_opt_val} if has_rand_opt else {})
            }
        ]

        last_error = None
        for flags in flag_variations:
            update_fields = dict(base_update)
            update_fields.update(flags)
            try:
                res = supabase.table('quizzes').update(update_fields).eq('id', clean_id).execute()
                if not res or not getattr(res, 'data', None) or len(res.data) == 0:
                    raise RuntimeError(f"Quiz with ID {clean_id} not found in Supabase")
                return res.data[0]
            except Exception as e:
                err_str = str(e).lower()
                last_error = e
                if any(k in err_str for k in ('invalid input syntax for type integer', 'type boolean', '22p02', '42804')):
                    logger.warning("Quiz update flag type attempt failed (%s), trying alternate flag types...", e)
                    continue
                raise

        logger.error("Supabase update_quiz error: %s", last_error)
        raise RuntimeError(f"Failed to update quiz in database: {last_error}")

    @staticmethod
    def create_quiz(data):
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        quiz_id = str(uuid.uuid4())
        
        # 1. Resolve and validate foreign key subject_id
        subject_id = str(data.get('subject_id') or '').strip()
        if not subject_id or len(subject_id) < 10:
            all_subs = SubjectRepository.get_all()
            if all_subs:
                subject_id = str(all_subs[0]['id'])
                data['subject_name'] = all_subs[0]['name']
            else:
                new_sub = SubjectRepository.get_or_create(
                    code='CS301',
                    name='Data Structures & Algorithms',
                    department=data.get('department', 'Computer Engineering'),
                    class_name=data.get('class_name', 'TE Computer')
                )
                subject_id = str(new_sub['id'])
                data['subject_name'] = new_sub['name']
        else:
            # Check whether subject_id exists in active database
            existing_sub = SubjectRepository.get_by_id(subject_id)
            if not existing_sub:
                all_subs = SubjectRepository.get_all()
                if all_subs:
                    subject_id = str(all_subs[0]['id'])
                    data['subject_name'] = all_subs[0]['name']
                else:
                    new_sub = SubjectRepository.get_or_create(
                        code='CS301',
                        name='Data Structures & Algorithms',
                        department=data.get('department', 'Computer Engineering'),
                        class_name=data.get('class_name', 'TE Computer')
                    )
                    subject_id = str(new_sub['id'])
                    data['subject_name'] = new_sub['name']
            else:
                if not data.get('subject_name'):
                    data['subject_name'] = existing_sub.get('name')

        # 2. Clamped unit number for institutional 4-unit curriculum
        try:
            unit_num = max(1, min(4, int(data.get('unit_number', 1) or 1)))
        except (ValueError, TypeError):
            unit_num = 1

        is_pub = bool(data.get('is_published') if 'is_published' in data else data.get('published', False))
        duration_val = int(data.get('duration_minutes') or data.get('duration') or 15)
        total_marks_val = float(data.get('total_marks', 0.0) or 0.0)
        total_marks_clean = int(round(total_marks_val)) if total_marks_val.is_integer() else total_marks_val
        pass_pct_val = float(data.get('passing_percentage') or data.get('pass_percentage') or 40.0)
        pass_pct_clean = int(round(pass_pct_val)) if pass_pct_val.is_integer() else pass_pct_val
        rand_q = bool(data.get('randomize_questions', False))
        rand_opt = bool(data.get('randomize_options', False))

        supabase = get_supabase_client()
        if supabase:
            # 3. Check for unique_subject_unit constraint in Supabase
            try:
                exist_res = supabase.table('quizzes')\
                    .select('id, title, published, total_questions')\
                    .eq('subject_id', subject_id)\
                    .eq('unit_number', unit_num)\
                    .maybe_single()\
                    .execute()
                
                if exist_res and getattr(exist_res, 'data', None):
                    ex_quiz = exist_res.data
                    # If existing quiz has 0 questions and is not published, reuse and update it
                    q_cnt = ex_quiz.get('total_questions') or ex_quiz.get('question_count') or 0
                    is_published_status = bool(ex_quiz.get('published') or ex_quiz.get('is_published'))
                    if q_cnt == 0 and not is_published_status:
                        logger.info("Reusing unconfigured draft quiz %s for subject %s unit %s", ex_quiz['id'], subject_id, unit_num)
                        upd_base = {
                            'title': str(data['title']).strip(),
                            'description': str(data.get('description', '') or '').strip() or None,
                            'unit_title': str(data.get('unit_title', '') or '').strip() or f"Unit {unit_num}",
                            'class_name': str(data.get('class_name', 'TE Computer')).strip(),
                            'division': str(data.get('division', 'All')).strip(),
                            'department': str(data.get('department', 'Computer Engineering')).strip(),
                            'duration': duration_val,
                            'total_marks': total_marks_clean,
                            'pass_percentage': pass_pct_clean,
                            'updated_at': now
                        }
                        QuizRepository._update_supabase_quiz(
                            supabase,
                            ex_quiz['id'],
                            upd_base,
                            has_pub=False,
                            pub_val=False,
                            has_rand_q=True,
                            rand_q_val=rand_q,
                            has_rand_opt=True,
                            rand_opt_val=rand_opt
                        )
                        return QuizRepository.get_by_id(ex_quiz['id'])
                    else:
                        raise ValueError(f"A quiz for this subject and Unit {unit_num} already exists ('{ex_quiz.get('title')}'). Please choose another unit or edit the existing quiz.")
            except ValueError:
                raise
            except Exception as chk_err:
                logger.warning("Could not pre-check existing quiz in Supabase: %s", chk_err)

            # 4. Insert exact fields matching Supabase PostgreSQL schema
            # Real production columns: id, subject_id, subject, unit_number, unit_title, title,
            # description, class_name, division, department, duration, total_questions,
            # marks_per_question, total_marks, pass_percentage, status, published,
            # randomize_questions, randomize_options, created_at, updated_at
            supabase_payload = {
                'id': quiz_id,
                'subject_id': subject_id,
                'subject': str(data.get('subject_name') or '').strip() or None,
                'unit_number': unit_num,
                'unit_title': str(data.get('unit_title', '') or '').strip() or f"Unit {unit_num}",
                'title': str(data['title']).strip(),
                'description': str(data.get('description', '') or '').strip() or None,
                'class_name': str(data.get('class_name', 'TE Computer')).strip(),
                'division': str(data.get('division', 'All')).strip(),
                'department': str(data.get('department', 'Computer Engineering')).strip(),
                'duration': duration_val,
                'total_questions': 0,
                'marks_per_question': float(data.get('marks_per_question', 1.0) or 1.0),
                'total_marks': total_marks_clean,
                'pass_percentage': pass_pct_clean,
                'status': 'published' if is_pub else 'draft',
                'created_at': now,
                'updated_at': now
            }

            # Optional faculty creator UUID if valid
            raw_cb = str(data.get('created_by') or '').strip()
            if raw_cb and len(raw_cb) >= 32:
                try:
                    uuid.UUID(raw_cb)
                    supabase_payload['created_by'] = raw_cb
                except ValueError:
                    pass

            created_row = QuizRepository._insert_supabase_quiz(supabase, supabase_payload, is_pub, rand_q, rand_opt)
            created = QuizRepository._normalize_quiz(created_row)
            created['is_published'] = is_pub
            created['published'] = is_pub
            created['randomize_questions'] = rand_q
            created['randomize_options'] = rand_opt
            created['question_count'] = 0
            created['total_questions'] = 0
            return created

        # Local SQLite fallback
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if table has duration_minutes or duration
        cursor.execute("PRAGMA table_info(quizzes)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        insert_cols = ['id', 'title', 'description', 'subject_id', 'subject', 'unit_number', 'unit_title',
                       'class_name', 'division', 'department', 'total_marks', 'created_at', 'updated_at']
        insert_vals = [quiz_id, str(data['title']).strip(), str(data.get('description', '') or '').strip() or None,
                       subject_id, str(data.get('subject_name') or 'General Subject').strip(), unit_num,
                       str(data.get('unit_title', '') or '').strip() or f"Unit {unit_num}",
                       str(data.get('class_name', 'TE Computer')).strip(), str(data.get('division', 'All')).strip(),
                       str(data.get('department', 'Computer Engineering')).strip(), total_marks_val, now, now]
        
        if 'duration' in columns:
            insert_cols.append('duration')
            insert_vals.append(duration_val)
        if 'duration_minutes' in columns:
            insert_cols.append('duration_minutes')
            insert_vals.append(duration_val)
        if 'total_questions' in columns:
            insert_cols.append('total_questions')
            insert_vals.append(0)
        if 'question_count' in columns:
            insert_cols.append('question_count')
            insert_vals.append(0)
        if 'marks_per_question' in columns:
            insert_cols.append('marks_per_question')
            insert_vals.append(float(data.get('marks_per_question', 1.0) or 1.0))
        if 'pass_percentage' in columns:
            insert_cols.append('pass_percentage')
            insert_vals.append(pass_pct_val)
        if 'passing_percentage' in columns:
            insert_cols.append('passing_percentage')
            insert_vals.append(pass_pct_val)
        if 'created_by' in columns:
            valid_created_by = None
            if data.get('created_by'):
                cursor.execute("SELECT id FROM faculty WHERE id = ?", (str(data.get('created_by')),))
                if cursor.fetchone():
                    valid_created_by = str(data.get('created_by'))
            insert_cols.append('created_by')
            insert_vals.append(valid_created_by)
        if 'status' in columns:
            insert_cols.append('status')
            insert_vals.append('published' if is_pub else 'draft')
        if 'published' in columns:
            insert_cols.append('published')
            insert_vals.append(1 if is_pub else 0)
        if 'is_published' in columns:
            insert_cols.append('is_published')
            insert_vals.append(1 if is_pub else 0)
        if 'randomize_questions' in columns:
            insert_cols.append('randomize_questions')
            insert_vals.append(1 if rand_q else 0)
        if 'randomize_options' in columns:
            insert_cols.append('randomize_options')
            insert_vals.append(1 if rand_opt else 0)

        placeholders = ', '.join(['?'] * len(insert_vals))
        col_string = ', '.join(insert_cols)
        cursor.execute(f"INSERT INTO quizzes ({col_string}) VALUES ({placeholders})", insert_vals)
        conn.commit()
        conn.close()
        
        return QuizRepository.get_by_id(quiz_id)

    @staticmethod
    def update_quiz(quiz_id, data):
        clean_id = str(quiz_id).strip()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        supabase = get_supabase_client()
        if supabase:
            base_update = {'updated_at': now}
            if 'title' in data: base_update['title'] = str(data['title']).strip()
            if 'description' in data: base_update['description'] = str(data['description']).strip()
            if 'unit_number' in data:
                try:
                    base_update['unit_number'] = max(1, min(4, int(data['unit_number'])))
                except (ValueError, TypeError):
                    pass
            if 'unit_title' in data: base_update['unit_title'] = str(data['unit_title']).strip()
            if 'duration' in data or 'duration_minutes' in data:
                dur = int(data.get('duration') if 'duration' in data else data.get('duration_minutes'))
                base_update['duration'] = dur
            if 'pass_percentage' in data or 'passing_percentage' in data:
                pct = float(data.get('pass_percentage') if 'pass_percentage' in data else data.get('passing_percentage'))
                base_update['pass_percentage'] = int(round(pct)) if pct.is_integer() else pct
            if 'total_marks' in data:
                tm = float(data['total_marks'])
                base_update['total_marks'] = int(round(tm)) if tm.is_integer() else tm
            if 'marks_per_question' in data:
                base_update['marks_per_question'] = float(data['marks_per_question'])

            has_pub = 'published' in data or 'is_published' in data
            has_rand_q = 'randomize_questions' in data
            has_rand_opt = 'randomize_options' in data

            pub_val = bool(data.get('published') if 'published' in data else data.get('is_published')) if has_pub else False
            rand_q_val = bool(data['randomize_questions']) if has_rand_q else False
            rand_opt_val = bool(data['randomize_options']) if has_rand_opt else False

            if has_pub:
                base_update['status'] = 'published' if pub_val else 'draft'

            QuizRepository._update_supabase_quiz(
                supabase, clean_id, base_update,
                has_pub=has_pub, pub_val=pub_val,
                has_rand_q=has_rand_q, rand_q_val=rand_q_val,
                has_rand_opt=has_rand_opt, rand_opt_val=rand_opt_val
            )
            return QuizRepository.get_by_id(clean_id)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(quizzes)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        set_clauses = ["updated_at = ?"]
        params = [now]
        if 'title' in data:
            set_clauses.append("title = ?")
            params.append(str(data['title']).strip())
        if 'description' in data:
            set_clauses.append("description = ?")
            params.append(str(data['description']).strip())
        if 'unit_number' in data:
            set_clauses.append("unit_number = ?")
            params.append(max(1, min(4, int(data['unit_number']))))
        if 'unit_title' in data:
            set_clauses.append("unit_title = ?")
            params.append(str(data['unit_title']).strip())
        if 'duration' in data or 'duration_minutes' in data:
            dur = int(data.get('duration_minutes') or data.get('duration'))
            if 'duration' in columns:
                set_clauses.append("duration = ?")
                params.append(dur)
            if 'duration_minutes' in columns:
                set_clauses.append("duration_minutes = ?")
                params.append(dur)
        if 'pass_percentage' in data or 'passing_percentage' in data:
            pct = float(data.get('passing_percentage') or data.get('pass_percentage'))
            if 'pass_percentage' in columns:
                set_clauses.append("pass_percentage = ?")
                params.append(pct)
            if 'passing_percentage' in columns:
                set_clauses.append("passing_percentage = ?")
                params.append(pct)
        if 'randomize_questions' in data:
            set_clauses.append("randomize_questions = ?")
            params.append(1 if data['randomize_questions'] else 0)
        if 'randomize_options' in data:
            set_clauses.append("randomize_options = ?")
            params.append(1 if data['randomize_options'] else 0)
        
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

        q_count = quiz.get('question_count', 0) or quiz.get('total_questions', 0)
        if target_status and q_count == 0:
            raise ValueError("This quiz cannot be published because it has 0 questions. Please add questions first.")

        status_text = 'published' if target_status else 'draft'

        supabase = get_supabase_client()
        if supabase:
            last_err = None
            for pub_val in (1 if target_status else 0, target_status):
                try:
                    res = supabase.table('quizzes').update({
                        'published': pub_val,
                        'status': status_text,
                        'updated_at': now
                    }).eq('id', clean_id).execute()
                    if not res or not getattr(res, 'data', None) or len(res.data) == 0:
                        raise RuntimeError(f"Quiz with ID {clean_id} not found in Supabase")
                    return QuizRepository.get_by_id(clean_id)
                except Exception as e:
                    err_str = str(e).lower()
                    last_err = e
                    if any(k in err_str for k in ('invalid input syntax for type integer', 'type boolean', '22p02', '42804')):
                        continue
                    raise
            logger.error("Supabase toggle_publish error: %s", last_err)
            raise RuntimeError(f"Database error toggling publish state: {last_err}")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(quizzes)")
        columns = [col['name'] for col in cursor.fetchall()]
        
        set_clauses = ["status = ?", "updated_at = ?"]
        params = [status_text, now]
        if 'published' in columns:
            set_clauses.append("published = ?")
            params.append(1 if target_status else 0)
        if 'is_published' in columns:
            set_clauses.append("is_published = ?")
            params.append(1 if target_status else 0)
        params.append(clean_id)
        
        cursor.execute(f"UPDATE quizzes SET {', '.join(set_clauses)} WHERE id = ?", params)
        conn.commit()
        conn.close()
        return QuizRepository.get_by_id(clean_id)

    @staticmethod
    def delete_quiz(quiz_id):
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            try:
                try:
                    supabase.table('quiz_questions').delete().eq('quiz_id', clean_id).execute()
                except Exception:
                    pass
                supabase.table('quizzes').delete().eq('id', clean_id).execute()
                return True
            except Exception as e:
                logger.error("Supabase delete_quiz error: %s", e)
                raise RuntimeError(f"Database error deleting quiz: {e}")

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM quiz_questions WHERE quiz_id = ?", (clean_id,))
        except Exception:
            pass
        cursor.execute("PRAGMA table_info(questions)")
        q_cols = [c['name'] for c in cursor.fetchall()]
        if 'quiz_id' in q_cols:
            cursor.execute("DELETE FROM questions WHERE quiz_id = ?", (clean_id,))
        cursor.execute("DELETE FROM quizzes WHERE id = ?", (clean_id,))
        conn.commit()
        conn.close()
        return True

    @staticmethod
    def recalculate_totals(quiz_id):
        clean_id = str(quiz_id).strip()
        supabase = get_supabase_client()
        if supabase:
            total_q = 0
            total_m = 0.0
            try:
                # 1. Fetch questions associated via authoritative quiz_questions join table
                try:
                    qq_res = supabase.table('quiz_questions').select('question_id').eq('quiz_id', clean_id).execute()
                    qq_rows = qq_res.data or []
                    total_q = len(qq_rows)
                    q_ids = [r['question_id'] for r in qq_rows if r.get('question_id')]
                    if q_ids:
                        marks_res = supabase.table('questions').select('marks').in_('id', q_ids).execute()
                        marks_rows = marks_res.data or []
                        total_m = sum(float(r.get('marks') or 1.0) for r in marks_rows)
                except Exception as qq_err:
                    # Fallback to direct questions.quiz_id if join table fails
                    logger.debug("Recalculate via quiz_questions failed, trying questions: %s", qq_err)
                    q_res = supabase.table('questions').select('marks').eq('quiz_id', clean_id).execute()
                    rows = q_res.data or []
                    total_q = len(rows)
                    total_m = sum(float(r.get('marks') or 1.0) for r in rows)

                now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                rounded_m = int(round(total_m)) if float(total_m).is_integer() else total_m
                
                if total_q == 0:
                    for pub_val in (0, False):
                        try:
                            supabase.table('quizzes').update({
                                'total_questions': total_q,
                                'total_marks': rounded_m,
                                'published': pub_val,
                                'status': 'draft',
                                'updated_at': now
                            }).eq('id', clean_id).execute()
                            break
                        except Exception:
                            continue
                else:
                    supabase.table('quizzes').update({
                        'total_questions': total_q,
                        'total_marks': rounded_m,
                        'updated_at': now
                    }).eq('id', clean_id).execute()
                return total_q, total_m
            except Exception as e:
                logger.error("Supabase recalculate_totals error: %s", e)
                return total_q, total_m

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if quiz_questions join table has records
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='quiz_questions'")
        has_qq = cursor.fetchone()[0] > 0
        
        count = 0
        total_marks = 0.0
        if has_qq:
            cursor.execute("""
            SELECT COUNT(q.id) as count, COALESCE(SUM(q.marks), 0) as total_marks
            FROM questions q
            JOIN quiz_questions qq ON q.id = qq.question_id
            WHERE qq.quiz_id = ?
            """, (clean_id,))
            row = cursor.fetchone()
            count = row['count'] if row else 0
            total_marks = row['total_marks'] if row else 0.0

        if count == 0:
            cursor.execute("PRAGMA table_info(questions)")
            q_cols = [c['name'] for c in cursor.fetchall()]
            if 'quiz_id' in q_cols:
                cursor.execute("""
                SELECT COUNT(id) as count, COALESCE(SUM(marks), 0) as total_marks
                FROM questions
                WHERE quiz_id = ?
                """, (clean_id,))
                row = cursor.fetchone()
                if row and row['count']:
                    count = row['count']
                    total_marks = row['total_marks']

        unpub = ", published = 0, status = 'draft'" if count == 0 else ""
        cursor.execute(f"""
        UPDATE quizzes
        SET total_questions = ?, total_marks = ?, updated_at = ? {unpub}
        WHERE id = ?
        """, (count, total_marks, datetime.datetime.now(datetime.timezone.utc).isoformat(), clean_id))
        conn.commit()
        conn.close()
        return count, total_marks
