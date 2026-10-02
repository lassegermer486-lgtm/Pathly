"""
Regression: rebuilding from the committed dedup output with the committed
id_registry.json must give every institution the ID it already has.
"""

import json
from pathlib import Path

import pytest

from registry.master.build import IdRegistry


MASTER = Path(__file__).resolve().parent.parent / "data" / "master"


def load(name):
    path = MASTER / name
    if not path.exists():
        pytest.skip(f"{path} not present")
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_institutions_keep_their_registry_ids():
    institutions = load("universities_dedup.json")
    ids = load("id_registry.json")
    master = load("universities_de_master.json")

    expected = {tuple(sorted(row["members"])): row["registry_id"] for row in master}

    # build() passes the chosen name; it is stored, but plays no part in matching.
    named = [{**i, "name": i["names"][0]} for i in institutions]
    assigned = IdRegistry(ids).assign(named, "2099-01-01T00:00:00+00:00")

    got = {
        tuple(sorted(i["members"])): assigned[i["cluster_id"]]["registry_id"]
        for i in institutions
    }

    assert got == expected
    assert len(set(got.values())) == len(got)


def test_stable_id_summary_counts_kept_new_merged_and_unlisted():
    from registry.master.build import stable_id_summary

    registry = IdRegistry({"ids": {
        "PTH-DE-0000000A": {"created_at": "1"},
        "PTH-DE-0000000B": {"created_at": "1", "alias_of": "PTH-DE-0000000A"},
        "PTH-DE-0000000C": {"created_at": "1"},
        "PTH-DE-0000000D": {"created_at": "2"},
    }})
    existing = {"PTH-DE-0000000A", "PTH-DE-0000000B", "PTH-DE-0000000C"}
    rows = [{"registry_id": "PTH-DE-0000000A"}, {"registry_id": "PTH-DE-0000000D"}]

    summary = stable_id_summary(existing, rows, registry)

    assert summary == {"existing": 3, "kept": 1, "new": 1, "merged": 1,
                       "unlisted": ["PTH-DE-0000000C"], "all_existing_kept": False}
