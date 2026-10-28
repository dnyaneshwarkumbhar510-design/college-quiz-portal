import unittest
import json
import datetime
import uuid
from unittest.mock import MagicMock, patch
from main import app
from config import Config
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.question_repository import QuestionRepository
from app.database.repositories.student_repository import StudentRepository
from app.services.quiz_service import QuizService

class TestFixesVerification(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_quiz_service_subject_and_unit_validation(self):
        """Test that QuizService automatically clamps unit_number to [1, 4] and resolves subject."""
        # Ensure subjects exist
        subjects = SubjectRepository.get_all()
        self.assertGreater(len(subjects), 0)
        sub_id = subjects[0]['id']

        # Unit number > 4 should be clamped to 4
        quiz_data = {
            'title': 'Automated Test Unit Clamped Quiz',
            'subject_id': sub_id,
            'unit_number': 8,
            'unit_title': 'Advanced Algorithms',
            'duration_minutes': 30,
            'total_marks': 20,
            'passing_percentage': 40
        }
        created = QuizService.create_quiz(quiz_data)
        self.assertIsNotNone(created)
        self.assertIn(created['unit_number'], [1, 2, 3, 4])
        self.assertEqual(created['unit_number'], 4)
        self.assertEqual(created['duration'], 30)
        self.assertEqual(created['duration_minutes'], 30)
        self.assertEqual(created['passing_percentage'], 40.0)

    def test_supabase_payload_columns_match_production_schema(self):
        """
        Verify that when a Supabase client is present, create_quiz sends ONLY
        valid Supabase schema columns matching the real production schema:
        - uses 'duration' (NOT 'duration_minutes' which causes PGRST204)
        - uses 'total_questions' (NOT 'question_count')
        - uses 'pass_percentage' (NOT 'passing_percentage')
        - uses 'published' (NOT 'is_published')
        - includes 'created_at' and 'updated_at'
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        expected_created_row = {
            'id': 'test-uuid-001',
            'subject_id': 'c0000000-0000-0000-0000-000000000001',
            'subject': 'Data Structures & Algorithms',
            'unit_number': 2,
            'unit_title': 'Unit 2 Topic',
            'title': 'Production Schema Verified Quiz',
            'description': 'Verified description',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration': 20,
            'total_questions': 0,
            'marks_per_question': 1.0,
            'total_marks': 15.0,
            'pass_percentage': 40.0,
            'status': 'draft',
            'published': False,
            'randomize_questions': False,
            'randomize_options': False,
            'created_at': '2026-10-27T00:00:00+00:00',
            'updated_at': '2026-10-27T00:00:00+00:00'
        }

        mock_execute.return_value = MagicMock(data=[expected_created_row])
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        # Mock pre-check query
        mock_select = MagicMock()
        mock_select.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        mock_table.select.return_value = mock_select
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            created = QuizRepository.create_quiz({
                'title': 'Production Schema Verified Quiz',
                'description': 'Verified description',
                'subject_id': 'c0000000-0000-0000-0000-000000000001',
                'subject_name': 'Data Structures & Algorithms',
                'unit_number': 2,
                'unit_title': 'Unit 2 Topic',
                'class_name': 'TE Computer',
                'division': 'All',
                'department': 'Computer Engineering',
                'duration': 20,
                'total_marks': 15.0,
                'pass_percentage': 40.0
            })

            # Verify table called was 'quizzes'
            mock_supabase.table.assert_any_call('quizzes')

            # Verify the exact payload inserted into Supabase
            actual_payload = mock_table.insert.call_args[0][0]

            # Critical assertion: only valid Supabase columns must be present
            valid_supabase_quizzes_columns = {
                'id', 'subject_id', 'subject', 'unit_number', 'unit_title', 'title', 'description',
                'class_name', 'division', 'department', 'duration', 'total_questions',
                'marks_per_question', 'total_marks', 'pass_percentage', 'created_by', 'status',
                'published', 'randomize_questions', 'randomize_options', 'created_at', 'updated_at'
            }

            for key in actual_payload.keys():
                self.assertIn(key, valid_supabase_quizzes_columns, f"Forbidden column '{key}' sent to Supabase quizzes table!")

            # Verify unsupported columns that cause PGRST204 are absent
            self.assertNotIn('duration_minutes', actual_payload, "duration_minutes causes PGRST204 and must NOT be sent!")
            self.assertNotIn('question_count', actual_payload, "question_count must not be sent to Supabase quizzes!")
            self.assertNotIn('passing_percentage', actual_payload, "passing_percentage must not be sent to Supabase quizzes!")
            self.assertNotIn('is_published', actual_payload, "is_published must not be sent to Supabase quizzes!")

            # Verify real columns are present
            self.assertIn('duration', actual_payload)
            self.assertIn('total_questions', actual_payload)
            self.assertIn('pass_percentage', actual_payload)
            self.assertIn('published', actual_payload)
            self.assertIn('created_at', actual_payload)
            self.assertIn('updated_at', actual_payload)

            # Verify normalized return values provide both aliases
            self.assertEqual(created['duration'], 20)
            self.assertEqual(created['duration_minutes'], 20)
            self.assertEqual(created['total_questions'], 0)
            self.assertEqual(created['question_count'], 0)
            self.assertEqual(created['passing_percentage'], 40.0)
            self.assertEqual(created['pass_percentage'], 40.0)
            self.assertFalse(created['is_published'])
            self.assertFalse(created['published'])

    def test_quiz_update_payload_matches_production_schema(self):
        """
        Verify that update_quiz sends only production-compatible columns to Supabase
        ('duration', 'pass_percentage', 'published', 'updated_at') and NOT
        ('duration_minutes', 'passing_percentage', 'is_published').
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_execute = MagicMock()

        updated_row = {
            'id': 'test-quiz-upd-01',
            'title': 'Updated Quiz Title',
            'duration': 45,
            'pass_percentage': 50.0,
            'published': True,
            'status': 'published',
            'updated_at': '2026-10-27T12:00:00+00:00'
        }
        mock_execute.return_value = MagicMock(data=[updated_row])
        mock_update.eq.return_value.execute = mock_execute
        mock_table.update.return_value = mock_update
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=updated_row)
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            QuizRepository.update_quiz('test-quiz-upd-01', {
                'title': 'Updated Quiz Title',
                'duration_minutes': 45,
                'passing_percentage': 50.0,
                'is_published': True
            })

            mock_supabase.table.assert_any_call('quizzes')
            update_payload = mock_table.update.call_args[0][0]

            self.assertIn('duration', update_payload)
            self.assertEqual(update_payload['duration'], 45)
            self.assertIn('pass_percentage', update_payload)
            self.assertEqual(update_payload['pass_percentage'], 50.0)
            self.assertIn('published', update_payload)
            self.assertTrue(update_payload['published'])
            self.assertIn('updated_at', update_payload)

            self.assertNotIn('duration_minutes', update_payload)
            self.assertNotIn('passing_percentage', update_payload)
            self.assertNotIn('is_published', update_payload)

    def test_mobile_ui_css_and_overlay_rules(self):
        """
        Verify Problem 2 fix:
        - .hidden has display: none !important
        - .admin-sidebar-overlay is hidden by default and only displayed when not .hidden
        - .admin-shell, .admin-viewport, and .admin-content are responsive
        """
        css_path = 'app/static/css/style.css'
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 1. Verify .hidden definition
        self.assertIn('.hidden', css_content)
        self.assertIn('display: none !important;', css_content)

        # 2. Verify .admin-sidebar-overlay has display: none by default
        self.assertIn('.admin-sidebar-overlay', css_content)
        self.assertIn('display: none;', css_content)
        self.assertIn('.admin-sidebar-overlay:not(.hidden)', css_content)

        # 3. Verify shell template has hidden and style="display: none;" on #sidebarOverlay
        shell_path = 'app/templates/faculty/shell.html'
        with open(shell_path, 'r', encoding='utf-8') as f:
            shell_content = f.read()

        self.assertIn('id="sidebarOverlay"', shell_content)
        self.assertIn('admin-sidebar-overlay hidden', shell_content)
        self.assertIn('display: none;', shell_content)

        # 4. Verify admin.js toggles overlay visibility properly
        js_path = 'app/static/js/admin.js'
        with open(js_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        self.assertIn("overlay.classList.add('hidden')", js_content)
        self.assertIn("overlay.style.display = 'none'", js_content)
        self.assertIn("overlay.classList.remove('hidden')", js_content)
        self.assertIn("overlay.style.display = 'block'", js_content)

    def test_add_quiz_api_with_faculty_session(self):
        """Test API creation of quiz through POST /api/admin/quizzes."""
        # Login faculty
        with self.client.session_transaction() as sess:
            sess['faculty'] = {
                'id': 'faculty-test-id-01',
                'full_name': 'Prof. Ankita Gadekar',
                'email': 'ankita.gadekar@nmiet.edu.in',
                'role': 'faculty'
            }

        subjects = SubjectRepository.get_all()
        sub_id = subjects[0]['id']

        res = self.client.post('/api/admin/quizzes', json={
            'title': 'API Test Examination Quiz',
            'subject_id': sub_id,
            'unit_number': 3,
            'unit_title': 'Unit 3 Trees & Graphs',
            'class_name': 'TE Computer',
            'division': 'A',
            'department': 'Computer Engineering',
            'duration_minutes': 25,
            'total_marks': 25,
            'passing_percentage': 40
        })

        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['quiz']['title'], 'API Test Examination Quiz')
        self.assertEqual(data['quiz']['unit_number'], 3)
        self.assertEqual(data['quiz']['duration'], 25)

    def test_fpl_custom_subject_quiz_creation_and_persistence(self):
        """
        Verify that POST /api/admin/quizzes with custom subject (e.g. Fpl):
        1. Creates/resolves the subject with valid created_at and updated_at.
        2. Assigns a valid subject UUID.
        3. Creates the quiz linked to that subject.
        4. Makes the quiz visible on /admin/quizzes and preserves it across requests.
        """
        with self.client.session_transaction() as sess:
            sess['faculty'] = {
                'id': 'faculty-fpl-tester',
                'full_name': 'Prof. Ankita Gadekar',
                'email': 'ankita.gadekar@nmiet.edu.in',
                'role': 'faculty'
            }

        res = self.client.post('/api/admin/quizzes', json={
            'title': 'Fundamentals of Programming Language Examination',
            'subject_name': 'Fpl',
            'subject_id': None,
            'unit_number': 1,
            'unit_title': 'Unit 1 C Basics',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration_minutes': 20,
            'total_marks': 15.0,
            'passing_percentage': 40.0
        })

        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertTrue(data['success'])
        created_quiz = data['quiz']
        self.assertEqual(created_quiz['title'], 'Fundamentals of Programming Language Examination')
        self.assertEqual(created_quiz['subject_name'], 'Fpl')
        self.assertIsNotNone(created_quiz['subject_id'])
        self.assertGreater(len(created_quiz['subject_id']), 10)

        # Check /admin/quizzes page contains the created quiz and subject name
        page_res = self.client.get('/admin/quizzes')
        self.assertEqual(page_res.status_code, 200)
        self.assertIn('Fundamentals of Programming Language Examination', page_res.get_data(as_text=True))
        self.assertIn('Fpl', page_res.get_data(as_text=True))

        # Check refresh / second GET still contains the quiz
        refresh_res = self.client.get('/admin/quizzes')
        self.assertEqual(refresh_res.status_code, 200)
        self.assertIn('Fundamentals of Programming Language Examination', refresh_res.get_data(as_text=True))

    def test_subject_seeding_includes_both_created_at_and_updated_at(self):
        """
        Verify that Supabase subject auto-seeding sends BOTH 'created_at' and 'updated_at'
        (both are NOT NULL in the production Supabase subjects table).
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_select = MagicMock()

        # Mock select check returning None (subject does not exist yet)
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        mock_execute.return_value = MagicMock(data=[{'id': 'c0000000-0000-0000-0000-000000000001'}])
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_table.select = mock_select.select
        mock_supabase.table.return_value = mock_table

        SubjectRepository._seed_defaults_supabase(mock_supabase)

        # Ensure insert was called for default subjects
        self.assertGreaterEqual(mock_table.insert.call_count, 1)

        valid_subject_columns = {
            'id', 'code', 'name', 'department', 'class_name', 'description', 'created_at', 'updated_at'
        }

        for call_args in mock_table.insert.call_args_list:
            payload = call_args[0][0]
            # Must contain created_at
            self.assertIn('created_at', payload, "Seed payload is missing 'created_at'!")
            self.assertIsNotNone(payload['created_at'])
            self.assertTrue(len(str(payload['created_at'])) > 10)

            # Must contain updated_at
            self.assertIn('updated_at', payload, "Seed payload is missing 'updated_at'!")
            self.assertIsNotNone(payload['updated_at'])
            self.assertTrue(len(str(payload['updated_at'])) > 10)

            # Verify all keys are in valid production columns
            for col in payload.keys():
                self.assertIn(col, valid_subject_columns, f"Unexpected column '{col}' in subject seed payload!")

    def test_custom_subject_get_or_create_fpl_payload_and_none_safety(self):
        """
        Verify that SubjectRepository.get_or_create for custom subject FPL:
        1. Includes all required fields: id, code, name, department, class_name, description, created_at, updated_at.
        2. Both created_at and updated_at are valid UTC ISO timestamps.
        3. Does NOT raise 'NoneType' object has no attribute 'data' when res is None.
        4. Successfully creates and returns custom subject FPL.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_insert = MagicMock()

        # 1. Simulate maybe_single().execute() returning None safely without AttributeError
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None

        new_subject_row = {
            'id': '9c06fc27-46dd-4411-a140-857de2c9737a',
            'code': 'FPL',
            'name': 'Fpl',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': '',
            'created_at': '2026-10-27T16:43:53.148341+00:00',
            'updated_at': '2026-10-27T16:43:53.148341+00:00'
        }
        mock_insert.insert.return_value.execute.return_value = MagicMock(data=[new_subject_row])
        mock_table.select = mock_select.select
        mock_table.insert = mock_insert.insert
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.subject_repository.get_supabase_client', return_value=mock_supabase):
            sub = SubjectRepository.get_or_create(
                code='FPL',
                name='Fpl',
                department='Computer Engineering',
                class_name='TE Computer',
                description=''
            )

            # Verify table called was subjects
            mock_supabase.table.assert_any_call('subjects')

            # Verify insert payload
            insert_call_args = mock_insert.insert.call_args[0][0]
            required_keys = ['id', 'code', 'name', 'department', 'class_name', 'description', 'created_at', 'updated_at']
            for k in required_keys:
                self.assertIn(k, insert_call_args, f"Custom subject payload missing '{k}'!")
                self.assertIsNotNone(insert_call_args[k])

            self.assertEqual(insert_call_args['code'], 'FPL')
            self.assertEqual(insert_call_args['name'], 'Fpl')
            self.assertTrue(len(str(insert_call_args['created_at'])) > 10)
            self.assertTrue(len(str(insert_call_args['updated_at'])) > 10)

            # Returned subject
            self.assertEqual(sub['id'], '9c06fc27-46dd-4411-a140-857de2c9737a')
            self.assertEqual(sub['code'], 'FPL')
            self.assertEqual(sub['name'], 'Fpl')

    def test_subject_get_or_create_converts_supabase_insert_errors_to_runtime_error(self):
        """Verify that Supabase insert errors in get_or_create are converted into a useful RuntimeError."""
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_insert = MagicMock()

        # Lookup returns None
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
        # Insert raises exception (e.g. Postgres constraint error)
        mock_insert.insert.return_value.execute.side_effect = Exception("null value in column 'updated_at' violates not-null constraint")
        mock_table.select = mock_select.select
        mock_table.insert = mock_insert.insert
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.subject_repository.get_supabase_client', return_value=mock_supabase):
            with self.assertRaises(RuntimeError) as ctx:
                SubjectRepository.get_or_create(code='ERR', name='Error Subject')
            self.assertIn("Database error in subject lookup/creation", str(ctx.exception))

    def test_default_subject_seeding_reports_failure_when_insert_fails(self):
        """Verify default subject seeding logs errors when inserts fail instead of claiming success."""
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_insert = MagicMock()

        # Select says subject does not exist
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None
        # Insert raises error
        mock_insert.insert.return_value.execute.side_effect = Exception("Insert failed")
        mock_table.select = mock_select.select
        mock_table.insert = mock_insert.insert
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.subject_repository.logger.error') as mock_log_err:
            SubjectRepository._seed_defaults_supabase(mock_supabase)
            mock_log_err.assert_called()

    def test_quiz_service_creates_custom_subject_and_references_valid_subject_uuid(self):
        """
        Verify QuizService.create_quiz() automatically creates a custom subject (e.g. Fpl / FPL)
        and passes the resulting subject UUID to QuizRepository.create_quiz().
        """
        fake_sub = {
            'id': '9c06fc27-46dd-4411-a140-857de2c9737a',
            'code': 'FPL',
            'name': 'Fpl',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': '',
            'created_at': '2026-10-27T16:43:53.148341+00:00',
            'updated_at': '2026-10-27T16:43:53.148341+00:00'
        }

        with patch('app.services.quiz_service.SubjectRepository.get_or_create', return_value=fake_sub) as mock_get_or_create, \
             patch('app.services.quiz_service.QuizRepository.create_quiz', return_value={'id': 'quiz-uuid-1', 'title': 'FPL Exam'}) as mock_repo_create:

            result = QuizService.create_quiz({
                'title': 'FPL Exam Quiz',
                'subject_name': 'Fpl',
                'unit_number': 1,
                'unit_title': 'Unit 1 Introduction to Programming',
                'class_name': 'TE Computer',
                'division': 'A',
                'department': 'Computer Engineering'
            })

            mock_get_or_create.assert_called_once_with(
                code='FPL',
                name='Fpl',
                department='Computer Engineering',
                class_name='TE Computer'
            )
            created_payload = mock_repo_create.call_args[0][0]
            self.assertEqual(created_payload['subject_id'], '9c06fc27-46dd-4411-a140-857de2c9737a')
            self.assertEqual(created_payload['subject_name'], 'Fpl')

    def test_quiz_repository_get_all_join_fallback(self):
        """
        Verify that if the PostgREST foreign key relationship syntax 'subjects(name)'
        encounters an error, QuizRepository.get_all gracefully falls back to select('*')
        without crashing the admin dashboard.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()

        quiz_row = {
            'id': 'quiz-fallback-01',
            'subject_id': 'c0000000-0000-0000-0000-000000000001',
            'unit_number': 1,
            'unit_title': 'Unit 1 Fallback',
            'title': 'Join Fallback Quiz',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration_minutes': 15,
            'question_count': 0,
            'total_marks': 15.0,
            'passing_percentage': 40.0,
            'is_published': False,
            'randomize_questions': False,
            'randomize_options': False,
            'created_at': '2026-10-27T00:00:00+00:00'
        }

        # First call with subjects(name) raises exception; second call with '*' succeeds
        call_count = {'count': 0}
        def fake_select(cols):
            call_count['count'] += 1
            inner = MagicMock()
            if 'subjects(name)' in cols:
                inner.order.return_value.execute.side_effect = RuntimeError("PGRST200 Relationship not found")
            else:
                inner.order.return_value.execute.return_value = MagicMock(data=[quiz_row])
            return inner

        mock_table.select = fake_select
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            quizzes = QuizRepository.get_all()
            self.assertEqual(len(quizzes), 1)
            self.assertEqual(quizzes[0]['title'], 'Join Fallback Quiz')
            self.assertGreaterEqual(call_count['count'], 2)

    def test_quiz_creation_integer_flag_types_prevent_22p02(self):
        """
        Verify that QuizRepository sends integer flags (0/1) to Supabase quizzes table
        by default to match the production schema (INTEGER columns), avoiding PostgreSQL 22P02:
        'invalid input syntax for type integer: "false"'.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        returned_row = {
            'id': 'test-uuid-integer-flags-001',
            'subject_id': 'c0000000-0000-0000-0000-000000000001',
            'subject': 'Data Structures & Algorithms',
            'unit_number': 1,
            'unit_title': 'Unit 1 Foundations',
            'title': 'Integer Flags Test Quiz',
            'description': 'Testing integer compatibility',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration': 20,
            'total_questions': 0,
            'marks_per_question': 1.0,
            'total_marks': 15,
            'pass_percentage': 40,
            'status': 'draft',
            'published': 0,
            'randomize_questions': 0,
            'randomize_options': 0,
            'created_at': '2026-10-28T00:00:00+00:00',
            'updated_at': '2026-10-28T00:00:00+00:00'
        }

        mock_execute.return_value = MagicMock(data=[returned_row])
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            created = QuizRepository.create_quiz({
                'title': 'Integer Flags Test Quiz',
                'description': 'Testing integer compatibility',
                'subject_id': 'c0000000-0000-0000-0000-000000000001',
                'subject_name': 'Data Structures & Algorithms',
                'unit_number': 1,
                'unit_title': 'Unit 1 Foundations',
                'class_name': 'TE Computer',
                'division': 'All',
                'department': 'Computer Engineering',
                'duration': 20,
                'total_marks': 15.0,
                'pass_percentage': 40.0,
                'randomize_questions': False,
                'randomize_options': False
            })

            actual_payload = mock_table.insert.call_args[0][0]

            # Primary assertions: flags sent to Supabase MUST be integers (0/1), NOT boolean False
            self.assertEqual(actual_payload['published'], 0)
            self.assertEqual(actual_payload['randomize_questions'], 0)
            self.assertEqual(actual_payload['randomize_options'], 0)
            self.assertIsInstance(actual_payload['published'], int)
            self.assertIsInstance(actual_payload['randomize_questions'], int)
            self.assertIsInstance(actual_payload['randomize_options'], int)
            # Ensure they are not bools (in Python bool is a subclass of int, so check type exactly)
            self.assertIs(type(actual_payload['published']), int)
            self.assertIs(type(actual_payload['randomize_questions']), int)
            self.assertIs(type(actual_payload['randomize_options']), int)

            # Ensure numeric fields are typed as valid integers or numbers
            self.assertIsInstance(actual_payload['duration'], int)
            self.assertEqual(actual_payload['duration'], 20)
            self.assertIsInstance(actual_payload['total_marks'], int)
            self.assertEqual(actual_payload['total_marks'], 15)
            self.assertIsInstance(actual_payload['pass_percentage'], int)
            self.assertEqual(actual_payload['pass_percentage'], 40)
            self.assertIsInstance(actual_payload['unit_number'], int)
            self.assertEqual(actual_payload['unit_number'], 1)
            self.assertEqual(actual_payload['total_questions'], 0)

            # Verify normalized quiz dictionary returns Python booleans for UI consumption
            self.assertFalse(created['is_published'])
            self.assertFalse(created['published'])
            self.assertFalse(created['randomize_questions'])
            self.assertFalse(created['randomize_options'])
            self.assertIs(type(created['is_published']), bool)
            self.assertIs(type(created['published']), bool)
            self.assertIs(type(created['randomize_questions']), bool)
            self.assertIs(type(created['randomize_options']), bool)

    def test_quiz_creation_adapts_to_boolean_columns_on_type_mismatch(self):
        """
        Verify that if the remote Supabase schema has BOOLEAN columns (throwing 42804
        'column is of type boolean but expression is of type integer'), the repository
        adaptively retries with boolean values and successfully completes quiz creation.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()

        returned_row = {
            'id': 'test-uuid-boolean-flags-002',
            'subject_id': 'c0000000-0000-0000-0000-000000000001',
            'subject': 'Data Structures & Algorithms',
            'unit_number': 3,
            'unit_title': 'Unit 3 Trees',
            'title': 'Boolean Adaptive Quiz',
            'description': 'Testing adaptive fallback',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration': 30,
            'total_questions': 0,
            'marks_per_question': 1.0,
            'total_marks': 20,
            'pass_percentage': 40,
            'status': 'draft',
            'published': False,
            'randomize_questions': False,
            'randomize_options': False,
            'created_at': '2026-10-28T00:00:00+00:00',
            'updated_at': '2026-10-28T00:00:00+00:00'
        }

        # Mock insert: first call (with integer flags) raises 42804 type boolean error;
        # subsequent variation succeeds
        call_records = []
        def fake_insert(payload):
            call_records.append(dict(payload))
            mock_res = MagicMock()
            if len(call_records) == 1:
                # First attempt with integer flags raises boolean type mismatch
                mock_res.execute.side_effect = RuntimeError(
                    "{'message': 'column \"published\" is of type boolean but expression is of type integer', 'code': '42804'}"
                )
            else:
                # Fallback variation with boolean flags succeeds
                mock_res.execute.return_value = MagicMock(data=[returned_row])
            return mock_res

        mock_table.insert = fake_insert
        mock_table.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            created = QuizRepository.create_quiz({
                'title': 'Boolean Adaptive Quiz',
                'subject_id': 'c0000000-0000-0000-0000-000000000001',
                'subject_name': 'Data Structures & Algorithms',
                'unit_number': 3,
                'duration': 30,
                'total_marks': 20.0,
                'pass_percentage': 40.0
            })

            # Verify that adaptive retry occurred
            self.assertGreaterEqual(len(call_records), 2)
            # First attempt sent integer flag
            self.assertEqual(call_records[0]['published'], 0)
            # Second attempt adapted published to boolean False
            self.assertFalse(call_records[1]['published'])
            self.assertIsNotNone(created)
            self.assertEqual(created['title'], 'Boolean Adaptive Quiz')

    def test_quiz_service_sanitization_and_type_casting(self):
        """
        Verify that QuizService.create_quiz thoroughly sanitizes all form input types
        (strings to ints/floats, clamping unit_number to [1, 4], resolving duration and marks).
        """
        mock_repo_create = MagicMock()
        mock_repo_create.return_value = {
            'id': 'sanitized-quiz-01',
            'title': 'Sanitized Parameters Quiz',
            'unit_number': 2,
            'duration': 25,
            'duration_minutes': 25,
            'total_marks': 30.0,
            'pass_percentage': 50.0,
            'passing_percentage': 50.0,
            'randomize_questions': True,
            'randomize_options': False
        }

        with patch('app.services.quiz_service.QuizRepository.create_quiz', mock_repo_create):
            with patch('app.services.quiz_service.SubjectRepository.get_all', return_value=[{'id': 'c0000000-0000-0000-0000-000000000001', 'name': 'DSA'}]):
                result = QuizService.create_quiz({
                    'title': 'Sanitized Parameters Quiz',
                    'unit_number': '2',
                    'duration_minutes': '25',
                    'total_marks': '30.0',
                    'passing_percentage': '50.0',
                    'randomize_questions': True,
                    'randomize_options': False
                })

                passed_data = mock_repo_create.call_args[0][0]
                self.assertIsInstance(passed_data['unit_number'], int)
                self.assertEqual(passed_data['unit_number'], 2)
                self.assertIsInstance(passed_data['duration'], int)
                self.assertEqual(passed_data['duration'], 25)
                self.assertIsInstance(passed_data['duration_minutes'], int)
                self.assertEqual(passed_data['duration_minutes'], 25)
                self.assertIsInstance(passed_data['total_marks'], float)
                self.assertEqual(passed_data['total_marks'], 30.0)
                self.assertIsInstance(passed_data['pass_percentage'], float)
                self.assertEqual(passed_data['pass_percentage'], 50.0)
                self.assertIsInstance(passed_data['randomize_questions'], bool)
                self.assertTrue(passed_data['randomize_questions'])
                self.assertIsInstance(passed_data['randomize_options'], bool)
                self.assertFalse(passed_data['randomize_options'])

    def test_quiz_toggle_publish_adapts_to_integer_columns(self):
        """
        Verify that QuizRepository.toggle_publish sends integer 1/0 for published
        state first and falls back to boolean if necessary.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_execute = MagicMock()

        updated_row = {
            'id': 'test-toggle-quiz-01',
            'title': 'Toggle Quiz',
            'published': 1,
            'status': 'published',
            'total_questions': 5,
            'updated_at': '2026-10-28T00:00:00+00:00'
        }

        mock_execute.return_value = MagicMock(data=[updated_row])
        mock_update.eq.return_value.execute = mock_execute
        mock_table.update.return_value = mock_update
        mock_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=updated_row)
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.quiz_repository.QuizRepository.get_by_id', return_value=updated_row):
                QuizRepository.toggle_publish('test-toggle-quiz-01', True)

                # Verify update was called with integer 1 for published
                actual_update_payload = mock_table.update.call_args[0][0]
                self.assertEqual(actual_update_payload['published'], 1)
                self.assertEqual(actual_update_payload['status'], 'published')

    def test_question_get_by_quiz_uses_quiz_questions_join_table(self):
        """
        Regression test: Verify QuestionRepository.get_by_quiz loads questions via
        authoritative quiz_questions join table and does NOT assume questions.quiz_id
        exists in Supabase schema.
        """
        mock_supabase = MagicMock()
        mock_qq_table = MagicMock()
        mock_q_table = MagicMock()

        # Mock quiz_questions response
        qq_rows = [
            {'id': 'qq-uuid-1', 'quiz_id': 'quiz-uuid-999', 'question_id': 'q-uuid-1', 'question_order': 1},
            {'id': 'qq-uuid-2', 'quiz_id': 'quiz-uuid-999', 'question_id': 'q-uuid-2', 'question_order': 2}
        ]
        qq_select_mock = MagicMock()
        qq_select_mock.eq.return_value.order.return_value.execute.return_value = MagicMock(data=qq_rows)
        mock_qq_table.select.return_value = qq_select_mock

        # Mock questions response (note questions table in Supabase does NOT have quiz_id column)
        q_rows = [
            {'id': 'q-uuid-1', 'question_text': 'What is a stack?', 'option_a': 'LIFO', 'option_b': 'FIFO', 'option_c': 'Tree', 'option_d': 'Graph', 'correct_answer': 'A', 'marks': 1.0},
            {'id': 'q-uuid-2', 'question_text': 'What is a queue?', 'option_a': 'LIFO', 'option_b': 'FIFO', 'option_c': 'Tree', 'option_d': 'Graph', 'correct_answer': 'B', 'marks': 2.0}
        ]
        q_select_mock = MagicMock()
        q_select_mock.in_.return_value.execute.return_value = MagicMock(data=q_rows)
        mock_q_table.select.return_value = q_select_mock

        def table_router(table_name):
            if table_name == 'quiz_questions':
                return mock_qq_table
            elif table_name == 'questions':
                return mock_q_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        with patch('app.database.repositories.question_repository.get_supabase_client', return_value=mock_supabase):
            questions = QuestionRepository.get_by_quiz('quiz-uuid-999')

            # Verify quiz_questions table was queried
            mock_qq_table.select.assert_called_with('id, quiz_id, question_id, question_order, created_at')
            qq_select_mock.eq.assert_called_with('quiz_id', 'quiz-uuid-999')

            # Verify questions table was queried via .in_() on IDs
            mock_q_table.select.assert_called_with('*')
            q_select_mock.in_.assert_called_with('id', ['q-uuid-1', 'q-uuid-2'])

            # Verify results are properly populated with quiz_id and preserved question_order
            self.assertEqual(len(questions), 2)
            self.assertEqual(questions[0]['id'], 'q-uuid-1')
            self.assertEqual(questions[0]['quiz_id'], 'quiz-uuid-999')
            self.assertEqual(questions[0]['question_order'], 1)
            self.assertEqual(questions[1]['id'], 'q-uuid-2')
            self.assertEqual(questions[1]['quiz_id'], 'quiz-uuid-999')
            self.assertEqual(questions[1]['question_order'], 2)

    def test_question_create_does_not_pass_quiz_id_to_questions_table_and_inserts_quiz_questions(self):
        """
        Regression test: Verify QuestionRepository.create_question does NOT pass
        'quiz_id' to public.questions table insert, and properly creates a link
        in public.quiz_questions.
        """
        mock_supabase = MagicMock()
        mock_qq_table = MagicMock()
        mock_q_table = MagicMock()

        # Mock count query on quiz_questions
        mock_count_exec = MagicMock(count=0)
        mock_qq_table.select.return_value.eq.return_value.execute.return_value = mock_count_exec
        mock_qq_table.insert.return_value.execute.return_value = MagicMock(data=[{'id': 'qq-uuid-new'}])

        # Mock questions table insert
        inserted_q_row = {
            'id': 'new-question-uuid',
            'question_text': 'What is encapsulation?',
            'option_a': 'Data hiding',
            'option_b': 'Inheritance',
            'option_c': 'Polymorphism',
            'option_d': 'Overloading',
            'correct_answer': 'A',
            'marks': 2.0,
            'explanation': 'Encapsulation binds data and code.',
            'created_at': '2026-10-28T00:00:00+00:00',
            'updated_at': '2026-10-28T00:00:00+00:00'
        }
        mock_q_table.insert.return_value.execute.return_value = MagicMock(data=[inserted_q_row])

        def table_router(table_name):
            if table_name == 'quiz_questions':
                return mock_qq_table
            elif table_name == 'questions':
                return mock_q_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        fake_quiz = {
            'id': 'quiz-uuid-999',
            'title': 'Test Quiz',
            'total_questions': 0
        }

        with patch('app.database.repositories.question_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.question_repository.QuizRepository.get_by_id', return_value=fake_quiz):
                with patch('app.database.repositories.question_repository.QuizRepository.recalculate_totals', return_value=(1, 2.0)):
                    result = QuestionRepository.create_question({
                        'quiz_id': 'quiz-uuid-999',
                        'question_text': 'What is encapsulation?',
                        'option_a': 'Data hiding',
                        'option_b': 'Inheritance',
                        'option_c': 'Polymorphism',
                        'option_d': 'Overloading',
                        'correct_answer': 'A',
                        'marks': 2.0,
                        'explanation': 'Encapsulation binds data and code.'
                    })

                    # Verify questions insert payload
                    actual_q_payload = mock_q_table.insert.call_args[0][0]
                    self.assertNotIn('quiz_id', actual_q_payload, "quiz_id MUST NOT be passed to public.questions table insert!")
                    self.assertEqual(actual_q_payload['question_text'], 'What is encapsulation?')
                    self.assertEqual(actual_q_payload['correct_answer'], 'A')
                    self.assertEqual(actual_q_payload['marks'], 2.0)

                    # Verify quiz_questions insert payload
                    actual_qq_payload = mock_qq_table.insert.call_args[0][0]
                    self.assertEqual(actual_qq_payload['quiz_id'], 'quiz-uuid-999')
                    self.assertEqual(actual_qq_payload['question_id'], actual_q_payload['id'])
                    self.assertEqual(actual_qq_payload['question_order'], 1)

                    # Verify returned question object has quiz_id and question_order
                    self.assertEqual(result['quiz_id'], 'quiz-uuid-999')
                    self.assertEqual(result['question_order'], 1)

    def test_quiz_repository_recalculate_totals_uses_quiz_questions(self):
        """
        Regression test: Verify QuizRepository.recalculate_totals queries quiz_questions
        join table first and does NOT fail when questions.quiz_id does not exist.
        """
        mock_supabase = MagicMock()
        mock_qq_table = MagicMock()
        mock_q_table = MagicMock()
        mock_quizzes_table = MagicMock()

        # Mock quiz_questions response
        mock_qq_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[
            {'question_id': 'q-1'},
            {'question_id': 'q-2'}
        ])

        # Mock questions response for marks
        mock_q_table.select.return_value.in_.return_value.execute.return_value = MagicMock(data=[
            {'marks': 2.5},
            {'marks': 3.5}
        ])

        # Mock quizzes table update
        mock_quizzes_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        def table_router(table_name):
            if table_name == 'quiz_questions':
                return mock_qq_table
            elif table_name == 'questions':
                return mock_q_table
            elif table_name == 'quizzes':
                return mock_quizzes_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            q_count, t_marks = QuizRepository.recalculate_totals('quiz-uuid-999')

            self.assertEqual(q_count, 2)
            self.assertEqual(t_marks, 6.0)

            # Verify quizzes table updated with total_questions = 2 and total_marks = 6
            update_payload = mock_quizzes_table.update.call_args[0][0]
            self.assertEqual(update_payload['total_questions'], 2)
            self.assertEqual(update_payload['total_marks'], 6)

    def test_question_delete_removes_from_quiz_questions(self):
        """
        Regression test: Verify QuestionRepository.delete_question removes association
        from quiz_questions table and recalculates totals.
        """
        mock_supabase = MagicMock()
        mock_qq_table = MagicMock()
        mock_q_table = MagicMock()

        mock_qq_table.delete.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_qq_table.select.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
        mock_q_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        def table_router(table_name):
            if table_name == 'quiz_questions':
                return mock_qq_table
            elif table_name == 'questions':
                return mock_q_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        with patch('app.database.repositories.question_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.question_repository.QuizRepository.recalculate_totals') as mock_recalc:
                result = QuestionRepository.delete_question('q-uuid-del', 'quiz-uuid-999')
                self.assertTrue(result)
                mock_recalc.assert_called_with('quiz-uuid-999')

    def test_quiz_repository_question_counts_use_quiz_questions(self):
        """
        Regression test: Verify QuizRepository.get_all and get_by_id query quiz_questions
        for question counts.
        """
        mock_supabase = MagicMock()
        mock_qq_table = MagicMock()
        mock_quizzes_table = MagicMock()

        mock_quizzes_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data={
            'id': 'quiz-uuid-count',
            'title': 'Count Test Quiz',
            'total_questions': 0
        })

        mock_qq_count_exec = MagicMock(count=4)
        mock_qq_table.select.return_value.eq.return_value.execute.return_value = mock_qq_count_exec

        def table_router(table_name):
            if table_name == 'quiz_questions':
                return mock_qq_table
            elif table_name == 'quizzes':
                return mock_quizzes_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        with patch('app.database.repositories.quiz_repository.get_supabase_client', return_value=mock_supabase):
            quiz = QuizRepository.get_by_id('quiz-uuid-count')
            self.assertIsNotNone(quiz)
            self.assertEqual(quiz['question_count'], 4)
            self.assertEqual(quiz['total_questions'], 4)
            mock_qq_table.select.assert_called_with('id', count='exact', head=True)

    def test_submit_attempt_converts_is_correct_to_integer_for_supabase(self):
        """
        Regression test: Verify AttemptRepository.submit_attempt converts is_correct
        to integer 1/0 for Supabase PostgreSQL payload to prevent 22P02 syntax errors.
        """
        from app.database.repositories.attempt_repository import AttemptRepository

        mock_supabase = MagicMock()
        mock_attempts_table = MagicMock()
        mock_answers_table = MagicMock()

        attempt_row = {
            'id': 'att-uuid-101',
            'quiz_id': 'quiz-uuid-101',
            'student_id': 'stu-uuid-101',
            'status': 'in_progress',
            'total_questions': 2,
            'total_marks': 3.0
        }

        # Mock attempts select
        mock_attempts_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=attempt_row)
        # Mock attempts update
        mock_attempts_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[attempt_row])
        # Mock answers delete
        mock_answers_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        # Mock answers insert
        mock_answers_table.insert.return_value.execute.return_value = MagicMock(data=[])
        # Mock answers select for get_attempt_details
        mock_answers_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[
            {'question_id': 'q-101', 'selected_answer': 'A', 'is_correct': 1, 'marks_awarded': 1.0},
            {'question_id': 'q-102', 'selected_answer': 'C', 'is_correct': 0, 'marks_awarded': 0.0}
        ])

        def table_router(table_name):
            if table_name == 'attempts':
                return mock_attempts_table
            elif table_name == 'answers':
                return mock_answers_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        fake_quiz = {
            'id': 'quiz-uuid-101',
            'title': 'Test Quiz',
            'pass_percentage': 40.0,
            'total_marks': 3.0
        }

        fake_questions = [
            {'id': 'q-101', 'question_text': 'Q1', 'option_a': 'Opt A', 'option_b': 'Opt B', 'option_c': 'Opt C', 'option_d': 'Opt D', 'correct_answer': 'A', 'marks': 1.0},
            {'id': 'q-102', 'question_text': 'Q2', 'option_a': 'Opt A', 'option_b': 'Opt B', 'option_c': 'Opt C', 'option_d': 'Opt D', 'correct_answer': 'B', 'marks': 2.0}
        ]

        with patch('app.database.repositories.attempt_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.attempt_repository.QuizRepository.get_by_id', return_value=fake_quiz):
                with patch('app.database.repositories.attempt_repository.QuestionRepository.get_by_quiz', return_value=fake_questions):
                    with patch('app.database.repositories.attempt_repository.StudentRepository.get_by_id', return_value={'id': 'stu-uuid-101', 'full_name': 'Test Student'}):
                        result = AttemptRepository.submit_attempt('att-uuid-101', {
                            'q-101': 'A', # Correct
                            'q-102': 'C'  # Wrong
                        })

                        # Verify answers delete was called for this attempt
                        mock_answers_table.delete.assert_called()
                        mock_answers_table.delete.return_value.eq.assert_called_with('attempt_id', 'att-uuid-101')

                        # Verify answers insert was called
                        mock_answers_table.insert.assert_called_once()
                        inserted_answers = mock_answers_table.insert.call_args[0][0]

                        self.assertEqual(len(inserted_answers), 2)

                        # Q1 answer assertions:
                        q1_ans = next(a for a in inserted_answers if a['question_id'] == 'q-101')
                        self.assertEqual(q1_ans['selected_answer'], 'A')
                        self.assertIsInstance(q1_ans['is_correct'], int)
                        self.assertNotIsInstance(q1_ans['is_correct'], bool)
                        self.assertEqual(q1_ans['is_correct'], 1, "is_correct must be integer 1 for Supabase")
                        self.assertEqual(q1_ans['marks_awarded'], 1.0)

                        # Q2 answer assertions:
                        q2_ans = next(a for a in inserted_answers if a['question_id'] == 'q-102')
                        self.assertEqual(q2_ans['selected_answer'], 'C')
                        self.assertIsInstance(q2_ans['is_correct'], int)
                        self.assertNotIsInstance(q2_ans['is_correct'], bool)
                        self.assertEqual(q2_ans['is_correct'], 0, "is_correct must be integer 0 for Supabase")
                        self.assertEqual(q2_ans['marks_awarded'], 0.0)

                        # Verify attempts update payload
                        mock_attempts_table.update.assert_called_once()
                        att_update = mock_attempts_table.update.call_args[0][0]
                        self.assertEqual(att_update['total_questions'], 2)
                        self.assertEqual(att_update['attempted_questions'], 2)
                        self.assertEqual(att_update['correct_answers'], 1)
                        self.assertEqual(att_update['wrong_answers'], 1)
                        self.assertEqual(att_update['unattempted'], 0)
                        self.assertEqual(att_update['obtained_marks'], 1.0)
                        self.assertEqual(att_update['percentage'], 33.33)
                        self.assertEqual(att_update['status'], 'FAIL') # 33.33% < 40%

                        # Verify reviews returned retain Python booleans for internal app usage
                        self.assertIsNotNone(result)
                        reviews = result['reviews']
                        q1_rev = next(r for r in reviews if r['question_id'] == 'q-101')
                        self.assertIs(q1_rev['is_correct'], True)
                        q2_rev = next(r for r in reviews if r['question_id'] == 'q-102')
                        self.assertIs(q2_rev['is_correct'], False)

    def test_submit_attempt_handles_unanswered_questions(self):
        """
        Verify that unanswered questions have selected_answer=None, is_correct=0,
        marks_awarded=0.0, and unattempted count is accurate.
        """
        from app.database.repositories.attempt_repository import AttemptRepository

        mock_supabase = MagicMock()
        mock_attempts_table = MagicMock()
        mock_answers_table = MagicMock()

        attempt_row = {
            'id': 'att-uuid-102',
            'quiz_id': 'quiz-uuid-102',
            'student_id': 'stu-uuid-102',
            'status': 'in_progress',
            'total_questions': 2,
            'total_marks': 2.0
        }

        mock_attempts_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=attempt_row)
        mock_attempts_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[attempt_row])
        mock_answers_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        mock_answers_table.insert.return_value.execute.return_value = MagicMock(data=[])
        mock_answers_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        def table_router(table_name):
            if table_name == 'attempts': return mock_attempts_table
            elif table_name == 'answers': return mock_answers_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        fake_quiz = {'id': 'quiz-uuid-102', 'title': 'Test Quiz 2', 'pass_percentage': 40.0, 'total_marks': 2.0}
        fake_questions = [
            {'id': 'q-201', 'question_text': 'Q201', 'option_a': 'Opt A', 'option_b': 'Opt B', 'option_c': 'Opt C', 'option_d': 'Opt D', 'correct_answer': 'B', 'marks': 1.0},
            {'id': 'q-202', 'question_text': 'Q202', 'option_a': 'Opt A', 'option_b': 'Opt B', 'option_c': 'Opt C', 'option_d': 'Opt D', 'correct_answer': 'D', 'marks': 1.0}
        ]

        with patch('app.database.repositories.attempt_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.attempt_repository.QuizRepository.get_by_id', return_value=fake_quiz):
                with patch('app.database.repositories.attempt_repository.QuestionRepository.get_by_quiz', return_value=fake_questions):
                    with patch('app.database.repositories.attempt_repository.StudentRepository.get_by_id', return_value={'id': 'stu-uuid-102'}):
                        # Empty answers submitted
                        AttemptRepository.submit_attempt('att-uuid-102', {})

                        inserted_answers = mock_answers_table.insert.call_args[0][0]
                        self.assertEqual(len(inserted_answers), 2)
                        for ans in inserted_answers:
                            self.assertIsNone(ans['selected_answer'])
                            self.assertEqual(ans['is_correct'], 0)
                            self.assertEqual(ans['marks_awarded'], 0.0)

                        att_update = mock_attempts_table.update.call_args[0][0]
                        self.assertEqual(att_update['attempted_questions'], 0)
                        self.assertEqual(att_update['correct_answers'], 0)
                        self.assertEqual(att_update['wrong_answers'], 0)
                        self.assertEqual(att_update['unattempted'], 2)
                        self.assertEqual(att_update['obtained_marks'], 0.0)
                        self.assertEqual(att_update['percentage'], 0.0)
                        self.assertEqual(att_update['status'], 'FAIL')

    def test_submit_attempt_adaptive_fallback_to_boolean_if_schema_requires_it(self):
        """
        Verify that if Supabase throws a 42804 / boolean mismatch error,
        it automatically retries with boolean values.
        """
        from app.database.repositories.attempt_repository import AttemptRepository

        mock_supabase = MagicMock()
        mock_attempts_table = MagicMock()
        mock_answers_table = MagicMock()

        attempt_row = {
            'id': 'att-uuid-103',
            'quiz_id': 'quiz-uuid-103',
            'student_id': 'stu-uuid-103',
            'status': 'in_progress'
        }

        mock_attempts_table.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=attempt_row)
        mock_attempts_table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[attempt_row])
        mock_answers_table.delete.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        # First insert fails with 42804 boolean type error, second insert succeeds
        mock_answers_table.insert.side_effect = [
            Exception({'message': 'column "is_correct" is of type boolean but expression is of type integer', 'code': '42804'}),
            MagicMock(data=[])
        ]
        mock_answers_table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

        def table_router(table_name):
            if table_name == 'attempts': return mock_attempts_table
            elif table_name == 'answers': return mock_answers_table
            return MagicMock()

        mock_supabase.table.side_effect = table_router

        fake_quiz = {'id': 'quiz-uuid-103', 'title': 'Test Quiz 3', 'pass_percentage': 50.0}
        fake_questions = [{'id': 'q-301', 'question_text': 'Q301', 'option_a': 'Opt A', 'option_b': 'Opt B', 'option_c': 'Opt C', 'option_d': 'Opt D', 'correct_answer': 'A', 'marks': 2.0}]

        with patch('app.database.repositories.attempt_repository.get_supabase_client', return_value=mock_supabase):
            with patch('app.database.repositories.attempt_repository.QuizRepository.get_by_id', return_value=fake_quiz):
                with patch('app.database.repositories.attempt_repository.QuestionRepository.get_by_quiz', return_value=fake_questions):
                    with patch('app.database.repositories.attempt_repository.StudentRepository.get_by_id', return_value={'id': 'stu-uuid-103'}):
                        AttemptRepository.submit_attempt('att-uuid-103', {'q-301': 'A'})

                        # Verify insert was called twice (first integer, then boolean fallback)
                        self.assertEqual(mock_answers_table.insert.call_count, 2)
                        fallback_payload = mock_answers_table.insert.call_args_list[1][0][0]
                        self.assertIs(fallback_payload[0]['is_correct'], True)

    def test_api_student_submit_quiz_endpoint(self):
        """
        Integration test: Verify POST /api/student/submit-quiz processes answers,
        updates scorecard, and returns HTTP 200 with result payload.
        """
        from app.database.repositories.student_repository import StudentRepository
        from app.services.quiz_service import QuizService
        from app.services.question_service import QuestionService
        from app.database.repositories.attempt_repository import AttemptRepository

        # Register a test student
        roll = f"SUBMIT_{int(datetime.datetime.now().timestamp()) % 100000}"
        student = StudentRepository.create_or_login({
            'full_name': 'Submission Test Student',
            'roll_number': roll,
            'class_name': 'TE Computer',
            'division': 'A',
            'department': 'Computer Engineering',
            'email': f'{roll.lower()}@college.edu'
        })
        self.assertIsNotNone(student)

        # Create test quiz
        subjects = SubjectRepository.get_all()
        sub_id = subjects[0]['id']
        quiz = QuizService.create_quiz({
            'title': f'Submit Endpoint Quiz {roll}',
            'subject_id': sub_id,
            'unit_number': 1,
            'duration_minutes': 15,
            'total_marks': 2.0,
            'passing_percentage': 40.0
        })

        # Add a question first
        question = QuestionService.create_question({
            'quiz_id': quiz['id'],
            'question_text': 'What does SQL stand for?',
            'option_a': 'Structured Query Language',
            'option_b': 'Simple Query Language',
            'option_c': 'Standard Query List',
            'option_d': 'Sequential Query Logic',
            'correct_answer': 'A',
            'marks': 2.0
        })

        # Now publish the quiz
        QuizRepository.toggle_publish(quiz['id'], True)

        # Start attempt
        attempt, is_completed = AttemptRepository.start_or_resume_attempt(quiz['id'], student['id'])
        self.assertFalse(is_completed)

        # Submit via client session
        with self.client.session_transaction() as sess:
            sess['student'] = student
            sess['student_id'] = student['id']

        response = self.client.post('/api/student/submit-quiz', json={
            'attemptId': attempt['id'],
            'answers': {
                question['id']: 'A'
            }
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['attemptId'], attempt['id'])
        self.assertEqual(data['result']['obtained_marks'], 2.0)
        self.assertEqual(data['result']['percentage'], 100.0)
        self.assertEqual(data['result']['status'], 'PASS')

    def test_faculty_admin_pages_render_content_not_blank(self):
        """
        Verify that /admin/students, /admin/analytics, /admin/downloads, and /admin/settings
        render their full content inside .admin-content rather than rendering a blank page.
        """
        with self.client.session_transaction() as sess:
            sess['faculty'] = {'username': 'admin', 'name': 'Prof. Test'}

        # 1. Student Registry
        res_students = self.client.get('/admin/students')
        self.assertEqual(res_students.status_code, 200)
        html_students = res_students.get_data(as_text=True)
        self.assertIn('Student Management', html_students)
        self.assertIn('Enrollment Registry', html_students)
        self.assertNotIn('<div class="admin-content">\n        \n      </div>', html_students)
        self.assertGreater(len(html_students), 4500)

        # 2. Performance Analytics
        res_analytics = self.client.get('/admin/analytics')
        self.assertEqual(res_analytics.status_code, 200)
        html_analytics = res_analytics.get_data(as_text=True)
        self.assertIn('Performance Analytics Dashboard', html_analytics)
        self.assertNotIn('<div class="admin-content">\n        \n      </div>', html_analytics)
        self.assertGreater(len(html_analytics), 4500)

        # 3. Downloads / Reports
        res_downloads = self.client.get('/admin/downloads')
        self.assertEqual(res_downloads.status_code, 200)
        html_downloads = res_downloads.get_data(as_text=True)
        self.assertIn('Institutional Data Export Center', html_downloads)
        self.assertIn('handleDownloadStudentResultsCsv', html_downloads)
        self.assertNotIn('<div class="admin-content">\n        \n      </div>', html_downloads)
        self.assertGreater(len(html_downloads), 4500)

        # 4. Settings
        res_settings = self.client.get('/admin/settings')
        self.assertEqual(res_settings.status_code, 200)
        html_settings = res_settings.get_data(as_text=True)
        self.assertIn('Portal & Institutional Settings', html_settings)
        self.assertIn('Institutional Identity', html_settings)
        # Ensure no secrets leaked
        self.assertNotIn('SUPABASE_KEY', html_settings)
        self.assertNotIn('SUPABASE_SERVICE_ROLE_KEY', html_settings)
        self.assertNotIn('FACULTY_PASSWORD', html_settings)
        self.assertNotIn('pbkdf2:sha256', html_settings)
        self.assertNotIn('<div class="admin-content">\n        \n      </div>', html_settings)
        self.assertGreater(len(html_settings), 4500)

    def test_faculty_student_detail_page_renders_content(self):
        """Verify that /admin/students/<id> renders the candidate profile."""
        with self.client.session_transaction() as sess:
            sess['faculty'] = {'username': 'admin', 'name': 'Prof. Test'}

        # Get or create student
        students = StudentRepository.get_all()
        if not students:
            student = StudentRepository.create_or_login({
                'full_name': 'Profile Verification Student',
                'roll_number': 'PROF_001',
                'class_name': 'TE Computer',
                'division': 'A',
                'department': 'Computer Engineering'
            })
            student_id = student['id']
        else:
            student_id = students[0]['id']

        res = self.client.get(f'/admin/students/{student_id}')
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn('Back to All Students', html)
        self.assertIn('Completed Examination Records', html)
        self.assertNotIn('<div class="admin-content">\n        \n      </div>', html)

    def test_mobile_navbar_and_css_overflow_rules(self):
        """
        Verify style.css rules for mobile faculty topbar and shell overflow:
        - .admin-topbar .mobile-nav-toggle does not have margin-left: auto
        - table has max-width: 100% and min-width is scoped to overflow wrappers
        - no 100vw used in admin-shell/admin-viewport/admin-content
        """
        import os
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        css_path = os.path.join(base_dir, 'app', 'static', 'css', 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # 100vw should not be present in admin layout classes
        self.assertNotIn('max-width: 100vw', css_content)

        # .admin-topbar .mobile-nav-toggle should have margin: 0 !important
        self.assertIn('.admin-topbar .mobile-nav-toggle', css_content)
        self.assertIn('margin: 0 !important;', css_content)

        # Responsive table check
        self.assertIn('.table-responsive > table', css_content)
        self.assertIn('.overflow-x-auto > table', css_content)

    def test_all_faculty_and_student_routes_render_cleanly(self):
        """
        Verify that all core admin and student routes render cleanly with HTTP 200:
        - Faculty Dashboard
        - Create Quiz
        - Manage Quizzes
        - Question Bank
        - Results & Rankings
        - Student Login
        - Student Dashboard
        - Settings 5 structured cards
        """
        with self.client.session_transaction() as sess:
            sess['faculty'] = {'username': 'admin', 'name': 'Prof. Test'}

        # Faculty Dashboard
        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Welcome, Faculty', res.get_data(as_text=True))

        # Create Quiz
        res = self.client.get('/admin/quizzes/new')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Create New Quiz', res.get_data(as_text=True))

        # Manage Quizzes
        res = self.client.get('/admin/quizzes')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Quiz Management', res.get_data(as_text=True))

        # Question Bank
        res = self.client.get('/admin/questions')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Question Bank', res.get_data(as_text=True))

        # Results & Rankings
        res = self.client.get('/admin/results')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Results &', res.get_data(as_text=True))

        # Settings 5 cards verification
        res_settings = self.client.get('/admin/settings')
        self.assertEqual(res_settings.status_code, 200)
        html_set = res_settings.get_data(as_text=True)
        self.assertIn('Institutional Identity & Application Version', html_set)
        self.assertIn('Database Engine & Storage Status', html_set)
        self.assertIn('Security & Data Integrity', html_set)
        self.assertIn('Institutional Examination Parameters', html_set)
        self.assertIn('Session & Security Configuration', html_set)
        self.assertIn('OPERATIONAL', html_set)

        # Student Login Page
        res = self.client.get('/login/student')
        self.assertEqual(res.status_code, 200)
        self.assertIn('Student Examination Entry', res.get_data(as_text=True))

        # Student Dashboard
        students = StudentRepository.get_all()
        if students:
            st = students[0]
            with self.client.session_transaction() as s_sess:
                s_sess['student'] = st
                s_sess['student_id'] = st['id']
            res_st = self.client.get('/student/dashboard')
            self.assertEqual(res_st.status_code, 200)
            self.assertIn('Student Dashboard', res_st.get_data(as_text=True))

if __name__ == '__main__':
    unittest.main()
