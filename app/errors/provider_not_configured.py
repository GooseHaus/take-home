from app.errors.app_error import AppError


class ProviderNotConfigured(AppError):
    """An external provider is needed but its API key is missing."""

    status_code = 503
    code = "provider_not_configured"
