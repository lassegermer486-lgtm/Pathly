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
