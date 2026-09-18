class AppError(Exception):
    """Base for errors the API should surface. Services raise these; one handler in app.main maps them to HTTP."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
