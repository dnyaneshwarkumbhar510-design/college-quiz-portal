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
            sub_code = (data.get('subject_code') or subject_name[:8]).strip().upper()
            sub = SubjectRepository.get_or_create(
                code=sub_code,
                name=subject_name.strip(),
                department=data.get('department', 'Computer Engineering'),
                class_name=data.get('class_name', 'TE Computer')
            )
            if not sub or not sub.get('id'):
                raise RuntimeError(f"Could not resolve or create subject record for '{subject_name}'")
            data['subject_id'] = str(sub['id'])
            data['subject_name'] = sub.get('name') or subject_name
        elif subject_id:
            # Validate that subject_id actually exists in the active database
            existing_sub = SubjectRepository.get_by_id(subject_id)
            if not existing_sub:
                all_subs = SubjectRepository.get_all()
                if all_subs:
                    data['subject_id'] = str(all_subs[0]['id'])
                    data['subject_name'] = all_subs[0]['name']
                else:
                    sub = SubjectRepository.get_or_create(
                        code='CS301',
                        name='Data Structures & Algorithms',
                        department=data.get('department', 'Computer Engineering'),
                        class_name=data.get('class_name', 'TE Computer')
                    )
                    data['subject_id'] = str(sub['id'])
                    data['subject_name'] = sub['name']
            else:
                data['subject_id'] = str(existing_sub['id'])
                data['subject_name'] = existing_sub.get('name')
        else:
            all_subs = SubjectRepository.get_all()
            if all_subs:
                data['subject_id'] = str(all_subs[0]['id'])
                data['subject_name'] = all_subs[0]['name']
            else:
                sub = SubjectRepository.get_or_create(
                    code='CS301',
                    name='Data Structures & Algorithms',
                    department=data.get('department', 'Computer Engineering'),
                    class_name=data.get('class_name', 'TE Computer')
                )
                data['subject_id'] = str(sub['id'])
                data['subject_name'] = sub['name']

        # Ensure unit_number is clamped to valid institutional range [1, 4]
        raw_unit = data.get('unit_number', 1)
        try:
            data['unit_number'] = max(1, min(4, int(raw_unit or 1)))
        except (ValueError, TypeError):
            data['unit_number'] = 1

        # Ensure duration is a valid positive integer
        raw_dur = data.get('duration_minutes') or data.get('duration') or 15
        try:
            data['duration'] = max(1, int(raw_dur))
            data['duration_minutes'] = data['duration']
        except (ValueError, TypeError):
            data['duration'] = 15
            data['duration_minutes'] = 15

        # Ensure total_marks is a valid non-negative float
        raw_tm = data.get('total_marks', 0)
        try:
            data['total_marks'] = max(0.0, float(raw_tm))
        except (ValueError, TypeError):
            data['total_marks'] = 0.0

        # Ensure pass_percentage is a valid float
        raw_pass = data.get('passing_percentage') or data.get('pass_percentage') or 40.0
        try:
            data['pass_percentage'] = max(1.0, min(100.0, float(raw_pass)))
            data['passing_percentage'] = data['pass_percentage']
        except (ValueError, TypeError):
            data['pass_percentage'] = 40.0
            data['passing_percentage'] = 40.0

        # Sanitize flags
        data['randomize_questions'] = bool(data.get('randomize_questions', False))
        data['randomize_options'] = bool(data.get('randomize_options', False))
        if 'is_published' in data or 'published' in data:
            pub = bool(data.get('is_published') if 'is_published' in data else data.get('published', False))
            data['is_published'] = pub
            data['published'] = pub

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
