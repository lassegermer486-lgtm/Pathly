import os

import pytest

from registry.enrichment.agent_resolver import (
    AgentError,
    apply_result,
    load_dotenv,
    parse_answer,
    validate_answer,
)

from fakes import FakeResolver


def answer(url, canonical=None, lifecycle="active"):
    return {
        "official_url": url,
        "canonical_name": canonical,
        "lifecycle_status": lifecycle,
        "confidence": 0.9,
        "evidence": ["..."],
    }


def record(name, suggested_url=None, status="review"):
    return {
        "name": name,
        "state": "DE-NW",
        "official_url": None,
        "locations": [{"city": "Bielefeld"}],
        "website_resolution": {
            "status": status,
            "suggested_url": suggested_url,
            "flags": [],
        },
    }


HSBI = FakeResolver({
    "https://www.hsbi.de": (
        200,
        b"<html><head><title>Hochschule Bielefeld - HSBI</title></head>"
        b'<body><a href="/impressum">Impressum</a></body></html>',
    ),
    "https://www.hsbi.de/impressum": (200, b"<html><body>Hochschule Bielefeld</body></html>"),
})


def test_parse_answer_tolerates_code_fence():
    parsed = parse_answer(
        '```json\n{"official_url": null, "canonical_name": null, '
        '"lifecycle_status": "gone", "confidence": 0.1, "evidence": []}\n```'
    )
    assert parsed["lifecycle_status"] == "unknown"

    with pytest.raises(AgentError):
        parse_answer('{"official_url": "https://x.de"}')


def test_agent_url_accepted_when_site_confirms_source_name():
    result = validate_answer(
        record("Hochschule Bielefeld"),
        answer("https://www.hsbi.de"),
        HSBI,
    )
    assert result["accepted"]
    assert result["reason"] == "identity_confirmed"


def test_rename_needs_the_state_listed_url_to_forward_there():
    renamed = answer("https://www.hsbi.de", canonical="Hochschule Bielefeld", lifecycle="renamed")

    # fh-bielefeld.de (from the state source) forwards to hsbi.de.
    confirmed = validate_answer(
        record("Fachhochschule Bielefeld", suggested_url="https://www.hsbi.de"),
        renamed,
        HSBI,
    )
    assert confirmed["accepted"]
    assert confirmed["reason"] == "rename_confirmed_by_source_redirect"

    # The agent's claim alone is not enough.
    unconfirmed = validate_answer(
        record("Fachhochschule Bielefeld"),
        renamed,
        HSBI,
    )
    assert not unconfirmed["accepted"]


def test_rejected_agent_answer_never_fills_official_url():
    rec = record("Fachhochschule Bielefeld", status="unresolved")
    agent = {
        "model": "test",
        "answer": answer("https://www.hsbi.de"),
        "citations": [],
        "asked_at": "2026-10-01T00:00:00Z",
    }
    validation = validate_answer(rec, agent["answer"], HSBI)
    updated = apply_result(rec, agent, validation)

    assert updated["official_url"] is None
    assert updated["website_resolution"]["status"] == "review"
    assert updated["website_resolution"]["suggested_url"] == "https://www.hsbi.de"


def test_agent_without_url_is_not_accepted():
    assert validate_answer(record("X"), answer(None), HSBI)["reason"] == "agent_no_url"


def test_dotenv_does_not_override_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PATHLY_TEST_A=from_file\nPATHLY_TEST_B='quoted'\n# comment\n")
    monkeypatch.setenv("PATHLY_TEST_A", "from_env")
    monkeypatch.delenv("PATHLY_TEST_B", raising=False)

    load_dotenv(env)

    assert os.environ["PATHLY_TEST_A"] == "from_env"
    assert os.environ["PATHLY_TEST_B"] == "quoted"
