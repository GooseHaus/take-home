from enum import StrEnum


class NewsTier(StrEnum):
    """Which search tier surfaced an article."""

    COMPANY = "company"
    INDUSTRY = "industry"
    MACRO = "macro"
