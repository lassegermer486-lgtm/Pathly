import re
from urllib.parse import urljoin

import requests

from registry import http_client
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter


class SachsenAdapter(RegistryAdapter):
    BASE_URL = "https://www.studieren.sachsen.de"

    CATEGORY_PAGES = {
        "university": "/vier-universitaten-4236.html",
        "art_music": "/funf-kunsthochschulen-4234.html",
        "university_of_applied_sciences": "/funf-hochschulen-fur-angewandte-wissenschaften-4232.html",
    }

    OTHER_URL = (
        BASE_URL
        + "/weitere-hochschulen-4328.html"
    )

    DUAL_URL = (
        BASE_URL
        + "/sieben-studienakademien-berufsakakademie-sachsen-4231.html"
    )

    def __init__(self, state_code, config):
        super().__init__(state_code, config)

        self.session = http_client.session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0",
        })

    def fetch(self):
        rows = []

        # 1. Universities, art colleges and public UAS
        for institution_type, path in self.CATEGORY_PAGES.items():
            url = urljoin(self.BASE_URL, path)

            rows.extend(
                self._fetch_standard_category(
                    url,
                    institution_type,
                )
            )

        # 2. State-recognised and administrative universities
        rows.extend(self._fetch_other())

        # 3. Duale Hochschule Sachsen
        dual_row = self._fetch_dual()

        if dual_row:
            rows.extend(dual_row)

        rows = self._deduplicate(rows)

        print(
            f"[SN] Parsed {len(rows)} institution candidates "
            f"from official Sachsen sources"
        )

        return rows

    def _get_soup(self, url):
        response = self.session.get(
            url,
            timeout=30,
        )
        response.raise_for_status()

        return BeautifulSoup(
            response.text,
            "html.parser",
        )

    def _fetch_standard_category(
        self,
        url,
        institution_type,
    ):
        soup = self._get_soup(url)

        rows = []

        for heading in soup.find_all("h2"):
            name = self._clean(
                heading.get_text(
                    " ",
                    strip=True,
                )
            )

            if not name:
                continue

            if self._is_generic_heading(name):
                continue

            official_url = self._find_official_url(
                heading,
                url,
            )

            rows.append({
                "name": name,
                "official_url": official_url,
                "institution_type": institution_type,
                "ownership": "public",
                "recognition_status": "state",
                "location_state": "DE-SN",
                "location_type": "main",
                "location_status": "confirmed",
                "source": {
                    "authority": (
                        "Freistaat Sachsen"
                    ),
                    "source_url": url,
                    "source_category": (
                        "official_state_higher_education"
                    ),
                },
            })

        return rows

    def _fetch_other(self):
        soup = self._get_soup(self.OTHER_URL)

        rows = []

        current_category = None
        pending_row = None

        for tag in soup.find_all(["h2", "p"]):
            text = self._clean(
                tag.get_text(
                    " ",
                    strip=True,
                )
            )

            if not text:
                continue

            if tag.name == "h2":
                lower = text.lower()

                if (
                    "staatlich anerkannte"
                    in lower
                ):
                    current_category = (
                        "state_recognised"
                    )

                elif (
                    "hochschulen der verwaltung"
                    in lower
                ):
                    current_category = (
                        "public_administration"
                    )

                else:
                    current_category = None

                pending_row = None
                continue

            if current_category is None:
                continue

            parsed = self._parse_other_entry(
                text,
                current_category,
                tag,
            )

            if parsed:
                rows.append(parsed)
                pending_row = parsed

            elif (
                pending_row
                and not pending_row.get("official_url")
            ):
                link = tag.find(
                    "a",
                    href=True,
                )

                if link:
                    href = link["href"]

                    if href.startswith("http"):
                        pending_row["official_url"] = href

        return rows

    def _parse_other_entry(
        self,
        text,
        category,
        tag,
    ):
        address_match = re.search(
            r"\bBesucheradresse\s*:",
            text,
            re.I,
        )

        # Standard entries have:
        # Institution name + Besucheradresse
        if address_match:
            name = self._clean(
                text[:address_match.start()]
            )

        # Hochschule Meißen is split across
        # multiple paragraphs on the source page.
        elif (
            re.search(
                r"\b(?:Hochschule|Universität)\b",
                text,
                re.I,
            )
            and len(text) < 180
        ):
            name = text

        else:
            return None

        if not name:
            return None

        city = None

        city_match = re.search(
            r"\b\d{5}\s+"
            r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß"
            r"/.\-\s]+?)"
            r"(?:\s+(?:www\.|https?://)|$)",
            text,
        )

        if city_match:
            city = self._clean(
                city_match.group(1)
            )

        official_url = None

        link = tag.find(
            "a",
            href=True,
        )

        if link:
            href = link["href"]

            if href.startswith("http"):
                official_url = href

        if category == "public_administration":
            institution_type = (
                "public_administration"
            )
            ownership = "public"

        else:
            institution_type = (
                self._infer_type(name)
            )
            ownership = "private_or_other"

        return {
            "name": name,
            "official_url": official_url,
            "institution_type": institution_type,
            "ownership": ownership,
            "recognition_status": "state",
            "city": city,
            "location_state": "DE-SN",
            "location_type": "main",
            "location_status": "confirmed",
            "source": {
                "authority": "Freistaat Sachsen",
                "source_url": self.OTHER_URL,
                "source_category": (
                    "official_state_other_higher_education"
                ),
            },
        }

    def _fetch_dual(self):
        soup = self._get_soup(self.DUAL_URL)

        paragraphs = [
            self._clean(p.get_text(" ", strip=True))
            for p in soup.find_all("p")
            if self._clean(p.get_text(" ", strip=True))
        ]

        # Discover the institution name from the official page text.
        institution_text = next(
            (
                text
                for text in paragraphs
                if re.search(
                    r"Duale(?:n)?\s+Hochschule\s+Sachsen",
                    text,
                    re.I,
                )
            ),
            None,
        )

        if not institution_text:
            return []

        name_match = re.search(
            r"(Duale(?:n)?\s+Hochschule\s+Sachsen)",
            institution_text,
            re.I,
        )

        if not name_match:
            return []

        # Canonical institution name; the source uses
        # "Dualen Hochschule Sachsen" grammatically in running text.
        name = "Duale Hochschule Sachsen"

        # Discover the paragraph containing the official location list.
        location_text = next(
            (
                text
                for text in paragraphs
                if re.search(
                    r"Standorten\s+in\s+",
                    text,
                    re.I,
                )
            ),
            None,
        )

        cities = []

        if location_text:
            location_match = re.search(
                r"Standorten\s+in\s+(.+?)\s+bietet\b",
                location_text,
                re.I,
            )

            if location_match:
                city_text = location_match.group(1)

                city_text = re.sub(
                    r"\s+(?:sowie|und)\s+",
                    ", ",
                    city_text,
                    flags=re.I,
                )

                cities = [
                    self._clean(city)
                    for city in city_text.split(",")
                    if self._clean(city)
                ]

        # Discover official DHSN website from the source page.
        official_url = None

        for a in soup.find_all("a", href=True):
            href = urljoin(
                self.DUAL_URL,
                a["href"],
            )

            if "dhsn.de" in href.lower():
                official_url = href
                break

        if not cities:
            cities = [None]

        rows = []

        for city in cities:
            rows.append({
                "name": name,
                "official_url": official_url,
                "institution_type": "university_of_applied_sciences",
                "ownership": "public",
                "recognition_status": "state",
                "city": city,
                "location_state": "DE-SN",
                "location_type": "campus" if city else "main",
                "location_status": "confirmed",
                "source": {
                    "authority": "Freistaat Sachsen",
                    "source_url": self.DUAL_URL,
                    "source_category": "official_state_dual_university",
                },
            })

        return rows

    def _find_official_url(
        self,
        heading,
        source_url,
    ):
        # Most entries use a collapsible section.
        # Search links until the next h2.
        for element in heading.find_all_next():
            if (
                element.name == "h2"
                and element is not heading
            ):
                break

            if element.name != "a":
                continue

            href = element.get("href")

            if not href:
                continue

            absolute = urljoin(
                source_url,
                href,
            )

            if (
                "studieren.sachsen.de"
                not in absolute
                and not absolute.startswith(
                    "mailto:"
                )
                and not absolute.startswith(
                    "tel:"
                )
            ):
                return absolute

        return None

    @staticmethod
    def _infer_type(name):
        lower = name.lower()

        if (
            "musik" in lower
            or "kunst" in lower
        ):
            return "art_music"

        if "universität" in lower:
            return "university"

        if (
            "hochschule" in lower
            or "(fh)" in lower
        ):
            return (
                "university_of_applied_sciences"
            )

        return "unknown"

    @staticmethod
    def _is_generic_heading(name):
        lower = name.lower()

        generic = (
            "herausgeber",
            "service",
            "verwandte portale",
            "seite empfehlen",
            "weitere informationen",
            "pressemitteilungen",
        )

        return any(
            lower.startswith(value)
            for value in generic
        )

    @staticmethod
    def _deduplicate(rows):
        result = []
        seen = set()

        for row in rows:
            key = (
                re.sub(
                    r"[^a-z0-9äöüß]+",
                    "",
                    row["name"].lower(),
                ),
                row.get("city"),
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(row)

        return result

    @staticmethod
    def _clean(value):
        return re.sub(
            r"\s+",
            " ",
            value or "",
        ).strip()
