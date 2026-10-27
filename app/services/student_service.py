from app.database.repositories.student_repository import StudentRepository
from app.database.repositories.attempt_repository import AttemptRepository
from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.subject_repository import SubjectRepository

class StudentService:
    @staticmethod
    def get_dashboard_data(student_id):
        student = StudentRepository.get_by_id(student_id)
        if not student:
            return None

        subjects = SubjectRepository.get_all()
        published_quizzes = QuizRepository.get_published()
        attempts = AttemptRepository.get_student_attempts(student_id)
        completed_attempts = [a for a in attempts if a.get('status') != 'in_progress']

        total_attempted = len(completed_attempts)
        avg_marks = 0.0
        avg_pct = 0.0
        best_score = 0.0
        latest_score = 0.0
        pass_count = 0

        if total_attempted > 0:
            sum_marks = sum(float(a.get('obtained_marks', 0.0)) for a in completed_attempts)
            sum_pct = sum(float(a.get('percentage', 0.0)) for a in completed_attempts)
            avg_marks = round(sum_marks / total_attempted, 1)
            avg_pct = round(sum_pct / total_attempted, 1)
            best_score = max(float(a.get('obtained_marks', 0.0)) for a in completed_attempts)
            latest_score = float(completed_attempts[0].get('obtained_marks', 0.0))
            pass_count = len([a for a in completed_attempts if a.get('status') == 'PASS'])

        # Enrich published quizzes with student's attempt status
        quiz_list = []
        for q in published_quizzes:
            q_copy = dict(q)
            # Find matching attempt for this quiz
            att = next((a for a in attempts if str(a.get('quiz_id')) == str(q['id'])), None)
            if att:
                q_copy['attempt_id'] = att['id']
                q_copy['has_attempted'] = att.get('status') != 'in_progress'
                q_copy['in_progress'] = att.get('status') == 'in_progress'
                q_copy['attempt_status'] = att.get('status')
                q_copy['obtained_marks'] = att.get('obtained_marks', 0.0)
                q_copy['percentage'] = att.get('percentage', 0.0)
            else:
                q_copy['has_attempted'] = False
                q_copy['in_progress'] = False
                q_copy['attempt_status'] = None
            quiz_list.append(q_copy)

        return {
            'student': student,
            'stats': {
                'totalAttempted': total_attempted,
                'avgMarks': avg_marks,
                'avgPercentage': avg_pct,
                'bestScore': best_score,
                'latestScore': latest_score,
                'passCount': pass_count
            },
            'subjects': subjects,
            'publishedQuizzes': quiz_list,
            'recentAttempts': completed_attempts[:5]
        }
