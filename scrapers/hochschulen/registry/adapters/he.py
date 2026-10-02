from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from registry import http_client
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class HessenAdapter(RegistryAdapter):

    CATEGORY_MAP = {
        "Universitäten": {
            "institution_type": "university",
            "ownership": "public",
        },
        "Hochschulen für Angewandte Wissenschaften": {
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
        },
        "Kunsthochschulen": {
            "institution_type": "art_music_university",
            "ownership": "public",
        },
        "Hochschule neuen Typs": {
            "institution_type": "university",
            "ownership": "public",
        },
        "Verwaltungsfachhochschulen und besondere Hochschulen für angewandte Wissenschaften": {
            "institution_type": "university_of_public_administration",
            "ownership": "public",
        },
        "Kirchliche Hochschulen": {
            "institution_type": "university",
            "ownership": "church",
        },
        "Weitere Hochschulen: nicht in Trägerschaft des Landes Hessen": {
            "institution_type": "university",
            "ownership": "private_or_other",
        },
        "Weitere Hochschulen: in Trägerschaft des Bundes": {
            "institution_type": "university_of_public_administration",
            "ownership": "federal",
        },
    }

    def fetch(self):
        url = self.config["url"]

        response = http_client.get(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent",
                    "Mozilla/5.0"
                )
            },
            timeout=30,
        )

        response.raise_for_status()

        # Raw snapshot
        raw_dir = Path(
            self.config.get("_raw_dir", "data/raw")
        )
        raw_dir.mkdir(parents=True, exist_ok=True)

        snapshot = raw_dir / "DE-HE_hochschulen.html"
        snapshot.write_bytes(response.content)

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        rows = []
        seen = set()

        for heading in soup.find_all("h2"):

            category = self._clean(
                " ".join(heading.stripped_strings)
            )

            mapping = self.CATEGORY_MAP.get(category)

            if not mapping:
                continue

            # Walk through DOM until next h2.
            for element in heading.find_all_next():

                if element is not heading and element.name == "h2":
                    break

                if element.name != "a":
                    continue

                href = element.get("href")

                if not href:
                    continue

                name = self._clean(
                    " ".join(element.stripped_strings)
                )

                if not name:
                    continue

                # Remove accessibility suffix added to external links.
                suffix = " Öffnet sich in einem neuen Fenster"

                if name.endswith(suffix):
                    name = name[:-len(suffix)].strip()

                official_url = urljoin(
                    response.url,
                    href
                )

                # Only external university links.
                if "wissenschaft.hessen.de" in official_url:
                    continue

                dedup_key = (
                    category,
                    name,
                    official_url
                )

                if dedup_key in seen:
                    continue

                seen.add(dedup_key)

                rows.append({
                    "name": name,
                    "country": "DE",
                    "state": "DE-HE",

                    "category": category,

                    "institution_type":
                        mapping["institution_type"],

                    "ownership":
                        mapping["ownership"],

                    "recognition_status": "unknown",

                    "official_url": official_url,

                    # The overview does not provide a
                    # standardized address for every institution.
                    "location_name": None,
                    "street": None,
                    "postal_code": None,
                    "city": None,

                    "source": {
                        "authority":
                            self.config.get("authority"),
                        "url": url,
                        "source_type": "html",
                        "retrieved_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                        "category": category,
                    },
                })

        print(
            f"[HE] Parsed {len(rows)} universities "
            f"from official HTML"
        )

        return rows

    @staticmethod
    def _clean(value):
        if value is None:
            return None

        value = " ".join(value.split())

        return value or None
