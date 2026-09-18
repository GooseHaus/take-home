"""Error responses declared on routes so they appear in the OpenAPI spec. The bodies come from the AppError handler."""

from app.schemas.api import ErrorResponse


def error(description: str) -> dict:
    return {"model": ErrorResponse, "description": description}


INVALID_TICKER = {422: error("The ticker is not a valid symbol, or a parameter failed validation")}
NOT_INGESTED = {404: error("Nothing has been ingested for this ticker")}
MOVEMENT_NOT_FOUND = {404: error("The ticker is not ingested, or it has no major movement on that date")}
CONVERSATION_NOT_FOUND = {404: error("No conversation with that id")}
PROVIDER_UNAVAILABLE = {
    502: error("An upstream provider (Exa or OpenAI) failed"),
    503: error("A required API key is not configured"),
}
