"""
URL enrichment: verify the websites named by the state sources and
resolve the missing ones deterministically.

    official_url from the state source?
        yes -> technical check (DNS, HTTP, redirects, final URL)
               + identity check
        no  -> domain candidates from the name
               -> technical check -> identity check -> confidence

Generated domains are only candidates. HTTP 200 proves that a website
exists, not that it belongs to the institution. A candidate is accepted
only when the website itself names the institution, and only when no
second, different website does the same. Everything weaker goes to
review with official_url left empty.

Usage (from scrapers/hochschulen/):

    python -m registry.enrichment.website_resolver
    python -m registry.enrichment.website_resolver --only-missing
    python -m registry.enrichment.website_resolver --states DE-HH DE-TH
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import threading
import unicodedata
import warnings
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import idna
import requests
from bs4 import BeautifulSoup
from urllib3.exceptions import InsecureRequestWarning

from registry.enrichment.website import IMPRINT_TERMS, USER_AGENT
from registry.normalize import domain_key, normalize_url
from registry.utils.matching import (
    GENERIC_TOKENS,
    STOPWORDS,
    UMLAUTS,
    name_tokens,
)


HIGH_CONFIDENCE = 0.85
MEDIUM_CONFIDENCE = 0.70

MAX_CANDIDATES = 30

# Reachable, but the server refuses automated requests.
BLOCKED_STATUS = {401, 403, 429, 503}

# Hard limit for one request including its body, in seconds.
FETCH_DEADLINE = 45

# Worth one more try.
RETRY_STATUS = {500, 502, 504}
RETRY_ERRORS = {"ReadTimeout", "ConnectTimeout", "ConnectionError"}

# Titles of anti-bot interstitials ("Dein Browser wird geprüft!").
CHALLENGE_TITLES = (
    "browser wird geprüft",
    "just a moment",
    "checking your browser",
    "attention required",
    "ddos-guard",
    "captcha",  # "Link11 - CAPTCHA" on thueringen.de
)

# Titles of outage/maintenance pages ("Hessen | Störung" on
# sorry-hessenweb.hessen.de). A temporary outage must not overturn a URL
# the state source lists.
OUTAGE_TITLES = (
    "störung",
    "wartungsarbeiten",
    "under maintenance",
    "vorübergehend nicht verfügbar",
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Most specific first. Only the first matching type is used.
TYPE_ABBREVIATIONS = (
    ("technische universität", "tu"),
    ("technische hochschule", "th"),
    ("fachhochschule", "fh"),
    ("universität", "uni"),
    ("hochschule", "hs"),
)

# Type abbreviations are never treated as an institution's acronym.
TYPE_ACRONYMS = {"fh", "hs", "tu", "th", "uni", "uas"}

# Tokens that cannot identify an institution on a website.
NON_DISTINCTIVE = GENERIC_TOKENS | TYPE_ACRONYMS | {
    "berufsakademie", "fernhochschule", "kunsthochschule",
    "musikhochschule", "school", "business", "administration",
    "management",
}

LEGAL_FORM_RE = re.compile(
    r"\b(?:ggmbh|gmbh|e\.\s?v\.|ag)(?=\W|$)\.?",
    re.IGNORECASE,
)

# "Euro-FH - Europäische Fernhochschule Hamburg"
NAME_SEPARATOR_RE = re.compile(r"\s+[-–—|]\s+")


# ----------------------------------------------------------------------
# Name analysis
# ----------------------------------------------------------------------

def fold(text: str | None) -> str:
    """Comparison form: lower case, umlauts as ae/oe/ue/ss, words only."""
    value = unicodedata.normalize("NFKC", text or "")
    value = value.replace("\xad", "").lower().translate(UMLAUTS)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def core_name(name: str) -> str:
    """Source name without parenthetical additions and legal forms."""
    value = unicodedata.normalize("NFKC", name).replace("\xad", "")
    value = re.sub(r"\([^)]*\)", " ", value)
    value = LEGAL_FORM_RE.sub(" ", value)
    return " ".join(value.split()).strip(" ,-–")


def without_stopwords(folded: str) -> str:
    """ "universitaet zu luebeck" -> "universitaet luebeck" """
    return " ".join(token for token in folded.split() if token not in STOPWORDS)


def name_variants(name: str, record_places: list[str] = ()) -> list[str]:
    """
    Forms of the source name to look for on a website, folded and
    without filler words. Each variant needs a word that is not a
    generic type word, so "Evangelische Hochschule" alone never
    identifies anything. A single word only counts if it is a long,
    distinctive brand ("nordakademie").
    """
    core = core_name(name)
    variants = [fold(v) for v in (name, core, *NAME_SEPARATOR_RE.split(core))]

    # "IU Internationale Hochschule in Erfurt"
    match = re.match(r"^(.+?)\s+in\s+\S+$", core)
    if match:
        variants.append(fold(match.group(1)))

    # Without the city the source appends:
    # "Deutsche Hochschule der Polizei Münster"
    for place in record_places:
        suffix = " " + fold(place)
        variants.extend(v[: -len(suffix)] for v in list(variants) if v.endswith(suffix))

    result = []
    for variant in variants:
        tokens = without_stopwords(variant).split()
        distinctive = [t for t in tokens if t not in NON_DISTINCTIVE]

        usable = (
            (len(tokens) >= 2 and distinctive)
            or (len(tokens) == 1 and distinctive and len(tokens[0]) >= 7)
        )

        variant = " ".join(tokens)
        if usable and variant not in result:
            result.append(variant)

    return result


def explicit_acronyms(name: str) -> list[str]:
    """
    Acronyms written in the source name, e.g. "(BHT)", "(HfM)" or
    "HSBA Hamburg School ...". Never constructed from initials.
    """
    found = []

    # "(BHT)", "(German UDS)" — but not "(privat)" or "(FH)".
    for inner in re.findall(r"\(([^)]+)\)", name):
        inner = inner.strip()
        if (
            2 <= len(inner) <= 15
            and sum(char.isupper() for char in inner) >= 2
            and inner.lower() not in TYPE_ACRONYMS
            and not LEGAL_FORM_RE.fullmatch(inner)
        ):
            found.append(inner)

    for token in re.findall(r"[A-Za-zÄÖÜäöü0-9]+(?:-[A-Za-zÄÖÜäöü0-9]+)*", name):
        letters = re.sub(r"[^A-Za-zÄÖÜäöü]", "", token)
        upper = sum(char.isupper() for char in letters)

        if (
            2 <= len(token) <= 6
            and upper >= 2
            and upper >= len(letters) - 1
            and token.lower() not in TYPE_ACRONYMS
        ):
            found.append(token)

    result = []
    for acronym in found:
        if acronym.lower() not in (a.lower() for a in result):
            result.append(acronym)

    return result


def places(record: dict, known_cities: frozenset[str] = frozenset()) -> list[str]:
    """
    Location cities, known city names inside the name ("HSBA Hamburg
    School ...") and the trailing word of the name ("... Gotha").
    `known_cities` are folded city names from all records.
    """
    result = [
        location["city"]
        for location in record.get("locations") or []
        if location.get("city")
    ]

    words = core_name(record["name"]).replace(",", " ").split()

    result.extend(word for word in words if fold(word) in known_cities)

    if (
        words
        and words[-1][:1].isupper()
        and fold(words[-1]) not in NON_DISTINCTIVE | STOPWORDS
    ):
        result.append(words[-1])

    unique = []
    for place in result:
        if fold(place) not in (fold(p) for p in unique):
            unique.append(place)

    return unique


def slug(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).replace("\xad", "")
    value = value.lower().replace("&", " und ")
    value = re.sub(r"[^a-z0-9äöüß]+", "-", value)
    return value.strip("-")


def spellings(label: str) -> list[str]:
    """
    ASCII spelling first (muenchen), then the IDN spelling with
    umlauts (münchen) if the label has any.
    """
    ascii_label = label.translate(UMLAUTS)

    if ascii_label == label:
        return [label]

    return [ascii_label, label]


def to_ascii_host(host: str) -> str:
    """IDNA form for DNS and HTTP: münchen.de -> xn--mnchen-3ya.de"""
    return idna.encode(host, uts46=True).decode("ascii")


# ----------------------------------------------------------------------
# Candidate generation
# ----------------------------------------------------------------------

@dataclass
class Candidate:
    domain: str
    rule: str


def generate_candidates(
    record: dict,
    known_cities: frozenset[str] = frozenset(),
    limit: int = MAX_CANDIDATES,
) -> list[Candidate]:
    """
    Domain candidates in priority order. These are guesses that still
    have to pass the technical and identity checks.
    """
    name = record["name"]
    core = core_name(name)
    lower = core.lower()
    place_labels = [slug(place) for place in places(record, known_cities)]
    acronyms = explicit_acronyms(name)

    labels: list[tuple[str, str, tuple[str, ...]]] = []

    def add(label, rule, tlds=(".de",)):
        if label and len(label) <= 63:
            labels.append((label, rule, tlds))

    # 1. Acronyms written in the source name have the highest priority.
    for acronym in acronyms:
        label = slug(acronym)
        for place in place_labels:
            add(f"{label}-{place}", "source_acronym+place")
        add(label, "source_acronym", (".de", ".com", ".eu"))

    # 2. Brand before a separator: "Euro-FH - Europäische Fernhochschule".
    segments = NAME_SEPARATOR_RE.split(core)
    if len(segments) > 1:
        add(slug(segments[0]), "brand_segment", (".de", ".com"))

    # 3. Institution type + place: fh-gotha.de, fachhochschule-gotha.de
    for phrase, abbreviation in TYPE_ABBREVIATIONS:
        if phrase in lower:
            for place in place_labels:
                add(f"{abbreviation}-{place}", "type_abbreviation+place")
                add(f"{slug(phrase)}-{place}", "type+place")
            break

    # 4. Full name without filler words, only for short names.
    words = [word for word in core.split() if fold(word) not in STOPWORDS]
    if len(words) <= 5:
        add(slug(" ".join(words)), "full_name")

    # 5. Initials, lowest priority: "Technische Universität München" -> tum.
    #    Not when the source already names an acronym.
    initials = "" if acronyms else "".join(
        word[0]
        for word in re.split(r"[\s\-]+", segments[0])
        if word and word[0].isalpha() and fold(word) not in STOPWORDS
    ).lower()

    if 2 <= len(initials) <= 5:
        for place in place_labels:
            add(f"{initials}-{place}", "initials+place")
        add(initials, "initials")

    candidates: list[Candidate] = []
    seen: set[str] = set()

    for label, rule, tlds in labels:
        for spelled in spellings(label):
            for tld in tlds:
                domain = spelled + tld
                if domain not in seen:
                    seen.add(domain)
                    candidates.append(Candidate(domain, rule))

    return candidates[:limit]


# ----------------------------------------------------------------------
# Identity verification
# ----------------------------------------------------------------------

ORGANIZATION_TYPES = (
    "Organization",
    "CollegeOrUniversity",
    "EducationalOrganization",
    "WebSite",
)


def _json_ld_names(soup: BeautifulSoup) -> list[str]:
    names = []

    def walk(node):
        if isinstance(node, list):
            for item in node:
                walk(item)
            return

        if not isinstance(node, dict):
            return

        types = node.get("@type") or []
        if isinstance(types, str):
            types = [types]

        if any(t in ORGANIZATION_TYPES for t in types):
            for key in ("name", "legalName", "alternateName"):
                value = node.get(key)
                if isinstance(value, str):
                    names.append(value)

        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value)

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(script.string or ""))
        except (ValueError, TypeError):
            continue

    return names


def identity_texts(soup: BeautifulSoup) -> list[str]:
    """Where a website names itself: title, h1, site name, structured data."""
    texts = []

    if soup.title and soup.title.string:
        texts.append(soup.title.string)

    texts.extend(h1.get_text(" ", strip=True) for h1 in soup.find_all("h1"))

    for attrs in (
        {"property": "og:site_name"},
        {"property": "og:title"},
        {"name": "application-name"},
    ):
        meta = soup.find("meta", attrs=attrs)
        if meta and meta.get("content"):
            texts.append(meta["content"])

    texts.extend(_json_ld_names(soup))

    return [text for text in texts if text and text.strip()]


def visible_text(soup: BeautifulSoup, limit: int = 60000) -> str:
    for element in soup(["script", "style", "noscript", "svg"]):
        element.decompose()
    return " ".join(soup.stripped_strings)[:limit]


def _contains_phrase(text: str, phrase: str) -> bool:
    return f" {phrase} " in f" {text} "


@dataclass
class Identity:
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    imprint_url: str | None = None


def confidence_from(evidence: set[str]) -> float:
    """
    The website naming itself (title/structured data) and the imprint
    naming the responsible institution are independent signals. Only
    the imprint, or both together, reach HIGH_CONFIDENCE; a matching
    title alone could also be a third-party page about the institution.
    """
    title = "name_in_title" in evidence
    title_tokens = "tokens_in_title" in evidence
    imprint = "name_in_imprint" in evidence
    imprint_tokens = "tokens_in_imprint" in evidence

    if title and imprint:
        return 0.97
    if imprint:
        return 0.92 if title_tokens else 0.90
    if title and imprint_tokens:
        return 0.90
    if title_tokens and imprint_tokens:
        return 0.85
    if title:
        return 0.80
    if title_tokens or "name_in_homepage_text" in evidence:
        return 0.72
    if "acronym_in_title" in evidence:
        return 0.50
    return 0.0


def score_identity(
    record: dict,
    soup: BeautifulSoup,
    imprint_text: str | None = None,
) -> Identity:
    name = record["name"]
    variants = name_variants(name, places(record))
    distinctive = name_tokens(core_name(name)) - NON_DISTINCTIVE

    fields = [without_stopwords(fold(text)) for text in identity_texts(soup)]
    page = without_stopwords(fold(visible_text(BeautifulSoup(str(soup), "html.parser"))))
    imprint = without_stopwords(fold(imprint_text))

    evidence = set()

    if any(_contains_phrase(f, v) for f in fields for v in variants):
        evidence.add("name_in_title")

    if imprint and any(_contains_phrase(imprint, v) for v in variants):
        evidence.add("name_in_imprint")

    # All distinctive words of the name, e.g. {thueringer, verwaltung,
    # gotha}. Needs at least two, otherwise "Hochschule für Wirtschaft
    # Berlin" would be confirmed by any page saying "Berlin".
    if len(distinctive) >= 2:
        if any(distinctive <= set(f.split()) for f in fields):
            evidence.add("tokens_in_title")
        if imprint and distinctive <= set(imprint.split()):
            evidence.add("tokens_in_imprint")

    if any(_contains_phrase(page, v) for v in variants):
        evidence.add("name_in_homepage_text")

    acronyms = [fold(a) for a in explicit_acronyms(name)]
    if any(_contains_phrase(f, a) for f in fields for a in acronyms if a):
        evidence.add("acronym_in_title")

    return Identity(
        score=confidence_from(evidence),
        evidence=sorted(evidence),
    )


def find_imprint_url(soup: BeautifulSoup, base_url: str) -> str | None:
    best = None

    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"].strip())

        if not href.startswith(("http://", "https://")):
            continue

        text = link.get_text(" ", strip=True).lower()
        score = 0

        if any(term in text for term in IMPRINT_TERMS):
            score += 2
        if any(term in href.lower() for term in IMPRINT_TERMS):
            score += 1
        if score and domain_key(href) == domain_key(base_url):
            score += 2

        if score and (best is None or score > best[0]):
            best = (score, href)

    return best[1] if best else None


def meta_refresh_target(soup: BeautifulSoup, base_url: str) -> str | None:
    meta = soup.find(
        "meta",
        attrs={"http-equiv": re.compile("^refresh$", re.IGNORECASE)},
    )

    if not meta or not meta.get("content"):
        return None

    match = re.search(r"url\s*=\s*['\"]?([^'\";]+)", meta["content"], re.IGNORECASE)

    return urljoin(base_url, match.group(1).strip()) if match else None


# ----------------------------------------------------------------------
# Technical verification
# ----------------------------------------------------------------------

@dataclass
class FetchResult:
    url: str
    final_url: str | None = None
    status: int | None = None
    html: bytes | None = None
    error: str | None = None
    # Certificate could not be verified (usually an incomplete chain,
    # which browsers repair and Python does not).
    tls_unverified: bool = False

    def _title(self) -> str:
        if not self.html:
            return ""
        match = re.search(rb"<title[^>]*>(.*?)</title>", self.html[:20000], re.I | re.S)
        return match.group(1).decode("utf-8", "ignore").lower() if match else ""

    @property
    def challenge(self) -> bool:
        """Anti-bot interstitial instead of the real page."""
        return any(marker in self._title() for marker in CHALLENGE_TITLES)

    @property
    def outage(self) -> bool:
        """Maintenance or outage page instead of the real page."""
        return any(marker in self._title() for marker in OUTAGE_TITLES)

    @property
    def ok(self) -> bool:
        return (
            self.status is not None
            and 200 <= self.status < 300
            and self.html is not None
            and not self.challenge
            and not self.outage
        )

    @property
    def blocked(self) -> bool:
        return self.status in BLOCKED_STATUS or self.challenge or self.outage

    @property
    def outcome(self) -> str:
        if self.ok:
            return "reachable"
        if self.challenge:
            return "bot_challenge"
        if self.outage:
            return "site_unavailable"
        if self.status is not None:
            return f"http_{self.status}"
        return self.error or "no_response"


class WebsiteResolver:
    def __init__(
        self,
        timeout: int = 30,
        known_cities: frozenset[str] = frozenset(),
    ):
        self.timeout = timeout
        self.known_cities = known_cities

    # -- network ---------------------------------------------------------

    def host_exists(self, host: str) -> bool:
        try:
            socket.getaddrinfo(to_ascii_host(host), 443)
            return True
        except (socket.gaierror, UnicodeError, idna.IDNAError):
            return False

    def fetch(self, url: str, verify: bool = True) -> FetchResult:
        """
        One GET with a hard wall-clock limit. requests' timeout only
        bounds each socket read, so a server that trickles bytes could
        hold a run forever; the request therefore runs in a daemon
        thread that is abandoned after FETCH_DEADLINE seconds.
        """
        box = {}

        def get():
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", InsecureRequestWarning)
                    response = requests.get(
                        url,
                        headers=HEADERS,
                        timeout=self.timeout,
                        allow_redirects=True,
                        verify=verify,
                    )
                content_type = response.headers.get("Content-Type", "")
                box["response"] = response
                box["html"] = (
                    response.content
                    if "html" in content_type or not content_type
                    else None
                )
                response.close()
            except requests.RequestException as exc:
                box["error"] = type(exc).__name__
            except Exception as exc:  # malformed responses, decoding, ...
                box["error"] = type(exc).__name__

        thread = threading.Thread(target=get, daemon=True)
        thread.start()
        thread.join(FETCH_DEADLINE)

        if thread.is_alive():
            return FetchResult(url, error="DeadlineExceeded")

        if "error" in box:
            return FetchResult(url, error=box["error"])

        response = box["response"]
        html = box["html"]

        return FetchResult(
            url,
            final_url=response.url,
            status=response.status_code,
            html=html,
            tls_unverified=not verify,
        )

    def fetch_once_more(self, url: str) -> FetchResult:
        """One URL, with a retry for transient failures and TLS fallback."""
        result = self.fetch(url)

        if result.status in RETRY_STATUS or result.error in RETRY_ERRORS:
            result = self.fetch(url)

        if result.error == "SSLError":
            # Only public pages are read, nothing is sent. The result
            # is marked so that the report shows the broken certificate.
            result = self.fetch(url, verify=False)

        return result

    def fetch_robust(self, url: str) -> FetchResult:
        """
        A source URL as given, then with the other scheme and with or
        without "www." (http://www.ash-berlin.eu answers 404,
        https://www.ash-berlin.eu works; hcu-hamburg.de has no DNS,
        www.hcu-hamburg.de does).
        """
        result = self.fetch_once_more(url)

        if result.ok or result.blocked:
            return result

        for alternative in _alternative_urls(url):
            other = self.fetch_once_more(alternative)
            if other.ok or other.blocked:
                return other

        return result

    def fetch_domain(self, domain: str) -> FetchResult | None:
        """None if neither www.<domain> nor <domain> has DNS."""
        for host in (f"www.{domain}", domain):
            if not self.host_exists(host):
                continue

            ascii_host = to_ascii_host(host)
            result = self.fetch_once_more(f"https://{ascii_host}/")

            if result.status is None:
                result = self.fetch_once_more(f"http://{ascii_host}/")

            if result.status is not None:
                return result

        return None

    # -- identity --------------------------------------------------------

    def verify(
        self,
        record: dict,
        result: FetchResult,
        imprint_below: float,
    ) -> tuple[Identity, FetchResult]:
        """
        Identity of a reachable website. The imprint is only fetched
        when the homepage alone scores below `imprint_below`.
        """
        soup = BeautifulSoup(result.html, "html.parser")

        # Landing pages that forward via <meta http-equiv="refresh">.
        target = meta_refresh_target(soup, result.final_url)
        if target and domain_key(target) == domain_key(result.final_url):
            forwarded = self.fetch_once_more(target)
            if forwarded.ok:
                result = forwarded
                soup = BeautifulSoup(result.html, "html.parser")

        identity = score_identity(record, soup)

        if identity.score >= imprint_below:
            return identity, result

        imprint_url = find_imprint_url(soup, result.final_url)
        if not imprint_url:
            return identity, result

        imprint = self.fetch_once_more(imprint_url)
        if not imprint.ok:
            return identity, result

        identity = score_identity(
            record,
            soup,
            imprint_text=visible_text(BeautifulSoup(imprint.html, "html.parser")),
        )
        identity.imprint_url = imprint_url

        return identity, result

    # -- resolution ------------------------------------------------------

    def resolve(self, record: dict) -> dict:
        source_url = record.get("official_url")
        resolution = {
            "status": "unresolved",
            "method": None,
            "confidence": 0.0,
            "official_url": None,
            "source_url": source_url,
            "http_status": None,
            "identity": None,
            "flags": [],
            "candidates": [],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        if source_url:
            if self._resolve_source(record, source_url, resolution):
                return resolution

        self._resolve_candidates(record, resolution)
        return resolution

    def _resolve_source(self, record, source_url, resolution) -> bool:
        """
        The state source has priority. Returns False only when the
        source URL is dead, so that candidates are tried instead.
        """
        result = self.fetch_robust(source_url)

        # Deep link gone? The site itself may still be fine.
        root = _root_url(source_url)
        if not result.ok and not result.blocked and root != normalize_url(source_url):
            root_result = self.fetch_robust(root + "/")
            if root_result.ok:
                result = root_result
                resolution["flags"].append("source_link_broken_root_used")

        resolution["http_status"] = result.status

        if result.tls_unverified:
            resolution["flags"].append("tls_certificate_unverified")

        if result.blocked:
            # Reachable, but no automated check possible.
            resolution.update(
                status="resolved",
                method="source_direct",
                confidence=0.8,
                official_url=normalize_url(source_url),
            )
            resolution["flags"].append(
                "bot_challenge" if result.challenge
                else "site_unavailable" if result.outage
                else f"http_blocked_{result.status}"
            )
            return True

        if not result.ok:
            resolution["flags"].append(f"source_unreachable_{result.outcome}")
            return False

        identity, result = self.verify(record, result, imprint_below=MEDIUM_CONFIDENCE)
        final_url = canonical_url(source_url, result.final_url)

        # Sources often link a subpage ("mehr lesen" -> th-luebeck.de/
        # marktueberwachung). The site's homepage is the official URL if it
        # names the institution; a portal homepage (saarland.de) does not.
        if urlsplit(final_url).path:
            home = self.fetch_robust(_root_url(final_url) + "/")
            if home.ok and domain_key(home.final_url) == domain_key(final_url):
                home_identity, home = self.verify(record, home, imprint_below=MEDIUM_CONFIDENCE)
                if home_identity.score >= MEDIUM_CONFIDENCE:
                    identity, result = home_identity, home
                    final_url = _root_url(final_url)
                    resolution["flags"].append("subpage_replaced_by_homepage")

        resolution["identity"] = identity_dict(identity)

        if identity.score < MEDIUM_CONFIDENCE:
            resolution["flags"].append("identity_unconfirmed")

        if domain_key(final_url) == domain_key(source_url):
            resolution.update(
                status="resolved",
                method="source_direct",
                confidence=max(0.9, identity.score),
                official_url=final_url,
            )
            return True

        resolution["flags"].append("redirected_to_other_domain")

        # The new site does not carry the source name in its title or
        # imprint: likely renamed (FH Bielefeld -> HSBI) or merged
        # (EUFH -> CBS). Input for the lifecycle check.
        if not {"name_in_title", "name_in_imprint"} & set(identity.evidence):
            resolution["flags"].append("possible_rename_or_merger")

        if identity.score >= MEDIUM_CONFIDENCE:
            resolution.update(
                status="resolved",
                method="verified_redirect",
                confidence=max(0.85, identity.score),
                official_url=final_url,
            )
        else:
            # Keep what the state says, but someone has to look at it.
            resolution.update(
                status="review",
                method="source_direct",
                confidence=0.5,
                official_url=normalize_url(source_url),
                suggested_url=final_url,
            )

        return True

    def _resolve_candidates(self, record, resolution) -> None:
        reachable = []

        for candidate in generate_candidates(record, self.known_cities):
            result = self.fetch_domain(candidate.domain)
            entry = {
                "domain": candidate.domain,
                "rule": candidate.rule,
                "outcome": "no_dns" if result is None else result.outcome,
            }
            resolution["candidates"].append(entry)

            if result is None or not result.ok:
                continue

            identity, result = self.verify(record, result, imprint_below=HIGH_CONFIDENCE)
            entry["final_url"] = canonical_url(f"https://{candidate.domain}/", result.final_url)
            entry["identity"] = identity_dict(identity)

            reachable.append((identity, entry))

        strong = [(i, e) for i, e in reachable if i.score >= HIGH_CONFIDENCE]
        medium = [(i, e) for i, e in reachable if i.score >= MEDIUM_CONFIDENCE]

        # stuttgart.isba.eu and www.isba.eu are one website.
        strong_sites = {site_key(e["final_url"]) for _, e in strong}

        if len(strong_sites) > 1:
            resolution.update(status="review")
            resolution["flags"].append("ambiguous_candidates")
            return

        if strong:
            # Highest score; on a tie the shortest host (www.isba.eu
            # rather than stuttgart.isba.eu).
            identity, entry = min(
                strong,
                key=lambda item: (
                    -item[0].score,
                    len(domain_key(item[1]["final_url"])),
                ),
            )
            resolution.update(
                status="resolved",
                method="deterministic_high",
                confidence=identity.score,
                official_url=entry["final_url"],
                identity=entry["identity"],
            )
            return

        if medium:
            identity, entry = max(medium, key=lambda item: item[0].score)
            resolution.update(
                status="review",
                method="deterministic_medium",
                confidence=identity.score,
                suggested_url=entry["final_url"],
                identity=entry["identity"],
            )
            return

        # A dead source URL stays visible for review.
        if resolution["source_url"]:
            resolution.update(
                status="review",
                official_url=normalize_url(resolution["source_url"]),
            )


def _alternative_urls(url: str) -> list[str]:
    parts = urlsplit(url.strip())
    host = parts.netloc
    other_scheme = "https" if parts.scheme == "http" else "http"
    other_host = host[4:] if host.startswith("www.") else f"www.{host}"
    rest = parts.path or "/"

    return [
        f"{other_scheme}://{host}{rest}",
        f"https://{other_host}{rest}",
        f"http://{other_host}{rest}",
    ]


def canonical_url(requested: str, final: str) -> str:
    """
    The final URL after redirects, except when a homepage was requested
    and the site forwards within itself: then the homepage is the stable
    official URL (www.th-luebeck.de -> /marktueberwachung stores
    https://www.th-luebeck.de). Forwarding to another site keeps the path.
    """
    final_url = normalize_url(final)

    if not urlsplit(normalize_url(requested)).path and domain_key(final_url) == domain_key(requested):
        return _root_url(final_url)

    return final_url


def site_key(url: str) -> str:
    """
    Registrable domain, approximated by the last two host labels.
    Good enough for .de/.com/.eu/.org; no public-suffix list needed.
    """
    host = domain_key(url) or ""
    return ".".join(host.split(".")[-2:])


def _root_url(url: str) -> str:
    parts = urlsplit(normalize_url(url))
    return f"{parts.scheme}://{parts.netloc}"


def identity_dict(identity: Identity) -> dict:
    return {
        "score": identity.score,
        "evidence": identity.evidence,
        "imprint_url": identity.imprint_url,
    }


# ----------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------

def build_report(records: list[dict]) -> dict:
    checked = [r for r in records if r["website_resolution"]["status"] != "not_checked"]
    resolutions = [r["website_resolution"] for r in checked]

    def entry(record):
        res = record["website_resolution"]
        reachable = [c for c in res["candidates"] if c["outcome"] == "reachable"]
        return {
            "state": record["state"],
            "name": record["name"],
            "status": res["status"],
            "method": res["method"],
            "confidence": res["confidence"],
            "official_url": res["official_url"],
            "suggested_url": res.get("suggested_url"),
            "source_url": res["source_url"],
            "flags": res["flags"],
            "reachable_candidates": [
                {
                    "domain": c["domain"],
                    "final_url": c["final_url"],
                    "identity": c["identity"]["score"],
                }
                for c in reachable
            ][:5],
        }

    with_url = sum(1 for r in records if r.get("official_url"))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "records": len(records),
        "checked": len(checked),
        "official_url_coverage": round(with_url / len(records), 4) if records else 0,
        "by_status": dict(Counter(r["status"] for r in resolutions)),
        "by_method": dict(Counter(r["method"] for r in resolutions if r["method"])),
        "flags": dict(Counter(f for r in resolutions for f in r["flags"])),
        "review": [entry(r) for r in checked if r["website_resolution"]["status"] == "review"],
        "unresolved": [entry(r) for r in checked if r["website_resolution"]["status"] == "unresolved"],
        "unconfirmed_source_urls": [
            entry(r)
            for r in checked
            if "identity_unconfirmed" in r["website_resolution"]["flags"]
        ],
        "possible_rename_or_merger": [
            entry(r)
            for r in checked
            if "possible_rename_or_merger" in r["website_resolution"]["flags"]
        ],
    }


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ProjectPathly — verify and resolve official university websites"
    )
    parser.add_argument("--in", dest="input", default="data/normalized/universities_de.json")
    parser.add_argument("--out", default="data/enriched/universities_de_urls.json")
    parser.add_argument("--report", default="data/reports/url_resolution.json")
    parser.add_argument("--states", nargs="+", default=None)
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Only resolve records without a source URL; skip validating the others.",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    records = json.loads(Path(args.input).read_text(encoding="utf-8"))

    def selected(record):
        if args.states and record["state"] not in args.states:
            return False
        if args.only_missing and record.get("official_url"):
            return False
        return True

    todo = [i for i, record in enumerate(records) if selected(record)]

    print()
    print("=" * 62)
    print("PROJECTPATHLY — WEBSITE RESOLVER")
    print("=" * 62)
    print(f"[START] {len(todo)} of {len(records)} records")

    known_cities = frozenset(
        fold(location["city"])
        for record in records
        for location in record.get("locations") or []
        if location.get("city")
    )

    resolver = WebsiteResolver(timeout=args.timeout, known_cities=known_cities)
    results: dict[int, dict] = {}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(resolver.resolve, records[i]): i for i in todo}

        for future in as_completed(futures):
            index = futures[future]
            record = records[index]

            try:
                results[index] = future.result()
            except Exception as exc:  # one broken site must not stop the run
                results[index] = {
                    "status": "review",
                    "method": None,
                    "confidence": 0.0,
                    "official_url": record.get("official_url"),
                    "source_url": record.get("official_url"),
                    "http_status": None,
                    "identity": None,
                    "flags": [f"resolver_error_{type(exc).__name__}"],
                    "candidates": [],
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }

            res = results[index]
            print(
                f"[{res['status'].upper():10s}] {record['state']} "
                f"{record['name'][:55]:55s} "
                f"{res['method'] or '-':20s} {res['confidence']:.2f} "
                f"{res['official_url'] or res.get('suggested_url') or ''}",
                flush=True,
            )

    # A partial run (--states / --only-missing) keeps the earlier results
    # of all records it did not check.
    previous = {}
    if (args.states or args.only_missing) and Path(args.out).exists():
        previous = {
            f"{r['state']}|{r['name']}": r
            for r in json.loads(Path(args.out).read_text(encoding="utf-8"))
        }

    enriched = []
    for index, record in enumerate(records):
        record = dict(record)

        if index not in results and f"{record['state']}|{record['name']}" in previous:
            enriched.append(previous[f"{record['state']}|{record['name']}"])
            continue

        if index in results:
            res = results[index]
            record["official_url"] = res["official_url"]
            record["website_resolution"] = res
        else:
            record["website_resolution"] = {
                "status": "not_checked",
                "method": None,
                "confidence": None,
                "official_url": record.get("official_url"),
                "source_url": record.get("official_url"),
                "http_status": None,
                "identity": None,
                "flags": [],
                "candidates": [],
                "checked_at": None,
            }

        enriched.append(record)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(enriched, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(enriched)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("-" * 62)
    print(f"CHECKED:      {report['checked']}/{report['records']}")
    for status, count in sorted(report["by_status"].items()):
        print(f"  {status:12s}{count}")
    print(f"URL COVERAGE: {report['official_url_coverage'] * 100:.1f} %")
    print(f"OUTPUT:       {out}")
    print(f"REPORT:       {report_path}")
    print("-" * 62)


if __name__ == "__main__":
    main()
