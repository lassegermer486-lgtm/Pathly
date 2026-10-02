import re
from urllib.parse import urljoin

import requests

from registry import http_client
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter


class RheinlandPfalzAdapter(RegistryAdapter):
    MAIN_URL = (
        "https://mwwg.rlp.de/"
        "themen/wissenschaft/hochschulen/"
        "hochschulen-in-rheinland-pfalz"
    )

    CATEGORY_MAP = {
        "Universitäten": {
            "institution_type": "university",
            "ownership": "public",
        },
        "Hochschulen für angewandte Wissenschaften": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
        },
        "Weitere Hochschulen": {
            "institution_type": "unknown",
            "ownership": "unknown",
        },
    }

    def __init__(self, state_code, config):
        super().__init__(state_code, config)

        self.session = http_client.session()
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

        for heading in soup.find_all("h2"):
            category_name = self._clean(
                heading.get_text(" ", strip=True)
            )

            if category_name not in self.CATEGORY_MAP:
                continue

            category = self.CATEGORY_MAP[
                category_name
            ]

            node = heading.find_next()

            while node:
                if node.name == "h2":
                    break

                if node.name == "a" and node.get("href"):
                    name = self._clean(
                        node.get_text(" ", strip=True)
                    )

                    if self._looks_like_institution(name):
                        rows.append({
                            "name": name,
                            "official_url": urljoin(
                                self.MAIN_URL,
                                node["href"],
                            ),
                            "institution_type": (
                                self._institution_type(
                                    name,
                                    category[
                                        "institution_type"
                                    ],
                                )
                            ),
                            "ownership": category[
                                "ownership"
                            ],
                            "recognition_status": "state",
                            "location_name": None,
                            "city": None,
                            "location_state": "DE-RP",
                            "location_type": "main",
                            "location_status": "confirmed",
                            "source": {
                                "authority": (
                                    "Ministerium für Wissenschaft "
                                    "und Gesundheit Rheinland-Pfalz"
                                ),
                                "source_url": self.MAIN_URL,
                                "source_category": (
                                    "official_state_registry"
                                ),
                            },
                            "location_source_url": self.MAIN_URL,
                            "location_source_authority": (
                                "Land Rheinland-Pfalz"
                            ),
                        })

                node = node.find_next()

        rows = self._deduplicate(rows)

        print(
            f"[RP] Parsed {len(rows)} institutions "
            f"from official Rheinland-Pfalz source"
        )

        return rows

    @staticmethod
    def _looks_like_institution(name):
        if not name:
            return False

        lower = name.lower()

        return any(
            marker in lower
            for marker in [
                "universität",
                "hochschule",
                "fakultät",
                "whu",
            ]
        )

    @staticmethod
    def _institution_type(name, default):
        lower = name.lower()

        if any(
            marker in lower
            for marker in [
                "kunsthochschule",
                "hochschule für musik",
            ]
        ):
            return "art_music"

        if "verwaltungswissenschaften" in lower:
            return "public_administration"

        if any(
            marker in lower
            for marker in [
                "polizei",
                "finanzen",
                "öffentliche verwaltung",
                "bundesbank",
            ]
        ):
            return "public_administration"

        if "theologische fakultät" in lower:
            return "theological"

        return default

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
