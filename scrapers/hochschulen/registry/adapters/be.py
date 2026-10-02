from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests

from registry import http_client
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter
from registry.normalize import is_host_within


class BerlinAdapter(RegistryAdapter):

    BASE_URL = (
        "https://www.berlin.de/sen/wissenschaft/"
        "einrichtungen/hochschulen/"
    )

    PAGES = [
        {
            "path": "universitaeten/",
            "category": "Universitäten",
            "institution_type": "university",
            "ownership": "public",
        },
        {
            "path": "hochschulen-fuer-angewandte-wissenschaften/",
            "category": "Hochschulen für angewandte Wissenschaften",
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
        },
        {
            "path": "kunsthochschulen/",
            "category": "Kunsthochschulen",
            "institution_type": "art_music_university",
            "ownership": "public",
        },
        {
            "path": "konfessionelle-hochschulen/",
            "category": "Konfessionelle Hochschulen",
            "institution_type": "university_of_applied_sciences",
            "ownership": "church",
        },
        {
            "path": "private-hochschulen/",
            "category": (
                "Vom Land Berlin staatlich anerkannte "
                "Hochschulen in freier Trägerschaft"
            ),
            "institution_type": "university",
            "ownership": "private",
        },
    ]

    PRIVATE_HEADING = (
        "Vom Land Berlin staatlich anerkannte "
        "Hochschulen in freier Trägerschaft"
    )

    STOP_HEADINGS = {
        "Senatsverwaltung für Wissenschaft, Gesundheit und Pflege",
        "Weitere Informationen zu diesem Auftritt",
        "Weitere Informationen zu Berlin.de",
    }

    # Some official institution websites are not linked cleanly
    # from the Berlin pages. These can be enriched later.
    URL_OVERRIDES = {
        "Charité - Universitätsmedizin Berlin":
            "http://www.charite.de",
    }

    def fetch(self):
        rows = []

        retrieved_at = datetime.now(
            timezone.utc
        ).isoformat()

        raw_dir = Path("data/raw")
        raw_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        for meta in self.PAGES:

            url = urljoin(
                self.BASE_URL,
                meta["path"]
            )

            response = http_client.get(
                url,
                headers={
                    "User-Agent": self.config.get(
                        "user_agent",
                        "ProjectPathlyRegistry/0.1"
                    )
                },
                timeout=30,
            )

            response.raise_for_status()

            snapshot = (
                raw_dir
                / f"DE-BE_{meta['path'].strip('/').replace('/', '_')}.html"
            )

            snapshot.write_text(
                response.text,
                encoding="utf-8"
            )

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            if meta["path"] == "private-hochschulen/":
                page_rows = self._parse_private_page(
                    soup,
                    url,
                    meta,
                    retrieved_at,
                )
            else:
                page_rows = self._parse_heading_page(
                    soup,
                    url,
                    meta,
                    retrieved_at,
                )

            rows.extend(page_rows)

        # Remove duplicate institutional appearances.
        # Example: Universität der Künste appears under
        # universities and art universities.
        deduped = {}

        for row in rows:
            key = self._canonical_key(
                row["name"]
            )

            if key not in deduped:
                deduped[key] = row
                continue

            existing = deduped[key]

            # Prefer the more specific art/music classification
            # for institutions appearing in multiple categories.
            if (
                row["institution_type"]
                == "art_music_university"
            ):
                deduped[key] = row

            # Preserve a URL if only one occurrence has one.
            elif (
                not existing.get("official_url")
                and row.get("official_url")
            ):
                existing["official_url"] = row["official_url"]
                existing["official_url_source"] = row[
                    "official_url_source"
                ]

        result = list(
            deduped.values()
        )

        print(
            f"[BE] Parsed {len(rows)} source rows "
            f"→ {len(result)} unique institutions "
            f"from official Berlin pages"
        )

        return result

    def _parse_heading_page(
        self,
        soup,
        source_url,
        meta,
        retrieved_at,
    ):
        rows = []

        h1 = soup.find("h1")

        if not h1:
            return rows

        for h2 in soup.find_all("h2"):

            name = self._clean(
                h2.get_text(
                    " ",
                    strip=True
                )
            )

            if not name:
                continue

            if name in {
                "Inhaltsverzeichnis",
                *self.STOP_HEADINGS,
            }:
                continue

            ownership = meta["ownership"]
            institution_type = meta[
                "institution_type"
            ]

            if name == "Hochschule des Bundes für öffentliche Verwaltung":
                ownership = "federal"
                institution_type = (
                    "university_of_public_administration"
                )

            if name == "Charité - Universitätsmedizin Berlin":
                institution_type = "university"

            official_url = (
                self.URL_OVERRIDES.get(name)
                or self._find_external_link_after_heading(h2)
            )

            rows.append(
                self._row(
                    name=name,
                    official_url=official_url,
                    institution_type=institution_type,
                    ownership=ownership,
                    category=meta["category"],
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
            )

        return rows

    def _parse_private_page(
        self,
        soup,
        source_url,
        meta,
        retrieved_at,
    ):
        rows = []

        heading = None

        for h2 in soup.find_all("h2"):
            text = self._clean(
                h2.get_text(
                    " ",
                    strip=True
                )
            )

            if text == self.PRIVATE_HEADING:
                heading = h2
                break

        if heading is None:
            return rows

        seen = set()

        for element in heading.find_all_next():

            if (
                element is not heading
                and element.name == "h2"
            ):
                break

            if element.name != "a":
                continue

            href = element.get("href")

            if not href:
                continue

            name = self._clean(
                element.get_text(
                    " ",
                    strip=True
                )
            )

            if not name:
                continue

            official_url = urljoin(
                source_url,
                href
            )

            if is_host_within(official_url, "berlin.de"):
                continue

            if official_url.startswith(
                ("mailto:", "tel:")
            ):
                continue

            key = self._canonical_key(
                name
            )

            if key in seen:
                continue

            seen.add(key)

            rows.append(
                self._row(
                    name=name,
                    official_url=official_url,
                    institution_type=meta[
                        "institution_type"
                    ],
                    ownership=meta[
                        "ownership"
                    ],
                    category=meta["category"],
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
            )

        return rows

    def _find_external_link_after_heading(
        self,
        heading,
    ):
        """
        Each institution block ends with its address line, which
        starts with a link to the website whose text is the
        institution name ("Freie Universität Berlin: Kaiserswerther
        Straße 16/18 ..."). Earlier links in the block can point to
        affiliated institutes, e.g. the Jazz-Institut under UdK.
        """
        heading_key = self._canonical_key(
            self._clean(
                heading.get_text(
                    " ",
                    strip=True
                )
            ) or ""
        )

        candidates = []

        for element in heading.find_all_next():

            if (
                element is not heading
                and element.name == "h2"
            ):
                break

            if element.name != "a":
                continue

            href = element.get("href")

            if not href:
                continue

            absolute = urljoin(
                self.BASE_URL,
                href
            ).strip()

            if not absolute.startswith(
                ("http://", "https://")
            ):
                continue

            # Host check, not substring: fu-berlin.de and
            # htw-berlin.de are institution websites.
            if is_host_within(absolute, "berlin.de"):
                continue

            text_key = self._canonical_key(
                (
                    self._clean(
                        element.get_text(
                            " ",
                            strip=True
                        )
                    ) or ""
                ).rstrip(":")
            )

            candidates.append(
                (text_key, absolute)
            )

        for text_key, absolute in candidates:
            if text_key == heading_key:
                return absolute

        for text_key, absolute in candidates:
            if text_key.startswith(heading_key):
                return absolute

        return candidates[0][1] if candidates else None

    def _row(
        self,
        *,
        name,
        official_url,
        institution_type,
        ownership,
        category,
        source_url,
        retrieved_at,
    ):
        return {
            "name": name,
            "official_url": official_url,
            "official_url_source": (
                source_url
                if official_url
                else None
            ),
            "institution_type": institution_type,
            "ownership": ownership,
            "recognition_status": (
                "state_recognized"
                if ownership == "private"
                else "unknown"
            ),
            "location_name": None,
            "city": "Berlin",
            "postal_code": None,
            "street": None,
            "location_type": "main",
            "source": {
                "authority": (
                    "Land Berlin – Senatsverwaltung "
                    "für Wissenschaft"
                ),
                "url": source_url,
                "source_type": "official_state_registry",
                "retrieved_at": retrieved_at,
                "category": category,
            },
        }

    @staticmethod
    def _clean(value):
        if not value:
            return None

        return " ".join(
            value.split()
        ).strip()

    @staticmethod
    def _canonical_key(name):
        import re

        key = name.lower()
        key = key.replace("–", "-").replace("—", "-")

        # Remove abbreviations in parentheses so that, for example,
        # "Universität der Künste Berlin" and
        # "Universität der Künste Berlin (UdK)"
        # resolve to the same institution.
        key = re.sub(r"\s*\([^)]*\)\s*", " ", key)

        return " ".join(key.split()).strip()
