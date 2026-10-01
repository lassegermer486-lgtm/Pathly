import pytest
import yaml

from scraper_ui.overrides_file import OverridesError, add_pair, remove_pair

ORIGINAL = """\
# Manuelle Entscheidungen.

# Dieselbe Hochschule -> zusammenführen.
merge:
  # HSD: eine Hochschule, Sitz Potsdam.
  - ["DE-BB|HSD Hochschule Döpfer GmbH", "DE-NW|HSD Hochschule Döpfer"]

# Verschiedene Hochschulen -> nie zusammenführen.
keep_separate:
  # Eigenständige evangelische Hochschulen.
  - ["DE-BY|Evangelische Hochschule Nürnberg", "DE-BE|Evangelische Hochschule Berlin"]

# Korrekturen pro university_id.
records: {}
"""


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "overrides.yaml"
    p.write_text(ORIGINAL, encoding="utf-8")
    return p


def test_add_keeps_comments_and_other_entries(path):
    assert add_pair(path, "merge", "DE-BW|SRH Heidelberg", "DE-TH|SRH Heidelberg in Gera", "Campus laut Website")
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    assert data["merge"][-1] == ["DE-BW|SRH Heidelberg", "DE-TH|SRH Heidelberg in Gera"]
    assert len(data["merge"]) == 2 and len(data["keep_separate"]) == 1 and data["records"] == {}
    for comment in ("# HSD: eine Hochschule, Sitz Potsdam.", "# Verschiedene Hochschulen -> nie zusammenführen.",
                    "# Korrekturen pro university_id."):
        assert comment in text
    assert "Campus laut Website" in text
    # The new entry sits inside the merge block, before the next section's comment.
    assert text.index("SRH Heidelberg") < text.index("# Verschiedene Hochschulen")


def test_add_twice_is_a_noop(path):
    assert add_pair(path, "keep_separate", "A|x", "B|y")
    assert not add_pair(path, "keep_separate", "B|y", "A|x")
    assert len(yaml.safe_load(path.read_text(encoding="utf-8"))["keep_separate"]) == 2


def test_remove_restores_the_original_file(path):
    add_pair(path, "merge", "A|x", "B|y", "Notiz")
    assert remove_pair(path, "merge", "B|y", "A|x")
    assert path.read_text(encoding="utf-8") == ORIGINAL
    assert not remove_pair(path, "merge", "A|x", "B|y")


def test_names_with_special_characters_round_trip(path):
    a = 'DE-HH|Hochschule "Macromedia", University of Applied Science **'
    b = "DE-HH|NORDAKADEMIE Hochschule der Wirtschaft | Graduate School: #1"
    add_pair(path, "merge", a, b)
    assert [a, b] in yaml.safe_load(path.read_text(encoding="utf-8"))["merge"]
    assert remove_pair(path, "merge", a, b)
    assert path.read_text(encoding="utf-8") == ORIGINAL


def test_empty_and_missing_sections(tmp_path):
    p = tmp_path / "overrides.yaml"
    p.write_text("merge: []\nrecords: {}\n", encoding="utf-8")
    add_pair(p, "merge", "A|x", "B|y")
    add_pair(p, "keep_separate", "C|x", "D|y")
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert data == {"merge": [["A|x", "B|y"]], "keep_separate": [["C|x", "D|y"]], "records": {}}


def test_missing_file_is_created(tmp_path):
    p = tmp_path / "config" / "overrides.yaml"
    add_pair(p, "merge", "A|x", "B|y")
    assert yaml.safe_load(p.read_text(encoding="utf-8"))["merge"] == [["A|x", "B|y"]]


def test_inline_list_is_refused_without_writing(tmp_path):
    p = tmp_path / "overrides.yaml"
    content = 'merge: [["A|x", "B|y"]]\n'
    p.write_text(content, encoding="utf-8")
    with pytest.raises(OverridesError):
        add_pair(p, "merge", "C|x", "D|y")
    assert p.read_text(encoding="utf-8") == content
