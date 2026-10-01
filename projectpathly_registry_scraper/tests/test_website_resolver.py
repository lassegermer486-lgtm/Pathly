from bs4 import BeautifulSoup

from registry.enrichment.website_resolver import (
    FetchResult,
    explicit_acronyms,
    generate_candidates,
    name_variants,
    score_identity,
)
from registry.normalize import normalize_url

from fakes import FakeResolver


def domains(record, known_cities=frozenset()):
    return [c.domain for c in generate_candidates(record, known_cities)]


def record(name, city=None, url=None):
    return {
        "name": name,
        "state": "DE-XX",
        "official_url": url,
        "locations": [{"city": city}],
    }


# ----------------------------------------------------------------------
# Candidate generation (spec §12–§16)
# ----------------------------------------------------------------------

def test_candidates_spec_examples():
    tum = domains(record("Technische Universität München", "München"))
    assert tum[:4] == [
        "tu-muenchen.de",
        "tu-münchen.de",
        "technische-universitaet-muenchen.de",
        "technische-universität-münchen.de",
    ]
    assert "tum.de" in tum

    hm = domains(record("Hochschule München", "München"))
    assert {"hochschule-muenchen.de", "hochschule-münchen.de", "hs-muenchen.de", "hm.de"} <= set(hm)


def test_source_acronym_comes_first_and_replaces_initials():
    bht = domains(record("Berliner Hochschule für Technik (BHT)", "Berlin"))
    assert bht[:2] == ["bht-berlin.de", "bht.de"]
    # No made-up initials ("bhft") when the source names an acronym.
    assert not any(d.startswith("bhf") for d in bht)


def test_known_city_inside_name_is_a_place():
    hsba = domains(
        record("HSBA Hamburg School of Business Administration"),
        known_cities=frozenset({"hamburg"}),
    )
    assert hsba[:2] == ["hsba-hamburg.de", "hsba.de"]
    # "Administration" is not a place.
    assert "hsba-administration.de" not in hsba


def test_explicit_acronyms_skip_annotations():
    assert explicit_acronyms("SRH University (privat)") == ["SRH"]
    assert explicit_acronyms("Hochschule Beispiel (FH)") == []
    assert explicit_acronyms("ISBA gGmbH Internationale Studien- und Berufsakademie") == ["ISBA"]


def test_name_variants_need_a_distinctive_word():
    # Generic words alone never identify an institution (spec §28).
    assert name_variants("Evangelische Hochschule Berlin", ["Berlin"]) == [
        "evangelische hochschule berlin"
    ]
    assert "deutsche hochschule polizei" in name_variants(
        "Deutsche Hochschule der Polizei Münster", ["Münster"]
    )
    assert "universitaet luebeck" in name_variants("Universität zu Lübeck")


# ----------------------------------------------------------------------
# Identity (spec §18–§20)
# ----------------------------------------------------------------------

def page(title, body=""):
    return BeautifulSoup(
        f"<html><head><title>{title}</title></head><body>{body}</body></html>",
        "html.parser",
    )


def test_identity_needs_more_than_a_title():
    uni = record("HSBA Hamburg School of Business Administration")
    soup = page("HSBA Hamburg School of Business Administration")

    assert score_identity(uni, soup).score == 0.80
    assert score_identity(
        uni,
        soup,
        imprint_text="Herausgeber: HSBA Hamburg School of Business Administration gGmbH",
    ).score == 0.97


def test_reachable_generic_domain_is_not_evidence():
    # Spec §20: wirtschaft-berlin.de answering HTTP 200 proves nothing.
    uni = record("Hochschule für Wirtschaft Berlin", "Berlin")
    soup = page(
        "Wirtschaft Berlin – Nachrichten",
        "Alle Hochschulen in Berlin im Überblick.",
    )
    assert score_identity(uni, soup, imprint_text="Wirtschaft Berlin Verlag GmbH").score == 0.0


def test_similar_institution_elsewhere_is_not_evidence():
    uni = record("Evangelische Hochschule Berlin", "Berlin")
    soup = page("Evangelische Hochschule Dresden")
    assert score_identity(uni, soup, imprint_text="Evangelische Hochschule Dresden").score == 0.0


def test_bot_challenge_is_blocked_not_reachable():
    result = FetchResult(
        "https://www.hu-berlin.de",
        final_url="https://www.hu-berlin.de/",
        status=200,
        html=b"<html><head><title>Dein Browser wird gepr\xc3\xbcft!</title></head></html>",
    )
    assert result.blocked and not result.ok


def test_normalize_url_drops_default_port():
    assert normalize_url("https://www.hs-pforzheim.de:443/") == "https://www.hs-pforzheim.de"
    assert normalize_url("https://example.de:8443/x") == "https://example.de:8443/x"


# ----------------------------------------------------------------------
# Resolution with a fake network
# ----------------------------------------------------------------------

HSBA_HOME = (
    b"<html><head><title>HSBA Hamburg School of Business Administration</title></head>"
    b'<body><a href="/impressum">Impressum</a></body></html>'
)
HSBA_IMPRINT = b"<html><body>HSBA Hamburg School of Business Administration gGmbH</body></html>"
OTHER_IMPRINT = b"<html><body>Beispiel Verlag GmbH</body></html>"


HSBA = record("HSBA Hamburg School of Business Administration")


def test_candidate_with_title_and_imprint_is_accepted():
    resolver = FakeResolver({
        "https://www.hsba.de/": (200, HSBA_HOME),
        "https://www.hsba.de/impressum": (200, HSBA_IMPRINT),
    })
    result = resolver.resolve(HSBA)

    assert result["status"] == "resolved"
    assert result["method"] == "deterministic_high"
    assert result["official_url"] == "https://www.hsba.de"


