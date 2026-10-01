from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class BremenAdapter(RegistryAdapter):

    SOURCE_URL = (
        "https://umwelt.bremen.de/"
        "wissenschaft/hochschulen-einrichtungen-2157273"
    )

    INSTITUTIONS = {
        "Universität Bremen": {
            "institution_type": "university",
            "ownership": "public",
            "recognition_status": "public",
            "official_url": "https://www.uni-bremen.de",
        },
        "Hochschule Bremen": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
            "recognition_status": "public",
            "official_url": "https://www.hs-bremen.de",
        },
        "Hochschule Bremerhaven": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
            "recognition_status": "public",
            "official_url": "https://www.hs-bremerhaven.de",
        },
        "Hochschule für Künste Bremen": {
            "institution_type": "art_music_university",
            "ownership": "public",
            "recognition_status": "public",
            "official_url": "https://www.hfk-bremen.de",
        },
        "Apollon Hochschule der Gesundheitswirtschaft": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "private_or_church",
            "recognition_status": "state_recognized",
            "official_url": "https://www.apollon-hochschule.de",
        },
        "Constructor University": {
            "institution_type": "university",
            "ownership": "private_or_church",
            "recognition_status": "state_recognized",
            "official_url": "https://constructor.university",
        },
    }

    HFOEV = {
        "name": "Hochschule für Öffentliche Verwaltung",
        "institution_type": "university_of_public_administration",
        "ownership": "public",
        "recognition_status": "public",
        "official_url": "https://www.hfoev.bremen.de",
        "locations": [
            {
                "name": "Standort I",
                "city": "Bremen",
                "postal_code": "28195",
                "street": "Doventorscontrescarpe 172 C",
                "location_type": "main",
            },
            {
                "name": "Standort II",
                "city": "Bremen",
                "postal_code": "28201",
                "street": "Niedersachsendamm 78-80",
                "location_type": "campus",
            },
        ],
    }

    def fetch(self):

        session = requests.Session()
        session.headers.update({
            "User-Agent":
                "ProjectPathly Registry Research/1.0"
        })

        response = session.get(
            self.SOURCE_URL,
            timeout=30
        )
        response.raise_for_status()

        raw_dir = Path(
            self.config.get(
                "_raw_dir",
                "data/raw"
            )
        )
        raw_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        (
            raw_dir /
            f"{self.state_code}_universities.html"
        ).write_text(
            response.text,
            encoding="utf-8"
        )

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        retrieved_at = datetime.now(
            timezone.utc
        ).isoformat()

        rows = []
        found = set()

        # Six institutions explicitly listed by the responsible
        # Bremen science authority.
        for heading in soup.find_all("h3"):

            name = self._clean(
                heading.get_text(
                    " ",
                    strip=True
                )
            )

            if name not in self.INSTITUTIONS:
                continue

            if name in found:
                continue

            found.add(name)

            meta = self.INSTITUTIONS[name]

            rows.append({
                "name": name,
                "official_url":
                    meta["official_url"],
                "institution_type":
                    meta["institution_type"],
                "ownership":
                    meta["ownership"],
                "recognition_status":
                    meta["recognition_status"],
                "location_name": None,
                "city": (
                    "Bremerhaven"
                    if name == "Hochschule Bremerhaven"
                    else "Bremen"
                ),
                "postal_code": None,
                "street": None,
                "location_type": "main",
                "source": {
                    "authority": (
                        "Freie Hansestadt Bremen – "
                        "Senatorin für Umwelt, "
                        "Klima und Wissenschaft"
                    ),
                    "url": self.SOURCE_URL,
                    "source_type":
                        "official_state_registry",
                    "retrieved_at":
                        retrieved_at,
                    "category":
                        "Hochschulen",
                },
            })

        missing = (
            set(self.INSTITUTIONS)
            - found
        )

        if missing:
            raise RuntimeError(
                "Expected Bremen institutions "
                "not found in official source: "
                + ", ".join(sorted(missing))
            )

        # Hochschule für Öffentliche Verwaltung:
        # separate public university governed by its own
        # Bremen state law and therefore not listed on the
        # science authority's regular six-institution page.
        for location in self.HFOEV["locations"]:

            rows.append({
                "name": self.HFOEV["name"],
                "official_url":
                    self.HFOEV["official_url"],
                "institution_type":
                    self.HFOEV[
                        "institution_type"
                    ],
                "ownership":
                    self.HFOEV["ownership"],
                "recognition_status":
                    self.HFOEV[
                        "recognition_status"
                    ],
                "location_name":
                    location["name"],
                "city":
                    location["city"],
                "postal_code":
                    location["postal_code"],
                "street":
                    location["street"],
                "location_type":
                    location["location_type"],
                "source": {
                    "authority":
                        "Freie Hansestadt Bremen",
                    "url":
                        "https://www.hfoev.bremen.de/",
                    "source_type":
                        "official_state_university",
                    "retrieved_at":
                        retrieved_at,
                    "category":
                        "Verwaltungshochschule",
                },
            })

        print(
            "[HB] Parsed "
            f"{len(found)} regular institutions "
            "+ 1 public-administration university "
            "from official Bremen sources"
        )

        return rows

    @staticmethod
    def _clean(value):

        if not value:
            return None

        return " ".join(
            value.split()
        ).strip()
