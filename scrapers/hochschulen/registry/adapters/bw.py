from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from registry import http_client
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class BadenWuerttembergAdapter(RegistryAdapter):

    BASE = (
        "https://mwk.baden-wuerttemberg.de/de/"
        "hochschulen-studium/hochschullandschaft/hochschularten/"
    )

    PAGES = {
        "universitaeten": {
            "heading": "Die Universitäten im Land",
            "institution_type": "university",
            "ownership": "public",
        },
        "paedagogische-hochschulen": {
            "heading": "Die Pädagogischen Hochschulen im Land",
            "institution_type": "university_of_education",
            "ownership": "public",
        },
        "kunst-und-musikhochschulen": {
            "heading": "Die Kunst- und Musikhochschulen im Land",
            "institution_type": "art_music_university",
            "ownership": "public",
        },
        "hochschulen-fuer-angewandte-wissenschaften": {
            "heading": "Die Hochschulen für angewandte Wissenschaften im Land",
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
        },
        "nichtstaatliche-hochschulen": {
            "heading": "Die nichtstaatlichen Hochschulen im Land",
            "institution_type": "university",
            "ownership": "private_or_church",
        },
    }

    # Links occurring inside the relevant sections that are
    # not themselves universities.
    EXCLUDED_NAMES = {
        "#lieberlehramt",
        "Portal e-teaching.org",
        "Die Studieninformation für Baden-Württemberg",
        "Rektorenkonferenz der deutschen Musikhochschulen in der HRK",
        "Deutscher Musikrat",
        "Landessammlung Streichinstrumente",
        "Hochschulen für Angewandte Wissenschaften Baden-Württemberg e.V.",
        "Zukunftskonferenz Musikhochschulen",
        "Merkblatt über die Voraussetzungen der staatlichen Anerkennung als Hochschule (PDF)",
    }

    def fetch(self):
        headers = {
            "User-Agent": self.config.get(
                "user_agent",
                "ProjectPathlyRegistry/0.1"
            )
        }

        raw_dir = Path(
            self.config.get("_raw_dir", "data/raw")
        )
        raw_dir.mkdir(parents=True, exist_ok=True)

        rows = []

        # --------------------------------------------------
        # Normal university categories
        # --------------------------------------------------

        for slug, meta in self.PAGES.items():

            url = urljoin(self.BASE, slug)

            response = http_client.get(
                url,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            (
                raw_dir /
                f"DE-BW_{slug}.html"
            ).write_bytes(response.content)

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            links = self._extract_section_links(
                soup=soup,
                page_url=response.url,
                heading_text=meta["heading"],
            )

            for name, official_url in links:

                if name in self.EXCLUDED_NAMES:
                    continue

                # Documents inside a university section are supporting
                # material, not university registry entries.
                if official_url.lower().split("?")[0].endswith(".pdf"):
                    continue

                rows.append({
                    "name": name,
                    "country": "DE",
                    "state": "DE-BW",

                    "category": meta["heading"],

                    "institution_type":
                        meta["institution_type"],

                    "ownership":
                        meta["ownership"],

                    "recognition_status": "unknown",

                    "official_url": official_url,

                    "location_name": None,
                    "street": None,
                    "postal_code": None,
                    "city": None,

                    "source": {
                        "authority":
                            self.config.get("authority"),
                        "url": url,
                        "source_type": "html_multi_page",
                        "retrieved_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                        "category":
                            meta["heading"],
                    },
                })

        # --------------------------------------------------
        # DHBW special case
        # --------------------------------------------------

        dhbw_url = urljoin(
            self.BASE,
            "duale-hochschule-baden-wuerttemberg"
        )

        response = http_client.get(
            dhbw_url,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        (
            raw_dir /
            "DE-BW_duale-hochschule-baden-wuerttemberg.html"
        ).write_bytes(response.content)

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        dhbw_links = self._extract_section_links(
            soup=soup,
            page_url=response.url,
            heading_text="Die Standorte der DHBW",
        )

        for name, official_url in dhbw_links:

            if name == "Die Studieninformation für Baden-Württemberg":
                continue

            # Main institution
            if name == "Duale Hochschule Baden-Württemberg":

                rows.append({
                    "name": "Duale Hochschule Baden-Württemberg",
                    "country": "DE",
                    "state": "DE-BW",
                    "category": "Duale Hochschule Baden-Württemberg",
                    "institution_type": "dual_university",
                    "ownership": "public",
                    "recognition_status": "unknown",
                    "official_url": official_url,

                    "location_name": None,
                    "street": None,
                    "postal_code": None,
                    "city": None,

                    "source": {
                        "authority":
                            self.config.get("authority"),
                        "url": dhbw_url,
                        "source_type": "html_multi_page",
                        "retrieved_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                        "category":
                            "Duale Hochschule Baden-Württemberg",
                    },
                })

                continue

            # DHBW campus / CAS
            if (
                name.startswith("DHBW ")
                or name.startswith(
                    "Center for Advanced Studies"
                )
            ):

                location_name = name

                if name.startswith("DHBW "):
                    city = name.removeprefix(
                        "DHBW "
                    ).strip()
                else:
                    city = None

                rows.append({
                    "name": "Duale Hochschule Baden-Württemberg",
                    "country": "DE",
                    "state": "DE-BW",
                    "category": "Duale Hochschule Baden-Württemberg",
                    "institution_type": "dual_university",
                    "ownership": "public",
                    "recognition_status": "unknown",

                    # The university-level URL will be taken
                    # from the main DHBW row during aggregation.
                    "official_url": None,

                    "location_name": location_name,
                    "street": None,
                    "postal_code": None,
                    "city": city,

                    "source": {
                        "authority":
                            self.config.get("authority"),
                        "url": dhbw_url,
                        "source_type": "html_multi_page",
                        "retrieved_at":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),
                        "category":
                            "Duale Hochschule Baden-Württemberg",
                        "location_url":
                            official_url,
                    },
                })

        print(
            f"[BW] Parsed {len(rows)} source rows "
            f"from official MWK pages"
        )

        return rows

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    @staticmethod
    def _extract_section_links(
        soup,
        page_url,
        heading_text,
    ):

        target = None

        for heading in soup.find_all("h2"):

            text = " ".join(
                heading.stripped_strings
            ).strip()

            if text == heading_text:
                target = heading
                break

        if target is None:
            raise RuntimeError(
                f"Could not find section: {heading_text}"
            )

        links = []
        seen = set()

        for element in target.find_all_next():

            if (
                element is not target
                and element.name == "h2"
            ):
                break

            if element.name != "a":
                continue

            href = element.get("href")

            if not href:
                continue

            name = " ".join(
                element.stripped_strings
            ).strip()

            if not name:
                continue

            official_url = urljoin(
                page_url,
                href
            )

            key = (
                name,
                official_url
            )

            if key in seen:
                continue

            seen.add(key)

            links.append(
                (
                    name,
                    official_url,
                )
            )

        return links
