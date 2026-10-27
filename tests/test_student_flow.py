import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.services.quiz_service import QuizService
from app.services.question_service import QuestionService
from app.services.student_service import StudentService
from app.services.result_service import ResultService
from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.attempt_repository import AttemptRepository
from config import Config

class TestStudentFlowAndGrading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        subjects = SubjectRepository.get_all()
        if not subjects:
            self.subject_id = SubjectRepository.create({
                'name': 'Data Structures & Algorithms',
                'code': 'CS201',
                'description': 'DSA Core Course'
            })['id']
        else:
            self.subject_id = subjects[0]['id']

    def test_student_division_validation(self):
        """
        Verify that student registration enforces valid division from shared Config.DIVISIONS (A through Q).
        """
        # Valid divisions: test boundary values and middle values
        for div in ['A', 'B', 'M', 'Q']:
            self.assertIn(div, Config.DIVISIONS)
            student = StudentRepository.create_or_login({
                'full_name': f'Student Div {div}',
                'roll_number': f'ROLL-TEST-{div}',
                'division': div,
                'class_name': 'Third Year CSE',
                'department': 'CSE',
                'email': f'student_{div.lower()}@college.edu'
            })
            self.assertIsNotNone(student)
            self.assertEqual(student['division'], div)

    def test_quiz_attempt_evaluation_and_grading(self):
        """
        Test end-to-end examination attempt, automatic evaluation, marks, percentage, and pass/fail status.
        """
        # 1. Create a published 5-question quiz (pass mark: 40%)
        quiz = QuizService.create_quiz({
            'title': 'Operating Systems Mini-Quiz',
            'subject_id': self.subject_id,
            'unit_number': 1,
            'duration': 15,
            'total_questions': 5,
            'marks_per_question': 2, # 10 marks total
            'pass_percentage': 40.0,
            'is_published': True
        })
        quiz_id = str(quiz['id'])

        # Add 5 questions with defined correct answers
        # Q1: A, Q2: B, Q3: C, Q4: D, Q5: A
        created_q_ids = []
        answers_map = ['A', 'B', 'C', 'D', 'A']
        for idx, corr in enumerate(answers_map, 1):
            q = QuestionService.create_question({
                'quiz_id': quiz_id,
                'question_text': f'OS Question #{idx}',
                'option_a': 'Option Alpha',
                'option_b': 'Option Beta',
                'option_c': 'Option Gamma',
                'option_d': 'Option Delta',
                'correct_answer': corr,
                'explanation': f'Explanation for OS Q{idx}',
                'marks': 2,
                'question_order': idx
            })
            created_q_ids.append(str(q['id']))

        # 2. Register candidate
        student = StudentRepository.create_or_login({
            'full_name': 'Alice Wonder',
            'roll_number': 'OS-CAND-001',
            'division': 'A',
            'class_name': 'Final Year IT',
            'department': 'IT',
            'email': 'alice.wonder@college.edu'
        })
        student_id = str(student['id'])

        # 3. Candidate starts exam
        attempt, is_completed = AttemptRepository.start_or_resume_attempt(quiz_id, student_id)
        self.assertFalse(is_completed)
        attempt_id = str(attempt['id'])

        # Verify that questions delivered to student DO NOT contain correct answers or explanations
        exam_questions = QuestionService.get_student_exam_questions(quiz_id)
        self.assertEqual(len(exam_questions), 5)
        for eq in exam_questions:
            self.assertNotIn('correct_answer', eq)
            self.assertNotIn('explanation', eq)

        # 4. Scenario A: Student gets 3 correct out of 5 (6 marks out of 10 = 60% -> PASS)
        student_answers = {
            created_q_ids[0]: 'A', # Correct
            created_q_ids[1]: 'B', # Correct
            created_q_ids[2]: 'C', # Correct
            created_q_ids[3]: 'A', # Wrong (Correct is D)
            created_q_ids[4]: 'B'  # Wrong (Correct is A)
        }

        eval_result = ResultService.submit_quiz(attempt_id, student_answers)
        self.assertIsNotNone(eval_result)
        self.assertEqual(eval_result['total_questions'], 5)
        self.assertEqual(eval_result['correct_count'], 3)
        self.assertEqual(eval_result['wrong_count'], 2)
        self.assertEqual(eval_result['unattempted_count'], 0)
        self.assertEqual(eval_result['obtained_marks'], 6.0)
        self.assertEqual(eval_result['total_marks'], 10.0)
        self.assertEqual(eval_result['percentage'], 60.0)
        self.assertEqual(eval_result['status'], 'PASS')

        # 5. Verify Attempt Details & Answer Review
        details = ResultService.get_attempt_details(attempt_id)
        self.assertIsNotNone(details)
        self.assertEqual(len(details['answers']), 5)
        
        # Check that answer review now exposes correct answer and explanation post-submission
        for ans in details['answers']:
            self.assertIn('correct_answer', ans)
            self.assertIn('explanation', ans)
            self.assertIn('selected_option', ans)
            self.assertIn('is_correct', ans)

if __name__ == '__main__':
    unittest.main()
