from enum import StrEnum


class ExplanationCategory(StrEnum):
    """The explanation pass's verdict on a move (D6). UNEXPLAINED is a first-class answer."""

    COMPANY = "company"
    INDUSTRY = "industry"
    MACRO = "macro"
    UNEXPLAINED = "unexplained"
