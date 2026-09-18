from app.errors.app_error import AppError


class InvalidTicker(AppError):
    status_code = 422
    code = "invalid_ticker"
