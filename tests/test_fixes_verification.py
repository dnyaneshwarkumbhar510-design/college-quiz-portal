import unittest
import json
from unittest.mock import MagicMock, patch
from main import app
from config import Config
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.question_repository import QuestionRepository
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

if __name__ == '__main__':
    unittest.main()
