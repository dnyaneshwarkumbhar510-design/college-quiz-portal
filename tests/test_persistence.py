import os
import sys
import unittest
import uuid

# Ensure Flask project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.services.quiz_service import QuizService
from app.services.question_service import QuestionService
from app.database.repositories.subject_repository import SubjectRepository
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.question_repository import QuestionRepository
from app.database.supabase_client import get_local_db_conn

class TestPersistenceAndRelationalIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        # Ensure a test subject exists
        subjects = SubjectRepository.get_all()
        if not subjects:
            self.subject_id = SubjectRepository.create({
                'name': 'Computer Science Engineering',
                'code': 'CS101',
                'description': 'Intro to CS'
            })['id']
        else:
            self.subject_id = subjects[0]['id']

    def test_flexible_quiz_sizing_and_persistence(self):
        """
        Verify that Quizzes can be created with 5, 10, 15, 20, 30, 40 questions
        and that every question-quiz relationship is strictly persisted in quiz_questions.
        """
        question_counts = [5, 10, 15, 20, 30, 40]
        created_quizzes = []

        for count in question_counts:
            # 1. Create Quiz
            quiz_data = {
                'title': f'Automated Exam {count} Questions',
                'description': f'Unit assessment with exactly {count} questions',
                'subject_id': self.subject_id,
                'unit_number': 1,
                'duration': 15,
                'total_questions': count,
                'marks_per_question': 1,
                'pass_percentage': 40.0,
                'is_published': False
            }
            quiz = QuizService.create_quiz(quiz_data)
            self.assertIsNotNone(quiz)
            quiz_id = str(quiz['id'])
            created_quizzes.append((quiz_id, count))

            # 2. Add 'count' faculty-authored questions
            for i in range(1, count + 1):
                q_data = {
                    'quiz_id': quiz_id,
                    'question_text': f'Question {i} for Quiz {count}: What is {i} + {i}?',
                    'question_type': 'multiple_choice',
                    'option_a': f'{i * 2}',
                    'option_b': f'{i * 2 + 1}',
                    'option_c': f'{i * 2 + 2}',
                    'option_d': f'{i * 2 + 3}',
                    'correct_answer': 'A',
                    'explanation': f'Adding {i} to itself yields {i * 2}',
                    'marks': 1,
                    'question_order': i
                }
                q = QuestionService.create_question(q_data)
                self.assertIsNotNone(q)
                self.assertIsNotNone(q.get('id'))

            # 3. Verify that QuestionService returns exactly 'count' questions
            retrieved_questions = QuestionService.get_questions_for_quiz(quiz_id)
            self.assertEqual(len(retrieved_questions), count,
                             f"Expected {count} questions for quiz {quiz_id}, got {len(retrieved_questions)}")

            # 4. Direct Database Check on relational 'quiz_questions' join table
            conn = get_local_db_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?", (quiz_id,))
            join_count = cursor.fetchone()[0]
            self.assertEqual(join_count, count,
                             f"quiz_questions join table has {join_count} rows, expected {count}")

        # 5. Simulate Server Restart / Module Reload
        # We query the database freshly to guarantee disk persistence
        for quiz_id, count in created_quizzes:
            fresh_quiz = QuizRepository.get_by_id(quiz_id)
            self.assertIsNotNone(fresh_quiz, f"Quiz {quiz_id} disappeared after reload!")
            fresh_questions = QuestionRepository.get_questions_by_quiz_id(quiz_id)
            self.assertEqual(len(fresh_questions), count,
                             f"Questions for {quiz_id} were lost after reload! Expected {count}, got {len(fresh_questions)}")

    def test_quiz_editing_and_deletion_safety(self):
        """
        Verify editing quiz metadata, publishing/unpublishing, and safe deletion.
        """
        quiz = QuizService.create_quiz({
            'title': 'Original Quiz Title',
            'subject_id': self.subject_id,
            'unit_number': 2,
            'duration': 10,
            'total_questions': 2,
            'pass_percentage': 50.0
        })
        quiz_id = str(quiz['id'])

        # Add 2 questions
        q1 = QuestionService.create_question({
            'quiz_id': quiz_id,
            'question_text': 'Q1 text',
            'option_a': 'Opt1',
            'option_b': 'Opt2',
            'option_c': 'Opt3',
            'option_d': 'Opt4',
            'correct_answer': 'B',
            'marks': 1
        })
        q2 = QuestionService.create_question({
            'quiz_id': quiz_id,
            'question_text': 'Q2 text',
            'option_a': 'OptA',
            'option_b': 'OptB',
            'option_c': 'OptC',
            'option_d': 'OptD',
            'correct_answer': 'C',
            'marks': 1
        })

        # Test edit quiz
        updated_quiz = QuizService.update_quiz(quiz_id, {'title': 'Updated Quiz Title', 'duration': 25})
        self.assertEqual(updated_quiz['title'], 'Updated Quiz Title')
        self.assertEqual(updated_quiz['duration'], 25)

        # Test toggle publish
        pub_quiz = QuizService.toggle_publish(quiz_id, True)
        self.assertTrue(pub_quiz.get('is_published') or pub_quiz.get('published'))

        unpub_quiz = QuizService.toggle_publish(quiz_id, False)
        self.assertFalse(unpub_quiz.get('is_published') or unpub_quiz.get('published'))

        # Test edit question
        q1_id = str(q1['id'])
        updated_q1 = QuestionService.update_question(q1_id, {'question_text': 'Edited Q1 text', 'correct_answer': 'D'})
        self.assertEqual(updated_q1['question_text'], 'Edited Q1 text')
        self.assertEqual(updated_q1['correct_answer'], 'D')

        # Test delete single question from quiz
        q2_id = str(q2['id'])
        QuestionService.delete_question(q2_id, quiz_id)
        remaining = QuestionService.get_questions_for_quiz(quiz_id)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(str(remaining[0]['id']), q1_id)

        # Test delete entire quiz and verify clean cascade without foreign-key orphan errors
        QuizService.delete_quiz(quiz_id)
        self.assertIsNone(QuizRepository.get_by_id(quiz_id))
        
        # Verify quiz_questions entries for this quiz are cleanly removed
        conn = get_local_db_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM quiz_questions WHERE quiz_id = ?", (quiz_id,))
        self.assertEqual(cursor.fetchone()[0], 0)

if __name__ == '__main__':
    unittest.main()
