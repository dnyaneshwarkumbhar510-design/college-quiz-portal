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
        # Ensure subject_id is resolved and validated against subjects table
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
        elif subject_id:
            # Validate that subject_id actually exists in the active database
            existing_sub = SubjectRepository.get_by_id(subject_id)
            if not existing_sub:
                all_subs = SubjectRepository.get_all()
                if all_subs:
                    data['subject_id'] = all_subs[0]['id']
                    data['subject_name'] = all_subs[0]['name']
                else:
                    sub = SubjectRepository.get_or_create(
                        code='CS301',
                        name='Data Structures & Algorithms',
                        department=data.get('department', 'Computer Engineering'),
                        class_name=data.get('class_name', 'TE Computer')
                    )
                    data['subject_id'] = sub['id']
                    data['subject_name'] = sub['name']
            else:
                data['subject_name'] = existing_sub.get('name')
        else:
            all_subs = SubjectRepository.get_all()
            if all_subs:
                data['subject_id'] = all_subs[0]['id']
                data['subject_name'] = all_subs[0]['name']
            else:
                sub = SubjectRepository.get_or_create(
                    code='CS301',
                    name='Data Structures & Algorithms',
                    department=data.get('department', 'Computer Engineering'),
                    class_name=data.get('class_name', 'TE Computer')
                )
                data['subject_id'] = sub['id']
                data['subject_name'] = sub['name']

        # Ensure unit_number is clamped to valid institutional range [1, 4]
        raw_unit = data.get('unit_number', 1)
        try:
            data['unit_number'] = max(1, min(4, int(raw_unit or 1)))
        except (ValueError, TypeError):
            data['unit_number'] = 1

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
