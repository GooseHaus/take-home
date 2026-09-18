from enum import StrEnum


class ArticleScope(StrEnum):
    """Which of a movement's articles a response includes.

    Every search result is stored, but most are candidates the explanation rejected. CITED is the default so a
    response carries the evidence and not the whole search log.
    """

    CITED = "cited"
    ALL = "all"
    NONE = "none"
