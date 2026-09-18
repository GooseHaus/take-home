from app.errors.app_error import AppError


class TickerNotIngested(AppError):
    """The ticker is well-formed but nothing has been ingested for it yet."""

    status_code = 404
    code = "ticker_not_ingested"
