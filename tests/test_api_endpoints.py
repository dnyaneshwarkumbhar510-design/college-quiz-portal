import os
import sys
import json
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.question_repository import QuestionRepository
from config import Config

class TestFlaskAPIAndPageRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()

    def test_public_pages_status_200(self):
        """Verify that public entry pages render properly."""
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/login/student')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/login/admin')
        self.assertEqual(r.status_code, 200)

    def test_faculty_login_and_admin_pages(self):
        """Verify faculty login and access to admin portals."""
        # Authenticate using Config.ADMIN_EMAIL and Config.ADMIN_PASSWORD
        res = self.client.post('/api/auth/admin-login', json={
            'email': Config.ADMIN_EMAIL,
            'password': Config.ADMIN_PASSWORD
        })
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])

        # Check /api/auth/me
        me_res = self.client.get('/api/auth/me')
        self.assertEqual(me_res.status_code, 200)
        me_data = json.loads(me_res.data)
        self.assertTrue(me_data['isAuthenticated'])
        self.assertIsNotNone(me_data['faculty'])

        # Check Admin HTML Pages
        for route in ['/admin/dashboard', '/admin/quizzes', '/admin/quizzes/new',
                      '/admin/questions', '/admin/results', '/admin/analytics',
                      '/admin/students', '/admin/downloads', '/admin/settings']:
            page_res = self.client.get(route)
            self.assertEqual(page_res.status_code, 200, f"Route {route} failed with status {page_res.status_code}")

    def test_student_lifecycle_api(self):
        """Verify student registration, starting exam, submitting, and receiving result via REST API."""
        # 1. Register student via /api/auth/student-login
        client = self.app.test_client()
        reg_res = client.post('/api/auth/student-login', json={
            'full_name': 'Grace Hopper',
            'roll_number': 'CS-API-101',
            'division': 'B',
            'class_name': 'Third Year',
            'department': 'CSE',
            'email': 'grace.hopper@college.edu'
        })
        self.assertEqual(reg_res.status_code, 200)
        reg_data = json.loads(reg_res.data)
        self.assertTrue(reg_data['success'])
        student_id = reg_data['student']['id']

        # 2. Check student me / profile
        prof_res = client.get('/api/student/profile')
        self.assertEqual(prof_res.status_code, 200)
        prof_data = json.loads(prof_res.data)
        self.assertEqual(prof_data['student']['id'], student_id)

        # 3. Check student dashboard page
        dash_res = client.get('/student/dashboard')
        self.assertEqual(dash_res.status_code, 200)

        # 4. Create and publish a quiz using admin client
        admin_client = self.app.test_client()
        admin_client.post('/api/auth/admin-login', json={
            'email': Config.ADMIN_EMAIL,
            'password': Config.ADMIN_PASSWORD
        })
        
        subjects = SubjectRepository.get_all()
        sub_id = subjects[0]['id'] if subjects else 'default-sub'

        create_quiz_res = admin_client.post('/api/faculty/quizzes', json={
            'title': 'Compiler Design Unit 1',
            'subject_id': sub_id,
            'unit_number': 1,
            'duration': 15,
            'total_questions': 2,
            'marks_per_question': 1,
            'pass_percentage': 40.0,
            'is_published': True
        })
        self.assertEqual(create_quiz_res.status_code, 201)
        quiz_data = json.loads(create_quiz_res.data)
        quiz_id = quiz_data['quiz']['id']

        # Add 2 questions to the quiz via /api/faculty/quizzes/<id>/questions
        q1_res = admin_client.post(f'/api/faculty/quizzes/{quiz_id}/questions', json={
            'question_text': 'What is Lexical Analysis?',
            'option_a': 'Token generation',
            'option_b': 'Syntax tree generation',
            'option_c': 'Code generation',
            'option_d': 'Optimization',
            'correct_answer': 'A',
            'marks': 1,
            'explanation': 'Lexical analysis breaks input characters into tokens.'
        })
        self.assertEqual(q1_res.status_code, 201)
        q1_id = json.loads(q1_res.data)['question']['id']

        q2_res = admin_client.post(f'/api/faculty/quizzes/{quiz_id}/questions', json={
            'question_text': 'What data structure is used for syntax parsing?',
            'option_a': 'Queue',
            'option_b': 'Parse Tree',
            'option_c': 'Graph',
            'option_d': 'Hash Table',
            'correct_answer': 'B',
            'marks': 1,
            'explanation': 'Syntax analysis builds parse trees.'
        })
        self.assertEqual(q2_res.status_code, 201)
        q2_id = json.loads(q2_res.data)['question']['id']

        # 5. Student fetches published quizzes
        quizzes_res = client.get('/api/student/quizzes')
        self.assertEqual(quizzes_res.status_code, 200)

        # 6. Student starts quiz via POST /api/student/quizzes/<quiz_id>/start
        start_res = client.post(f'/api/student/quizzes/{quiz_id}/start')
        self.assertEqual(start_res.status_code, 200)
        start_data = json.loads(start_res.data)
        self.assertTrue(start_data['success'])
        attempt_id = start_data['attempt']['id']
        self.assertEqual(len(start_data['questions']), 2)

        # 7. Student submits answers via POST /api/student/attempts/<attempt_id>/submit
        submit_res = client.post(f'/api/student/attempts/{attempt_id}/submit', json={
            'answers': {
                str(q1_id): 'A', # Correct
                str(q2_id): 'B'  # Correct
            }
        })
        self.assertEqual(submit_res.status_code, 200)
        submit_data = json.loads(submit_res.data)
        self.assertTrue(submit_data['success'])
        self.assertEqual(submit_data['result']['percentage'], 100.0)
        self.assertEqual(submit_data['result']['status'], 'PASS')

        # 8. Student result page /student/results/<attempt_id>
        res_page = client.get(f'/student/results/{attempt_id}')
        self.assertEqual(res_page.status_code, 200)

        # 9. Faculty results API /api/faculty/results
        fac_results_res = admin_client.get('/api/faculty/results')
        self.assertEqual(fac_results_res.status_code, 200)

        # 10. Faculty analytics API /api/faculty/analytics
        fac_analytics_res = admin_client.get('/api/faculty/analytics')
        self.assertEqual(fac_analytics_res.status_code, 200)

if __name__ == '__main__':
    unittest.main()
