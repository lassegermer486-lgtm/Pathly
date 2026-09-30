import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter


class NiedersachsenAdapter(RegistryAdapter):
    MAIN_URL = (
        "https://www.studieren-in-niedersachsen.de/"
        "studienwahl/hochschulen/hochschulprofile.html"
    )

    PROFILE_PATH = (
        "/studienwahl/hochschulen/hochschulprofile/"
    )

    CATEGORY_MAP = {
        "Universitäten": {
            "institution_type": "university",
            "ownership": "public",
        },
        "Künstlerische Hochschulen": {
            "institution_type": "art_music",
            "ownership": "public",
        },
        "Hochschulen für angewandte Wissenschaften": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
        },
        "Private Hochschulen": {
            "institution_type": "unknown",
            "ownership": "private_or_other",
        },
        "Verwaltungshochschulen": {
            "institution_type": "public_administration",
            "ownership": "public",
        },
    }

    def __init__(self, state_code, config):
        super().__init__(state_code, config)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            )
        })

    def fetch(self):
        response = self.session.get(
            self.MAIN_URL,
            timeout=30,
        )
        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        rows = []
        current_category = None

        for heading in soup.find_all("h3"):
            name = self._clean(
                heading.get_text(" ", strip=True)
            )

            if name in self.CATEGORY_MAP:
                current_category = name
                continue

            if current_category is None:
                continue

            # Each university is rendered as a clickable teaser.
            # The <h3> containing the university name sits inside
            # the surrounding <a>, rather than containing the link.
            link = heading.find_parent("a", href=True)

            if not link:
                continue

            profile_url = urljoin(
                self.MAIN_URL,
                link["href"],
            )

            if self.PROFILE_PATH not in profile_url:
                continue

            if profile_url.rstrip("/") == self.MAIN_URL.rstrip("/"):
                continue

            category = self.CATEGORY_MAP[
                current_category
            ]

            rows.append({
                "name": name,
                "official_url": None,
                "institution_type": category[
                    "institution_type"
                ],
                "ownership": category[
                    "ownership"
                ],
                "recognition_status": "state",
                "location_name": None,
                "city": None,
                "location_state": "DE-NI",
                "location_type": "main",
                "location_status": "confirmed",
                "source": {
                    "authority": (
                        "Studieren in Niedersachsen"
                    ),
                    "source_url": profile_url,
                    "source_category": (
                        "official_state_study_portal"
                    ),
                },
                "location_source_url": profile_url,
                "location_source_authority": (
                    "Studieren in Niedersachsen"
                ),
            })

        rows = self._deduplicate(rows)

        print(
            f"[NI] Parsed {len(rows)} institutions "
            f"from official Niedersachsen study portal"
        )

        return rows

    @staticmethod
    def _deduplicate(rows):
        result = []
        seen = set()

        for row in rows:
            key = re.sub(
                r"[^a-z0-9äöüß]+",
                "",
                row["name"].lower(),
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
