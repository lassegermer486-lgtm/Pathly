from registry.normalize import is_host_within, is_social_media_url
from registry.utils.matching import match_name


def test_host_within_is_not_a_substring_check():
    assert is_host_within("https://www.berlin.de/sen/", "berlin.de")
    assert is_host_within("https://service.berlin.de/app/", "berlin.de")
    assert not is_host_within("http://www.fu-berlin.de", "berlin.de")
    assert not is_host_within("https://www.uni-saarland.de/start/", "saarland.de")
    assert not is_host_within("http://www.hfm.saarland.de/", "www.saarland.de")


def test_social_media_url():
    assert is_social_media_url("https://www.instagram.com/tu.braunschweig/")
    assert not is_social_media_url("https://www.tu-braunschweig.de/")


# Pairs observed between the Thüringen statistics table and
# campus-thueringen.de.
THUERINGEN_PORTAL = [
    "Universität Erfurt",
    "Fach\xadhoch\xadschule Erfurt",
    "Technische Univer\xadsität Ilmenau",
    "Hochschule für Musik FRANZ LISZT Weimar",
    "Duale Hochschule Gera-Eisenach",
    "HMU Health and Medical University (privat)",
    "IU Inter\xadnatio\xadnale Hochschule - Campus Erfurt (privat)",
    "SRH University (privat)",
    "iba | Inter\xadnatio\xadnale Berufs\xadaka\xaddemie - Standort Erfurt (privat)",
]


def test_match_name_links_spelling_variants():
    assert match_name("Fachhochschule Erfurt", THUERINGEN_PORTAL) == "Fach\xadhoch\xadschule Erfurt"
    assert match_name("Duale Hochschule Eisenach-Gera", THUERINGEN_PORTAL) == "Duale Hochschule Gera-Eisenach"
    assert match_name("HMU Health and Medical University Erfurt", THUERINGEN_PORTAL) == "HMU Health and Medical University (privat)"
    assert match_name("SRH University of Applied Sciences Heidelberg in Gera", THUERINGEN_PORTAL) == "SRH University (privat)"
    assert match_name("Hochschule für Musik Franz Liszt Weimar", THUERINGEN_PORTAL) == "Hochschule für Musik FRANZ LISZT Weimar"


def test_match_name_keeps_type_words_apart():
    # Same city, different institution type.
    assert match_name("Universität Erfurt", THUERINGEN_PORTAL) == "Universität Erfurt"
    assert match_name("Universität Erfurt", ["Fachhochschule Erfurt"]) is None
    # A city page must never match an institution.
    assert match_name("Universität Erfurt", ["Erfurt"]) is None
    # No portal entry at all.
    assert match_name("Thüringer Fachhochschule für öffentliche Verwaltung Gotha", THUERINGEN_PORTAL) is None


def test_match_name_generic_tokens_are_not_evidence():
    assert match_name(
        "Evangelische Hochschule Berlin",
        ["Evangelische Hochschule Dresden"],
    ) is None
    assert match_name(
        "Hochschule für Musik Saar",
        ["Hochschule der Bildenden Künste Saar"],
    ) is None


def test_match_name_refuses_ties():
    assert match_name(
        "Hochschule Beispielstadt",
        ["Hochschule Beispielstadt Nord", "Hochschule Beispielstadt Süd"],
    ) is None
