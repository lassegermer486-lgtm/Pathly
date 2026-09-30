from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class BayernAdapter(RegistryAdapter):

    BASE = (
        "https://www.stmwk.bayern.de/ministerium/"
        "hochschule-und-forschung/hochschulen/"
    )

    PAGES = {
        "universitaeten.html": {
            "sections": {
                "Staatliche Universitäten": {
                    "institution_type": "university",
                    "ownership": "public",
                },
                "Nichtstaatliche Universitäten und wissenschaftliche Hochschulen": {
                    "institution_type": "university",
                    "ownership": "private_or_other",
                },
            }
        },

        "hochschulen-fuer-angewandte-wissenschaften.html": {
            "sections": {
                "Staatliche Hochschulen für angewandte Wissenschaften - Technische Hochschulen - Fachhochschulen": {
                    "institution_type": "university_of_applied_sciences",
                    "ownership": "public",
                },
                "Nichtstaatliche Fachhochschulen und Universitäten mit Fachhochschulstudiengängen": {
                    "institution_type": "university_of_applied_sciences",
                    "ownership": "private_or_other",
                },
            }
        },

        "kunsthochschulen.html": {
            "sections": {
                "Kunsthochschulen": {
                    "institution_type": "art_music_university",
                    "ownership": "public",
                },
                "Nichtstaatliche Kunsthochschulen": {
                    "institution_type": "art_music_university",
                    "ownership": "private_or_other",
                },
            }
        },
    }

    # These are not separate universities.
    #
    # KU Eichstätt-Ingolstadt and Universität der Bundeswehr München
    # already occur on the university page. Their appearances on the
    # HAW page therefore must not create additional institutions.
    EXCLUDED_NAMES = {
        "Katholische Universität Eichstätt-Ingolstadt: Fakultät für Religionspädagogik/Kirchliche Bildungsarbeit",
        "Katholische Universität Eichstätt-Ingolstadt: Fakultät für Soziale Arbeit",
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
        raw_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        rows = []

        for page, page_config in self.PAGES.items():

            url = urljoin(
                self.BASE,
                page
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()

            snapshot_name = (
                "DE-BY_"
                + page.replace(".html", "")
                + ".html"
            )

            (
                raw_dir /
                snapshot_name
            ).write_bytes(
                response.content
            )

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            for section_name, meta in (
                page_config["sections"].items()
            ):

                links = self._extract_section_links(
                    soup=soup,
                    page_url=response.url,
                    heading_text=section_name,
                )

                for name, official_url in links:

                    # Do not treat KU Eichstätt-Ingolstadt faculties
                    # as separate universities.
                    if official_url.rstrip("/") in {
                        "https://www.ku.de/rpf",
                        "https://www.ku.de/fsa",
                    }:
                        continue

                    # UniBw appears both on the university and HAW pages.
                    # Keep the university entry, skip only the HAW duplicate.
                    if (
                        page == "hochschulen-fuer-angewandte-wissenschaften.html"
                        and name == "Universität der Bundeswehr München"
                    ):
                        continue

                    if (
                        page == "hochschulen-fuer-angewandte-wissenschaften.html"
                        and name == "Universität der Bundeswehr München"
                    ):
                        continue

                    # Supporting documents are not
                    # university registry entries.
                    if (
                        official_url
                        .lower()
                        .split("?")[0]
                        .endswith(".pdf")
                    ):
                        continue

                    rows.append({
                        "name": name,
                        "country": "DE",
                        "state": "DE-BY",

                        "category": section_name,

                        "institution_type":
                            meta["institution_type"],

                        "ownership":
                            meta["ownership"],

                        "recognition_status":
                            "unknown",

                        "official_url":
                            official_url,

                        "location_name":
                            None,

                        "street":
                            None,

                        "postal_code":
                            None,

                        "city":
                            None,

                        "source": {
                            "authority":
                                self.config.get(
                                    "authority"
                                ),

                            "url":
                                url,

                            "source_type":
                                "html_multi_page",

                            "retrieved_at":
                                datetime.now(
                                    timezone.utc
                                ).isoformat(),

                            "category":
                                section_name,
                        },
                    })

        print(
            f"[BY] Parsed {len(rows)} source rows "
            f"from official StMWK pages"
        )

        return rows

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
                f"Could not find section: "
                f"{heading_text}"
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
