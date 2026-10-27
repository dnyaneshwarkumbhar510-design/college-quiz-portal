from app.database.repositories.question_repository import QuestionRepository

class QuestionService:
    @staticmethod
    def get_questions_for_quiz(quiz_id):
        return QuestionRepository.get_by_quiz(quiz_id)

    @staticmethod
    def get_student_exam_questions(quiz_id):
        return QuestionRepository.get_student_exam_questions(quiz_id)

    @staticmethod
    def create_question(data):
        return QuestionRepository.create_question(data)

    @staticmethod
    def update_question(question_id, data):
        return QuestionRepository.update_question(question_id, data)

    @staticmethod
    def delete_question(question_id, quiz_id=None):
        return QuestionRepository.delete_question(question_id, quiz_id)
