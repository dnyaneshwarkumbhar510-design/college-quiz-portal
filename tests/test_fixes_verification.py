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
        valid Supabase schema columns (no 'duration', 'total_questions', 'status',
        'published', 'created_by', 'subject', or 'updated_at').
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()

        expected_created_row = {
            'id': 'test-uuid-001',
            'subject_id': 'c0000000-0000-0000-0000-000000000001',
            'unit_number': 2,
            'unit_title': 'Unit 2 Topic',
            'title': 'Production Schema Verified Quiz',
            'description': 'Verified description',
            'class_name': 'TE Computer',
            'division': 'All',
            'department': 'Computer Engineering',
            'duration_minutes': 20,
            'question_count': 0,
            'total_marks': 15.0,
            'passing_percentage': 40.0,
            'is_published': False,
            'randomize_questions': False,
            'randomize_options': False,
            'created_at': '2026-10-27T00:00:00+00:00'
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
                'id', 'subject_id', 'unit_number', 'unit_title', 'title', 'description',
                'class_name', 'division', 'department', 'duration_minutes', 'question_count',
                'total_marks', 'passing_percentage', 'is_published', 'randomize_questions',
                'randomize_options', 'created_at'
            }

            for key in actual_payload.keys():
                self.assertIn(key, valid_supabase_quizzes_columns, f"Forbidden column '{key}' sent to Supabase quizzes table!")

            # Verify forbidden columns are absent
            self.assertNotIn('duration', actual_payload)
            self.assertNotIn('total_questions', actual_payload)
            self.assertNotIn('pass_percentage', actual_payload)
            self.assertNotIn('published', actual_payload)
            self.assertNotIn('status', actual_payload)
            self.assertNotIn('subject', actual_payload)
            self.assertNotIn('created_by', actual_payload)
            self.assertNotIn('updated_at', actual_payload)

            # Verify normalized return values
            self.assertEqual(created['duration'], 20)
            self.assertEqual(created['duration_minutes'], 20)
            self.assertEqual(created['total_questions'], 0)
            self.assertEqual(created['question_count'], 0)
            self.assertEqual(created['passing_percentage'], 40.0)
            self.assertEqual(created['pass_percentage'], 40.0)
            self.assertFalse(created['is_published'])
            self.assertFalse(created['published'])

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

    def test_subject_seeding_includes_created_at_and_matches_production_schema(self):
        """
        Verify that Supabase subject auto-seeding sends 'created_at' (NOT NULL in Supabase)
        and does NOT send 'updated_at' (does not exist in public.subjects schema).
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = MagicMock()
        mock_select = MagicMock()

        # Mock select check returning None (subject does not exist yet)
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=None)
        mock_execute.return_value = MagicMock(data=[])
        mock_insert.execute = mock_execute
        mock_table.insert.return_value = mock_insert
        mock_table.select = mock_select.select
        mock_supabase.table.return_value = mock_table

        SubjectRepository._seed_defaults_supabase(mock_supabase)

        # Ensure insert was called for default subjects
        self.assertGreaterEqual(mock_table.insert.call_count, 1)

        valid_subject_columns = {'id', 'code', 'name', 'department', 'class_name', 'description', 'created_at'}

        for call_args in mock_table.insert.call_args_list:
            payload = call_args[0][0]
            # Must contain created_at
            self.assertIn('created_at', payload, "Seed payload is missing 'created_at'!")
            self.assertIsNotNone(payload['created_at'])
            self.assertTrue(len(str(payload['created_at'])) > 10)

            # Must NOT contain updated_at
            self.assertNotIn('updated_at', payload, "Seed payload incorrectly contains 'updated_at' which does not exist in Supabase!")

            # Verify all keys are in valid production columns
            for col in payload.keys():
                self.assertIn(col, valid_subject_columns, f"Unexpected column '{col}' in subject seed payload!")

    def test_subject_get_or_create_supabase_payload_and_none_safety(self):
        """
        Verify that SubjectRepository.get_or_create:
        1. Includes 'created_at' in new_sub payload.
        2. Does NOT include 'updated_at'.
        3. Does NOT raise 'NoneType' object has no attribute 'data' when res is None or res.data is None.
        """
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_insert = MagicMock()

        # 1. Simulate maybe_single().execute() returning None safely without AttributeError
        mock_select.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = None

        new_subject_row = {
            'id': 'test-sub-uuid-999',
            'code': 'CS999',
            'name': 'Cloud Computing',
            'department': 'Computer Engineering',
            'class_name': 'TE Computer',
            'description': 'Distributed Systems and Cloud Architecture',
            'created_at': '2026-10-27T10:00:00+00:00'
        }
        mock_insert.insert.return_value.execute.return_value = MagicMock(data=[new_subject_row])
        mock_table.select = mock_select.select
        mock_table.insert = mock_insert.insert
        mock_supabase.table.return_value = mock_table

        with patch('app.database.repositories.subject_repository.get_supabase_client', return_value=mock_supabase):
            sub = SubjectRepository.get_or_create(
                code='CS999',
                name='Cloud Computing',
                department='Computer Engineering',
                class_name='TE Computer',
                description='Distributed Systems and Cloud Architecture'
            )

            # Verify table called was subjects
            mock_supabase.table.assert_any_call('subjects')

            # Verify insert payload
            insert_call_args = mock_insert.insert.call_args[0][0]
            self.assertIn('created_at', insert_call_args, "new_sub is missing 'created_at'!")
            self.assertIsNotNone(insert_call_args['created_at'])
            self.assertNotIn('updated_at', insert_call_args, "new_sub must not contain 'updated_at' for Supabase!")

            self.assertEqual(sub['code'], 'CS999')
            self.assertEqual(sub['name'], 'Cloud Computing')

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

if __name__ == '__main__':
    unittest.main()
