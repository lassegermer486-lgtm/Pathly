from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class BrandenburgAdapter(RegistryAdapter):

    BASE_URL = "https://mwfk.brandenburg.de"

    PAGES = {
        "universities": {
            "url": (
                "https://mwfk.brandenburg.de/mwfk/de/"
                "wissenschaft/hochschulen/universitaeten/"
            ),
            "institution_type": "university",
            "ownership": "public",
            "recognition_status": "public",
            "category": "Universitäten",
        },
        "uas": {
            "url": (
                "https://mwfk.brandenburg.de/mwfk/de/"
                "wissenschaft/hochschulen/fachhochschulen/"
            ),
            "institution_type": "university_of_applied_sciences",
            "ownership": "public",
            "recognition_status": "public",
            "category": "Fachhochschulen",
        },
        "private_universities": {
            "url": (
                "https://mwfk.brandenburg.de/mwfk/de/"
                "wissenschaft/hochschulen/"
                "nichtstaatliche-universitaeten/"
            ),
            "institution_type": "university",
            "ownership": "private_or_church",
            "recognition_status": "state_recognized",
            "category": "Nichtstaatliche Universitäten",
        },
        "private_uas": {
            "url": (
                "https://mwfk.brandenburg.de/mwfk/de/"
                "wissenschaft/hochschulen/"
                "nichtstaatliche-fachhochschulen/"
            ),
            "institution_type": "university_of_applied_sciences",
            "ownership": "private_or_church",
            "recognition_status": "state_recognized",
            "category": "Nichtstaatliche Fachhochschulen",
        },
    }

    SPECIAL_PROFILE_PATHS = {
        "/mwfk/de/wissenschaft/"
        "medizinische-universitaet-lausitz-carl-thiem/"
    }

    # Canonical institution names for public Brandenburg
    # universities. MWFK content blocks sometimes use campus
    # labels or abbreviations instead of the institution name.
    CANONICAL_NAMES = {
        "/mwfk/de/wissenschaft/hochschulen/universitaeten/btu/":
            "Brandenburgische Technische Universität Cottbus-Senftenberg",

        "/mwfk/de/wissenschaft/hochschulen/universitaeten/europa-universitaet-viadrina/":
            "Europa-Universität Viadrina",

        "/mwfk/de/wissenschaft/hochschulen/universitaeten/filmuniversitaet-babelsberg/":
            "Filmuniversität Babelsberg Konrad Wolf",

        "/mwfk/de/wissenschaft/hochschulen/universitaeten/universitaet-potsdam/":
            "Universität Potsdam",

        "/mwfk/de/wissenschaft/medizinische-universitaet-lausitz-carl-thiem/":
            "Medizinische Universität Lausitz – Carl Thiem",

        "/mwfk/de/wissenschaft/hochschulen/fachhochschulen/fachhochschule-potsdam/":
            "Fachhochschule Potsdam",

        "/mwfk/de/wissenschaft/hochschulen/fachhochschulen/hnee/":
            "Hochschule für nachhaltige Entwicklung Eberswalde",

        "/mwfk/de/wissenschaft/hochschulen/fachhochschulen/th-brandenburg/":
            "Technische Hochschule Brandenburg",

        "/mwfk/de/wissenschaft/hochschulen/fachhochschulen/th-wildau/":
            "Technische Hochschule Wildau",
    }

    def fetch(self):

        session = requests.Session()

        session.headers.update({
            "User-Agent":
                "ProjectPathly Registry Research/1.0"
        })

        retrieved_at = datetime.now(
            timezone.utc
        ).isoformat()

        rows = []

        for page_key, meta in self.PAGES.items():

            response = session.get(
                meta["url"],
                timeout=30
            )

            response.raise_for_status()

            self.snapshot(
                f"{self.state_code}_{page_key}.html",
                response.text
            )

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            profiles = self._find_profiles(
                soup,
                meta["url"],
                page_key
            )

            print(
                f"[BB] {page_key}: "
                f"{len(profiles)} profiles"
            )

            for profile in profiles:

                name = profile["name"]
                profile_url = profile["url"]

                institution_type = meta[
                    "institution_type"
                ]

                # The Filmuniversität is listed by Brandenburg
                # on the university page but is semantically
                # an art/film university.
                if (
                    "Filmuniversität Babelsberg"
                    in name
                ):
                    institution_type = (
                        "art_music_university"
                    )

                rows.append({
                    "name": name,
                    "official_url": None,
                    "institution_type":
                        institution_type,
                    "ownership":
                        meta["ownership"],
                    "recognition_status":
                        meta["recognition_status"],
                    "location_name": None,
                    "city": None,
                    "postal_code": None,
                    "street": None,
                    "location_type": "main",
                    "source": {
                        "authority": (
                            "Land Brandenburg – "
                            "Ministerium für Wissenschaft, "
                            "Forschung und Kultur"
                        ),
                        "url": profile_url,
                        "source_type":
                            "official_state_registry",
                        "retrieved_at":
                            retrieved_at,
                        "category":
                            meta["category"],
                    },
                })

        deduped = {}

        for row in rows:

            key = self._canonical_key(
                row["name"]
            )

            if key not in deduped:
                deduped[key] = row
                continue

            existing = deduped[key]

            if (
                existing["institution_type"]
                != "art_music_university"
                and row["institution_type"]
                == "art_music_university"
            ):
                deduped[key] = row

        # Additional state universities outside the regular
        # MWFK university overview.
        #
        # These are special-purpose public universities under
        # other state ministries and therefore do not appear in
        # the four regular MWFK category lists.

        special_institutions = [
            {
                "name": "Hochschule der Polizei des Landes Brandenburg",
                "official_url": "https://www.hpolbb.de",
                "institution_type": "university_of_public_administration",
                "ownership": "public",
                "recognition_status": "public",
                "location_name": None,
                "city": "Oranienburg",
                "postal_code": "16515",
                "street": "Bernauer Straße 146",
                "location_type": "main",
                "source": {
                    "authority": "Land Brandenburg",
                    "url": (
                        "https://bravors.brandenburg.de/"
                        "gesetze/bbgpolhg/3"
                    ),
                    "source_type": "official_state_law",
                    "retrieved_at": retrieved_at,
                    "category": "Verwaltungshochschule",
                },
            },
            {
                "name": "Fachhochschule für Finanzen des Landes Brandenburg",
                "official_url": "https://fhf.brandenburg.de",
                "institution_type": "university_of_public_administration",
                "ownership": "public",
                "recognition_status": "public",
                "location_name": None,
                "city": "Königs Wusterhausen",
                "postal_code": "15711",
                "street": "Schillerstraße 6",
                "location_type": "main",
                "source": {
                    "authority": "Land Brandenburg",
                    "url": (
                        "https://fhf.brandenburg.de/fhf/de/"
                        "studium/fachhochschule-fuer-finanzen/"
                    ),
                    "source_type": "official_state_registry",
                    "retrieved_at": retrieved_at,
                    "category": "Verwaltungshochschule",
                },
            },
        ]

        for row in special_institutions:
            key = self._canonical_key(
                row["name"]
            )

            if key not in deduped:
                deduped[key] = row

        result = list(
            deduped.values()
        )

        print(
            f"[BB] Parsed {len(rows)} profile rows "
            f"→ {len(result)} unique institutions "
            f"from official MWFK pages"
        )

        return result

    def _find_profiles(
        self,
        soup,
        overview_url,
        page_key,
    ):

        profiles = []
        seen = set()

        expected_fragment = {
            "universities":
                "/wissenschaft/hochschulen/"
                "universitaeten/",

            "uas":
                "/wissenschaft/hochschulen/"
                "fachhochschulen/",

            "private_universities":
                "/wissenschaft/hochschulen/"
                "nichtstaatliche-universitaeten/",

            "private_uas":
                "/wissenschaft/hochschulen/"
                "nichtstaatliche-fachhochschulen/",
        }[page_key]

        for a in soup.find_all(
            "a",
            href=True
        ):

            text = self._clean(
                a.get_text(
                    " ",
                    strip=True
                )
            )

            if text != "zum Hochschulprofil":
                continue

            absolute = urljoin(
                overview_url,
                a["href"]
            )

            path = urlparse(
                absolute
            ).path

            valid = (
                expected_fragment in path
                or (
                    page_key == "universities"
                    and path
                    in self.SPECIAL_PROFILE_PATHS
                )
            )

            if not valid:
                continue

            if absolute in seen:
                continue

            name = (
                self.CANONICAL_NAMES.get(path)
                or self._name_from_profile_link(a)
            )

            if not name:
                print(
                    "[WARN] BB: could not extract "
                    f"institution name from {absolute}"
                )
                continue

            seen.add(absolute)

            profiles.append({
                "name": name,
                "url": absolute,
            })

        return profiles

    def _name_from_profile_link(
        self,
        link,
    ):

        # Prefer the visible canonical institution name from
        # the surrounding MWFK content block. The link title
        # sometimes contains only abbreviations such as
        # "BTU", "HNEE" or "TH Wildau".
        container = link.find_parent(
            "div",
            class_=lambda c:
                c and "columns" in c
        )

        if container:

            # The same institution name can occur twice for
            # responsive layouts. The first strong element is
            # sufficient.
            strong = container.find(
                "strong"
            )

            if strong:

                name = self._clean(
                    strong.get_text(
                        " ",
                        strip=True
                    )
                )

                if name:
                    return name

            # Second fallback inside the content block:
            # image title contains the visible institution name.
            image = container.find(
                "img",
                title=True
            )

            if image:

                name = self._clean(
                    image.get("title")
                )

                if name:
                    return name

        # Final fallback: MWFK profile-link title.
        title = self._clean(
            link.get("title")
        )

        if title:

            prefix = "Link zur Seite:"

            if title.startswith(prefix):

                name = self._clean(
                    title[len(prefix):]
                )

                if name:
                    return name

        return None

    @staticmethod
    def _clean(value):

        if not value:
            return None

        return " ".join(
            value.split()
        ).strip()

    @staticmethod
    def _canonical_key(name):

        key = name.lower()

        key = key.replace(
            "–",
            "-"
        ).replace(
            "—",
            "-"
        )

        key = re.sub(
            r"\s*\([^)]*\)\s*",
            " ",
            key
        )

        return " ".join(
            key.split()
        ).strip()
