from app.errors.app_error import AppError


class MovementNotFound(AppError):
    status_code = 404
    code = "movement_not_found"
