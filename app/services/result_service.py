from app.database.repositories.attempt_repository import AttemptRepository

class ResultService:
    @staticmethod
    def get_attempt_details(attempt_id):
        return AttemptRepository.get_attempt_details(attempt_id)

    @staticmethod
    def submit_quiz(attempt_id, answers_dict):
        return AttemptRepository.submit_attempt(attempt_id, answers_dict)

    @staticmethod
    def get_admin_results(filters=None):
        return AttemptRepository.get_admin_results_table(filters)

    @staticmethod
    def get_overall_rankings(subject_id=None):
        return AttemptRepository.get_overall_rankings(subject_id)

    @staticmethod
    def get_unit_rankings(quiz_id):
        return AttemptRepository.get_unit_rankings(quiz_id)

    @staticmethod
    def get_admin_stats(unit_filter=None):
        return AttemptRepository.get_admin_dashboard_stats(unit_filter)
