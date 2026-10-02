from __future__ import annotations

import re

from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0 Safari/537.36"
)

IMPRINT_TERMS = (
    "impressum",
    "imprint",
    "legal notice",
    "legal-notice",
)


class WebsiteEvidenceResolver:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            }
        )

    def _get(self, url: str):
        response = self.session.get(
            url,
            timeout=self.timeout,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response

    @staticmethod
    def _same_domain(url_a: str, url_b: str) -> bool:
        def host(url):
            value = urlparse(url).netloc.lower()
            return value.removeprefix("www.")

        return host(url_a) == host(url_b)

    def discover_imprint(self, official_url: str) -> str | None:
        """
        Find the institution's imprint/legal-notice page dynamically.
        """

        try:
            response = self._get(official_url)
        except requests.RequestException as exc:
            print(
                f"[WEBSITE] Homepage failed: "
                f"{official_url} | {exc}"
            )
            return None

        final_url = response.url
        soup = BeautifulSoup(response.text, "html.parser")

        candidates = []

        # 1. Discover links from the actual website.
        for anchor in soup.find_all("a", href=True):
            href = anchor.get("href", "").strip()

            if not href:
                continue

            absolute_url = urljoin(final_url, href)

            text = " ".join(anchor.stripped_strings).lower()
            href_lower = absolute_url.lower()

            score = 0

            if "impressum" in text:
                score += 100

            if "impressum" in href_lower:
                score += 80

            if "imprint" in text:
                score += 70

            if "imprint" in href_lower:
                score += 60

            if "legal notice" in text:
                score += 50

            if "legal-notice" in href_lower:
                score += 40

            if score == 0:
                continue

            # Prefer links on the institution's own domain.
            if self._same_domain(final_url, absolute_url):
                score += 20

            candidates.append(
                (
                    score,
                    absolute_url,
                )
            )

        if candidates:
            candidates.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            for _, candidate_url in candidates:
                try:
                    candidate_response = self._get(
                        candidate_url
                    )

                    if candidate_response.status_code == 200:
                        return candidate_response.url

                except requests.RequestException:
                    continue

        # 2. Fallback to common paths.
        parsed = urlparse(final_url)

        base_url = (
            f"{parsed.scheme}://{parsed.netloc}/"
        )

        fallback_paths = (
            "impressum",
            "imprint",
            "legal-notice",
        )

        for path in fallback_paths:
            candidate_url = urljoin(
                base_url,
                path,
            )

            try:
                candidate_response = self._get(
                    candidate_url
                )

                if candidate_response.status_code == 200:
                    return candidate_response.url

            except requests.RequestException:
                continue

        return None

    def fetch_imprint_text(
        self,
        imprint_url: str,
    ) -> str | None:
        try:
            response = self._get(imprint_url)
        except requests.RequestException as exc:
            print(
                f"[WEBSITE] Imprint failed: "
                f"{imprint_url} | {exc}"
            )
            return None

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        # Remove obvious noise.
        for element in soup(
            [
                "script",
                "style",
                "noscript",
                "svg",
            ]
        ):
            element.decompose()

        text = " ".join(
            soup.stripped_strings
        )

        return text or None


GERMAN_STATE_PATTERNS = {
    "DE-BW": (
        "baden-württemberg",
        "baden württemberg",
        "ministeriums für wissenschaft, forschung und kunst baden-württemberg",
    ),
    "DE-BY": (
        "bayern",
        "bayerisches staatsministerium",
    ),
    "DE-BE": (
        "land berlin",
        "senatsverwaltung für wissenschaft",
    ),
    "DE-BB": (
        "land brandenburg",
        "ministeriums für wissenschaft, forschung und kultur des landes brandenburg",
        "ministerium für wissenschaft, forschung und kultur des landes brandenburg",
    ),
    "DE-HB": (
        "land bremen",
        "freie hansestadt bremen",
    ),
    "DE-HH": (
        "freie und hansestadt hamburg",
        "behörde für wissenschaft",
    ),
    "DE-HE": (
        "hessen",
        "hessisches ministerium",
    ),
    "DE-MV": (
        "mecklenburg-vorpommern",
        "mecklenburg vorpommern",
    ),
    "DE-NI": (
        "niedersachsen",
        "niedersächsisches ministerium",
    ),
    "DE-NW": (
        "nordrhein-westfalen",
        "nordrhein westfalen",
        "ministeriums für kultur und wissenschaft des landes nordrhein-westfalen",
        "ministerium für kultur und wissenschaft des landes nordrhein-westfalen",
    ),
    "DE-RP": (
        "rheinland-pfalz",
        "rheinland pfalz",
    ),
    "DE-SL": (
        "saarland",
    ),
    "DE-SN": (
        "sachsen",
        "sächsisches staatsministerium",
    ),
    "DE-ST": (
        "sachsen-anhalt",
        "sachsen anhalt",
    ),
    "DE-SH": (
        "schleswig-holstein",
        "schleswig holstein",
    ),
    "DE-TH": (
        "thüringen",
        "thüringer ministerium",
    ),
}


def _normalize_evidence_text(text: str) -> str:
    return " ".join(text.lower().split())


def _detect_state_in_text(text: str) -> list[str]:
    normalized = _normalize_evidence_text(text)

    matches = []

    for state_code, patterns in GERMAN_STATE_PATTERNS.items():
        if any(pattern in normalized for pattern in patterns):
            matches.append(state_code)

    return matches


def extract_website_evidence(text: str) -> dict:
    """
    Extract structured evidence from an official institution website.

    Important:
    This function collects evidence. It does NOT decide the final
    institution state by itself.
    """

    normalized = _normalize_evidence_text(text)

    evidence = {
        "states_mentioned": _detect_state_in_text(text),
        "recognition_states": [],
        "supervisory_states": [],
        "seat": None,
        "campus_hamburg": False,
        "hamburg_location": False,
        "state_recognized": False,
        "evidence": [],
    }

    if (
        "staatlich anerkannt" in normalized
        or "staatliche anerkennung" in normalized
    ):
        evidence["state_recognized"] = True
        evidence["evidence"].append(
            "state_recognition_statement"
        )

    if (
        "campus hamburg" in normalized
        or "standort hamburg" in normalized
        or "hochschulstandort hamburg" in normalized
    ):
        evidence["campus_hamburg"] = True
        evidence["evidence"].append(
            "explicit_hamburg_campus_or_location"
        )

    if re.search(
        r"\b\d{5}\s+hamburg\b",
        normalized,
    ):
        evidence["hamburg_location"] = True
        evidence["evidence"].append(
            "hamburg_postal_address"
        )

    # Explicit legal seat statements have substantially more weight
    # than a generic postal address.
    seat_patterns = (
        r"\bsitz\s*:\s*([a-zäöüß\-\s]+?)(?:,|\.|amtsgericht|registergericht)",
        r"\bmit sitz in\s+(?:\d{5}\s+)?([a-zäöüß\-]+)",
        r"\bsitz in\s+(?:\d{5}\s+)?([a-zäöüß\-]+)",
    )

    for pattern in seat_patterns:
        match = re.search(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        )

        if match:
            evidence["seat"] = match.group(1).strip()
            evidence["evidence"].append(
                "explicit_legal_seat"
            )
            break

    # Supervisory authority is one of our strongest signals.
    authority_patterns = (
        r"aufsichtsbehörde.{0,300}",
        r"zuständige aufsichtsbehörde.{0,300}",
    )

    for pattern in authority_patterns:
        for match in re.finditer(
            pattern,
            normalized,
            flags=re.IGNORECASE,
        ):
            authority_text = match.group(0)

            states = _detect_state_in_text(
                authority_text
            )

            for state in states:
                if state not in evidence["supervisory_states"]:
                    evidence["supervisory_states"].append(
                        state
                    )

    if evidence["supervisory_states"]:
        evidence["evidence"].append(
            "supervisory_authority_state"
        )

    # Recognition context: only inspect text close to the recognition
    # statement instead of assigning every state mentioned on the page.
    recognition_patterns = (
        "staatlich anerkannt",
        "staatliche anerkennung",
    )

    for phrase in recognition_patterns:
        start = 0

        while True:
            index = normalized.find(
                phrase,
                start,
            )

            if index == -1:
                break

            context_start = max(
                0,
                index - 300,
            )

            context_end = min(
                len(normalized),
                index + 500,
            )

            context = normalized[
                context_start:context_end
            ]

            for state in _detect_state_in_text(context):
                if state not in evidence["recognition_states"]:
                    evidence["recognition_states"].append(
                        state
                    )

            start = index + len(phrase)

    if evidence["recognition_states"]:
        evidence["evidence"].append(
            "recognition_context_state"
        )

    return evidence


def website_evidence_to_authority(
    evidence: dict,
    source_url: str | None = None,
):
    """
    Convert extracted website evidence into AuthorityEvidence.

    Conservative by design:
    ambiguous evidence remains unresolved.
    """
    from registry.enrichment.authority import AuthorityEvidence

    seat = evidence.get("seat")
    supervisory_states = evidence.get("supervisory_states", [])
    recognition_states = evidence.get("recognition_states", [])

    institution_state = None
    recognition_state = None
    confidence = "unknown"

    # Strongest website case:
    # explicit legal seat in Hamburg + recognition statement.
    if (
        seat
        and seat.lower() == "hamburg"
        and evidence.get("state_recognized")
    ):
        institution_state = "DE-HH"
        confidence = "high"

    # A single explicit supervisory authority is strong evidence
    # for the responsible state.
    elif len(supervisory_states) == 1:
        institution_state = supervisory_states[0]
        recognition_state = supervisory_states[0]
        confidence = "high"

    # Recognition context can also resolve a state if unique.
    elif len(recognition_states) == 1:
        recognition_state = recognition_states[0]
        institution_state = recognition_states[0]
        confidence = "medium"

    # Multiple states = intentionally unresolved.
    elif (
        len(supervisory_states) > 1
        or len(recognition_states) > 1
    ):
        confidence = "ambiguous"

    return AuthorityEvidence(
        institution_state=institution_state,
        recognition_state=recognition_state,
        legal_seat=seat,
        authority="official_institution_website",
        source_url=source_url,
        confidence=confidence,
    )
