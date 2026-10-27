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

if __name__ == '__main__':
    unittest.main()
