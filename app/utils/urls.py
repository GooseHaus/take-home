from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.constants.news import TRACKING_PARAM_PREFIXES, TRACKING_PARAMS


def _is_tracking(key: str) -> bool:
    key = key.lower()
    return key in TRACKING_PARAMS or key.startswith(TRACKING_PARAM_PREFIXES)


def normalize_url(url: str) -> str:
    """Article dedupe key: no fragment, no tracking params, lowercase host, no trailing slash."""
    parts = urlsplit(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _is_tracking(k)])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def source_domain(url: str) -> str | None:
    host = urlsplit(url).netloc.lower()
    return host.removeprefix("www.") or None
