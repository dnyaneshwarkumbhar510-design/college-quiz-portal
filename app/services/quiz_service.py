from app.database.repositories.quiz_repository import QuizRepository
from app.database.repositories.subject_repository import SubjectRepository

class QuizService:
    @staticmethod
    def get_quizzes(subject_id=None):
        return QuizRepository.get_all(subject_id)

    @staticmethod
    def get_published_quizzes(subject_id=None):
        return QuizRepository.get_published(subject_id)

    @staticmethod
    def get_quiz(quiz_id):
        return QuizRepository.get_by_id(quiz_id)

    @staticmethod
    def create_quiz(data):
        # Auto-create or ensure subject exists
        subject_id = data.get('subject_id')
        subject_name = data.get('subject_name') or data.get('subject')
        if subject_name and (not subject_id or len(str(subject_id)) < 10):
            sub = SubjectRepository.get_or_create(
                code=subject_name[:5].upper(),
                name=subject_name,
                department=data.get('department', 'Computer Engineering'),
                class_name=data.get('class_name', 'TE Computer')
            )
            data['subject_id'] = sub['id']
            data['subject_name'] = sub['name']

        return QuizRepository.create_quiz(data)

    @staticmethod
    def update_quiz(quiz_id, data):
        return QuizRepository.update_quiz(quiz_id, data)

    @staticmethod
    def toggle_publish(quiz_id, is_published):
        return QuizRepository.toggle_publish(quiz_id, is_published)

    @staticmethod
    def delete_quiz(quiz_id):
        return QuizRepository.delete_quiz(quiz_id)
