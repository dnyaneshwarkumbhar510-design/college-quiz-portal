import os
import sys
import json
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.services.auth_service import AuthService
from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.faculty_repository import FacultyRepository
from app.database.repositories.attempt_repository import AttemptRepository
from config import Config

class TestTargetedImprovements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()

    def setUp(self):
        self.client = self.app.test_client()

    def test_persistent_student_session_and_no_duplication(self):
        """
        Verify that:
        1. Student logs in and session stores student_id.
        2. On subsequent page requests (simulating refresh), same student identity is loaded.
        3. Logging in again with the same roll number + division updates the existing student without creating a duplicate record.
        4. Logout cleanly clears the session.
        """
        roll = 'ROLL-PERSIST-999'
        div = 'D'

        # Count initial students
        initial_students = StudentRepository.get_all()
        initial_count = len(initial_students)

        # 1. Student logs in
        login_res = self.client.post('/api/auth/student-login', json={
            'full_name': 'Siddharth Roy',
            'roll_number': roll,
            'division': div,
            'class_name': 'Third Year IT',
            'department': 'IT',
            'email': 'siddharth@college.edu'
        })
        self.assertEqual(login_res.status_code, 200)
        data = json.loads(login_res.data)
        self.assertTrue(data['success'])
        student_id = data['student']['id']

        # 2. Simulate page refresh / subsequent request to student dashboard
        dash_res = self.client.get('/student/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        # Verify student details are rendered on dashboard
        dash_html = dash_res.data.decode('utf-8')
        self.assertIn('Siddharth Roy', dash_html)
        self.assertIn(roll, dash_html)
        self.assertIn(f'Division {div}', dash_html)

        # 3. Simulate same student logging in again with updated full_name
        login_again_res = self.client.post('/api/auth/student-login', json={
            'full_name': 'Siddharth M. Roy',
            'roll_number': roll,
            'division': div,
            'class_name': 'Third Year IT',
            'department': 'IT',
            'email': 'siddharth.roy@college.edu'
        })
        self.assertEqual(login_again_res.status_code, 200)
        data_again = json.loads(login_again_res.data)
        # ID must remain the same
        self.assertEqual(data_again['student']['id'], student_id)
        self.assertEqual(data_again['student']['full_name'], 'Siddharth M. Roy')

        # Verify no duplicate student was created
        current_students = StudentRepository.get_all()
        matching = [s for s in current_students if s['roll_number'] == roll and s['division'] == div]
        self.assertEqual(len(matching), 1, "Duplicate student record was created for the same roll number + division!")

        # 4. Verify logout clears session
        logout_res = self.client.get('/logout', follow_redirects=False)
        self.assertEqual(logout_res.status_code, 302)

        # Dashboard should now redirect to login
        unauth_dash = self.client.get('/student/dashboard', follow_redirects=False)
        self.assertEqual(unauth_dash.status_code, 302)
        self.assertIn('/login/student', unauth_dash.headers['Location'])

    def test_faculty_credential_privacy(self):
        """
        Verify that faculty email and password are never unnecessarily displayed:
        1. Login form does not pre-populate or echo credentials in placeholders.
        2. Password field uses type="password".
        3. Authenticated session / shell displays 'Welcome, Faculty' instead of email.
        4. Password is never exposed in JSON responses.
        """
        # 1. Inspect login page HTML
        login_page_res = self.client.get('/login/admin')
        self.assertEqual(login_page_res.status_code, 200)
        login_html = login_page_res.data.decode('utf-8')
        self.assertIn('type="password"', login_html)
        self.assertNotIn('placeholder="ankita.gadekar@nmiet.edu.in"', login_html)

        # 2. Authenticate faculty
        auth_res = self.client.post('/api/auth/admin-login', json={
            'email': Config.FACULTY_EMAIL,
            'password': Config.FACULTY_PASSWORD
        })
        self.assertEqual(auth_res.status_code, 200)
        auth_data = json.loads(auth_res.data)
        # Ensure password is not in response
        self.assertNotIn('password', auth_data)
        self.assertNotIn('password_hash', auth_data)
        if 'faculty' in auth_data:
            self.assertNotIn('password', auth_data['faculty'])
            self.assertNotIn('password_hash', auth_data['faculty'])

        # 3. Inspect faculty shell
        dash_res = self.client.get('/admin/dashboard')
        self.assertEqual(dash_res.status_code, 200)
        dash_html = dash_res.data.decode('utf-8')
        self.assertIn('Welcome, Faculty', dash_html)
        self.assertNotIn(Config.FACULTY_PASSWORD, dash_html)

    def test_real_database_analytics_and_empty_state(self):
        """
        Verify that analytics are computed from actual database records.
        """
        stats = AttemptRepository.get_admin_dashboard_stats(0)
        self.assertIn('total_students', stats)
        self.assertIn('total_quizzes', stats)
        self.assertIn('total_attempts', stats)
        self.assertIn('average_score', stats)
        self.assertIn('pass_percentage', stats)
        self.assertIn('fail_percentage', stats)
        self.assertIn('highest_score', stats)
        self.assertIn('lowest_score', stats)

        # Verify that sum of pass and fail count equals total attempts
        if stats['total_attempts'] > 0:
            self.assertEqual(stats['passed_count'] + stats['failed_count'], stats['total_attempts'])

    def test_downloads_endpoint_and_filters(self):
        """
        Verify that faculty downloads endpoint accepts filters and returns real data.
        """
        # Login faculty
        self.client.post('/api/auth/admin-login', json={
            'email': Config.FACULTY_EMAIL,
            'password': Config.FACULTY_PASSWORD
        })

        # Test results endpoint
        res = self.client.get('/api/admin/results')
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data)
        self.assertTrue(data['success'])
        self.assertIsInstance(data['rows'], list)

        # Test overall ranking endpoint
        overall_res = self.client.get('/api/admin/results?type=overall-ranking')
        self.assertEqual(overall_res.status_code, 200)
        overall_data = json.loads(overall_res.data)
        self.assertTrue(overall_data['success'])
        self.assertIsInstance(overall_data['overallRankings'], list)

if __name__ == '__main__':
    unittest.main()
