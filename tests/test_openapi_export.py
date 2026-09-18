import pytest
import yaml

from scripts.export_openapi import GROUPS, OUTPUT_DIR, build_files

FILES = build_files()


@pytest.mark.parametrize("filename", sorted(FILES))
def test_committed_spec_is_up_to_date(filename):
    committed = (OUTPUT_DIR / filename).read_text(encoding="utf-8")
    assert committed == FILES[filename], "Run `python -m scripts.export_openapi` and commit the result"


def test_full_spec_covers_every_route():
    spec = yaml.safe_load(FILES["openapi.yaml"])
    assert sorted(spec["paths"]) == [
        "/chat",
        "/chat/{conversation_id}",
        "/health",
        "/tickers",
        "/tickers/{ticker}",
        "/tickers/{ticker}/ingest",
        "/tickers/{ticker}/movements/{day}",
        "/tickers/{ticker}/status",
    ]


@pytest.mark.parametrize("filename, tag", sorted(GROUPS.items()))
def test_group_specs_are_self_contained(filename, tag):
    spec = yaml.safe_load(FILES[filename])
    assert spec["paths"] and all(tag in op["tags"] for ops in spec["paths"].values() for op in ops.values())

    text = FILES[filename]
    defined = set(spec["components"]["schemas"])
    referenced = {part.split("'")[0] for part in text.split("#/components/schemas/")[1:]}
    assert referenced <= defined  # every $ref resolves inside the file
    assert referenced == defined  # and nothing unused was carried along


def test_error_responses_are_documented():
    spec = yaml.safe_load(FILES["openapi.yaml"])
    ticker_get = spec["paths"]["/tickers/{ticker}"]["get"]["responses"]
    assert ticker_get["404"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorResponse")
    assert {"200", "202", "502", "503"} <= set(spec["paths"]["/tickers/{ticker}/ingest"]["post"]["responses"])
    assert {"404", "502", "503"} <= set(spec["paths"]["/chat"]["post"]["responses"])
