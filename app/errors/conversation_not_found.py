from app.errors.app_error import AppError


class ConversationNotFound(AppError):
    status_code = 404
    code = "conversation_not_found"
