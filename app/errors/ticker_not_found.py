from app.errors.app_error import AppError


class TickerNotFound(AppError):
    """The market-data provider returned no price history for the ticker."""

    status_code = 404
    code = "ticker_not_found"