def test_title_without_imprint_goes_to_review():
    resolver = FakeResolver({
        "https://www.hsba.de/": (200, HSBA_HOME),
        "https://www.hsba.de/impressum": (200, OTHER_IMPRINT),
    })
    result = resolver.resolve(HSBA)

    assert result["status"] == "review"
    assert result["method"] == "deterministic_medium"
    assert result["official_url"] is None
    assert result["suggested_url"] == "https://www.hsba.de"


def test_two_different_confirmed_sites_are_ambiguous():
    resolver = FakeResolver({
        "https://www.hsba.de/": (200, HSBA_HOME),
        "https://www.hsba.de/impressum": (200, HSBA_IMPRINT),
        "https://www.hsba.com/": (200, HSBA_HOME),
        "https://www.hsba.com/impressum": (200, HSBA_IMPRINT),
    })
    result = resolver.resolve(HSBA)

    assert result["status"] == "review"
    assert "ambiguous_candidates" in result["flags"]
    assert result["official_url"] is None


def test_subdomains_of_one_site_are_not_ambiguous():
    resolver = FakeResolver(
        {
            "https://campus.hsba.de/": (200, HSBA_HOME),
            "https://campus.hsba.de/impressum": (200, HSBA_IMPRINT),
            "https://www.hsba.de/": (200, HSBA_HOME),
            "https://www.hsba.de/impressum": (200, HSBA_IMPRINT),
        },
        redirects={"https://www.hsba-hamburg.de/": "https://campus.hsba.de/"},
    )
    result = resolver.resolve(HSBA)

    assert result["status"] == "resolved"
    assert result["official_url"] == "https://www.hsba.de"


def test_source_url_redirected_to_unrelated_name_needs_review():
    uni = record("Fachhochschule Bielefeld", "Bielefeld", url="https://www.fh-bielefeld.de")
    resolver = FakeResolver(
        {"https://www.hsbi.de/": (200, b"<html><head><title>HSBI</title></head></html>")},
        redirects={"https://www.fh-bielefeld.de": "https://www.hsbi.de/"},
    )
    result = resolver.resolve(uni)

    assert result["status"] == "review"
    assert result["official_url"] == "https://www.fh-bielefeld.de"
    assert result["suggested_url"] == "https://www.hsbi.de"
    assert "possible_rename_or_merger" in result["flags"]


def test_source_url_behind_bot_challenge_is_kept():
    uni = record("Humboldt-Universität zu Berlin", "Berlin", url="https://www.hu-berlin.de")
    resolver = FakeResolver({
        "https://www.hu-berlin.de": (
            200,
            b"<html><head><title>Dein Browser wird gepr\xc3\xbcft!</title></head></html>",
        ),
    })
    result = resolver.resolve(uni)

    assert result["status"] == "resolved"
    assert result["method"] == "source_direct"
    assert "bot_challenge" in result["flags"]


def test_homepage_redirect_within_site_keeps_homepage():
    from registry.enrichment.website_resolver import canonical_url

    assert canonical_url("https://www.th-luebeck.de", "https://www.th-luebeck.de/marktueberwachung") == "https://www.th-luebeck.de"
    assert canonical_url("http://tu-clausthal.de", "https://www.tu-clausthal.de/") == "https://www.tu-clausthal.de"
    # Deep source link, or a move to another site: keep the path.
    assert canonical_url("https://www.hs-fresenius.de/standort/heidelberg", "https://www.hs-fresenius.de/standort/heidelberg/") == "https://www.hs-fresenius.de/standort/heidelberg"
    assert canonical_url("https://www.fhf-nordkirchen.de", "https://www.finanzverwaltung.nrw.de/dienststellen/hfs") == "https://www.finanzverwaltung.nrw.de/dienststellen/hfs"


def test_source_subpage_is_replaced_by_homepage_naming_the_institution():
    uni = record("Technische Hochschule Lübeck", "Lübeck", url="https://www.th-luebeck.de/marktueberwachung")
    resolver = FakeResolver({
        "https://www.th-luebeck.de/marktueberwachung": (200, b"<html><head><title>Markt\xc3\xbcberwachung</title></head></html>"),
        "https://www.th-luebeck.de/": (200, b"<html><head><title>Technische Hochschule L\xc3\xbcbeck</title></head></html>"),
    })
    result = resolver.resolve(uni)

    assert result["official_url"] == "https://www.th-luebeck.de"
    assert "subpage_replaced_by_homepage" in result["flags"]


def test_portal_subpage_stays_when_portal_homepage_is_someone_else():
    uni = record("Fachhochschule für Verwaltung und Polizei", "Saarbrücken", url="https://www.saarland.de/fhsv/start")
    resolver = FakeResolver({
        "https://www.saarland.de/fhsv/start": (
            200,
            b"<html><head><title>Fachhochschule f\xc3\xbcr Verwaltung und Polizei</title></head></html>",
        ),
        "https://www.saarland.de/": (200, b"<html><head><title>Saarland</title></head></html>"),
    })
    result = resolver.resolve(uni)

    assert result["official_url"] == "https://www.saarland.de/fhsv/start"
    assert "subpage_replaced_by_homepage" not in result["flags"]


def test_outage_page_keeps_the_source_url():
    uni = record("Hessische Hochschule für öffentliches Management und Sicherheit", url="https://hoems.hessen.de")
    resolver = FakeResolver(
        {"https://sorry-hessenweb.hessen.de": (200, "<html><head><title>Hessen | Störung</title></head></html>".encode())},
        redirects={"https://hoems.hessen.de": "https://sorry-hessenweb.hessen.de"},
    )
    result = resolver.resolve(uni)

    assert result["status"] == "resolved"
    assert result["official_url"] == "https://hoems.hessen.de"
    assert "site_unavailable" in result["flags"]
