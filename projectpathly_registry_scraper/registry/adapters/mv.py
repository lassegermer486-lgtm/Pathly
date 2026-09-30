import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter


class MecklenburgVorpommernAdapter(RegistryAdapter):

    MAIN_URL = (
        "https://www.regierung-mv.de/"
        "Landesregierung/wkm/Wissenschaft/Hochschule/"
    )

    def __init__(self, state_code, config):
        super().__init__(state_code, config)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
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

        rows = self._parse_profile_higher_education(soup)

        # The public-administration university is described
        # in the official overview text but does not currently
        # have its own profile card on the page.
        rows.extend(
            self._parse_public_administration(soup)
        )

        # Additional higher-education providers / study locations
        # discovered through official/public MV location sources.
        #
        # Registry phase = maximum recall. These entries may also
        # be discovered through another German state later and are
        # intentionally kept until nationwide deduplication.
        rows.extend([
            self._make_external_row(
                name="Hochschule der Bundesagentur für Arbeit",
                official_url="https://www.hdba.de/",
                city="Schwerin",
                source_url=(
                    "https://www.schwerin.de/"
                    "mein-schwerin/lernen/hochschulen-forschung/"
                    "hochschule/"
                ),
                source_authority="Landeshauptstadt Schwerin",
            ),
            self._make_external_row(
                name="HFH Hamburger Fern-Hochschule",
                official_url="https://www.hfh-fernstudium.de/",
                city="Schwerin",
                source_url=(
                    "https://www.schwerin.de/"
                    "mein-schwerin/lernen/hochschulen-forschung/"
                    "hochschule/"
                ),
                source_authority="Landeshauptstadt Schwerin",
            ),
            self._make_external_row(
                name="Internationale Studien- und Berufsakademie ISBA",
                official_url=(
                    "https://www.studieren-in-schwerin.de/"
                    "hochschulen/isba/"
                ),
                city="Schwerin",
                source_url=(
                    "https://www.schwerin.de/"
                    "mein-schwerin/lernen/hochschulen-forschung/"
                    "hochschule/"
                ),
                source_authority="Landeshauptstadt Schwerin",
            ),
            self._make_external_row(
                name="Fachhochschule des Mittelstands",
                official_url="https://www.fhm-campus.de/",
                city="Rostock",
                source_url=(
                    "https://www.fhm-campus.de/"
                    "dein-campus/campus-rostock/"
                ),
                source_authority=(
                    "Fachhochschule des Mittelstands"
                ),
            ),
        ])

        rows = self._deduplicate(rows)

        print(
            f"[MV] Parsed {len(rows)} institutions "
            "from official MV government source"
        )

        return rows

    def _parse_profile_higher_education(self, soup):
        rows = []

        profile_heading = None

        for heading in soup.find_all("h2"):
            text = self._clean(heading.get_text(" ", strip=True))

            if text == "Profile der Hochschulen":
                profile_heading = heading
                break

        if not profile_heading:
            raise RuntimeError(
                "MV university profile section not found"
            )

        node = profile_heading.find_next()

        while node:
            if (
                node.name == "h2"
                and node is not profile_heading
            ):
                break

            if node.name == "h4":
                name = self._clean(
                    node.get_text(" ", strip=True)
                )

                link = node.find("a", href=True)

                if not link:
                    link = node.find_next("a", href=True)

                official_url = None

                if link:
                    official_url = urljoin(
                        self.MAIN_URL,
                        link["href"],
                    )

                if self._looks_like_university(name):
                    rows.append(
                        self._make_row(
                            name=name,
                            official_url=official_url,
                        )
                    )

            node = node.find_next()

        return rows

    def _parse_public_administration(self, soup):
        target = None

        for text_node in soup.find_all(string=True):
            text = self._clean(str(text_node))

            if (
                "Fachhochschule für öffentliche Verwaltung"
                in text
                and "Güstrow" in text
            ):
                target = text
                break

        if not target:
            print(
                "[MV] WARNING: public-administration "
                "university reference not found"
            )
            return []

        return [
            self._make_row(
                name=(
                    "Fachhochschule für öffentliche Verwaltung, "
                    "Polizei und Rechtspflege Mecklenburg-Vorpommern"
                ),
                official_url=None,
                city="Güstrow",
                institution_type="public_administration",
            )
        ]

    def _make_external_row(
        self,
        name,
        official_url,
        city,
        source_url,
        source_authority,
    ):
        return {
            "name": name,
            "official_url": official_url,
            "institution_type": "unknown",
            "ownership": "unknown",
            "recognition_status": "unknown",
            "location_name": None,
            "city": city,
            "location_state": "DE-MV",
            "location_type": "study_location",
            "location_status": "candidate",
            "source": {
                "authority": source_authority,
                "source_url": source_url,
                "source_category": "location_discovery",
            },
            "location_source_url": source_url,
            "location_source_authority": source_authority,
        }

    def _make_row(
        self,
        name,
        official_url=None,
        city=None,
        institution_type=None,
    ):
        if institution_type is None:
            institution_type = self._institution_type(name)

        return {
            "name": name,
            "official_url": official_url,
            "institution_type": institution_type,
            "ownership": "public",
            "recognition_status": "state",
            "location_name": None,
            "city": city,
            "location_state": "DE-MV",
            "location_type": "main",
            "location_status": "confirmed",
            "source": {
                "authority": (
                    "Ministerium für Wissenschaft, Kultur, "
                    "Bundes- und Europaangelegenheiten "
                    "Mecklenburg-Vorpommern"
                ),
                "source_url": self.MAIN_URL,
                "source_category": "official_state_registry",
            },
            "location_source_url": self.MAIN_URL,
            "location_source_authority": (
                "Land Mecklenburg-Vorpommern"
            ),
        }

    @staticmethod
    def _institution_type(name):
        lower = name.lower()

        if "musik und theater" in lower:
            return "art_music"

        if "universität" in lower:
            return "university"

        if "hochschule" in lower:
            return "university_of_applied_sciences"

        return "unknown"

    @staticmethod
    def _looks_like_university(name):
        lower = name.lower()

        return any(
            marker in lower
            for marker in (
                "universität",
                "hochschule",
            )
        )

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
