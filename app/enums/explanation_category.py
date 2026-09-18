from enum import StrEnum


class ExplanationCategory(StrEnum):
    """The explanation pass's verdict on a move (D6). UNEXPLAINED is a valid answer."""

    COMPANY = "company"
    INDUSTRY = "industry"
    MACRO = "macro"
    UNEXPLAINED = "unexplained"
