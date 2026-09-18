from app.errors.app_error import AppError


class ProviderError(AppError):
    """An external provider call failed (network, quota, bad response)."""

    status_code = 502
    code = "provider_error"
