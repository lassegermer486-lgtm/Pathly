import re
import requests
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter


class ThueringenAdapter(RegistryAdapter):

    SOURCE_URL = (
        "https://statistik.thueringen.de/DatenBank/"
        "TabAnzeige.asp?auswahlnr=hs2090"
        "&tabelle=NT001313"
        "&zeit=2024%7C%7Cws"
    )

    AUTHORITY = "Thüringer Landesamt für Statistik"

    CATEGORY_MAP = {
        "universitäten": "university",
        "kunsthochschulen": "art_music",
        "verwaltungsfachhochschulen": "public_administration",
        "fachhochschulen": "university_of_applied_sciences",
    }

    @staticmethod
    def _clean(value):
        if not value:
            return None

        value = value.replace("\xa0", " ")
        value = re.sub(r"\s+", " ", value)

        return value.strip()

    @staticmethod
    def _is_summary_row(name):
        if not name:
            return True

        lower = name.lower()

        return (
            " - zusammen" in lower
            or lower.endswith(" zusammen")
            or lower == "hochschulen insgesamt"
            or lower == "fächergruppen zusammen"
        )

    @staticmethod
    def _ownership(name, institution_type):
        lower = name.lower()

        if (
            "priv." in lower
            or "private" in lower
            or "srh " in lower
            or lower.startswith("iu ")
            or lower.startswith("hmu ")
        ):
            return "private"

        if institution_type == "public_administration":
            return "public"

        return "public"

    @staticmethod
    def _clean_institution_name(name):
        # Remove statistical annotations without hardcoding institutions.
        name = re.sub(
            r"\s*\(Priv\.\s*FH\)\s*",
            " ",
            name,
            flags=re.IGNORECASE,
        )

        name = re.sub(
            r"\s*\*+\)?\s*$",
            "",
            name,
        )

        return re.sub(r"\s+", " ", name).strip()

    def fetch(self):
        response = requests.get(
            self.SOURCE_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.content,
            "html.parser",
        )

        table = soup.find("table")

        if table is None:
            raise RuntimeError(
                "No university statistics table found "
                "on Thüringer Landesamt für Statistik source."
            )

        rows = []
        current_type = "unknown"

        for tr in table.find_all("tr"):
            cells = tr.find_all(["th", "td"])

            if not cells:
                continue

            name = self._clean(
                cells[0].get_text(" ", strip=True)
            )

            if not name:
                continue

            lower = name.lower()

            # Category rows dynamically determine the institution type
            # for all following institutions.
            category_found = False

            for category, institution_type in self.CATEGORY_MAP.items():
                if (
                    lower.startswith(category)
                    and "zusammen" in lower
                ):
                    current_type = institution_type
                    category_found = True
                    break

            if category_found:
                continue

            if self._is_summary_row(name):
                continue

            # Ignore header/meta rows.
            if lower in {
                "hochschulart hochschule",
                "anzahl",
                "insgesamt",
            }:
                continue

            if lower.startswith("202"):
                continue

            # Real institution rows contain statistical values
            # in additional table cells.
            if len(cells) < 2:
                continue

            name = self._clean_institution_name(name)

            rows.append(
                {
                    "name": name,
                    "institution_type": current_type,
                    "ownership": self._ownership(
                        name,
                        current_type,
                    ),
                    "recognition_status": "official_statistics",
                    "official_url": None,

                    "location_name": None,
                    "city": None,
                    "location_state": "DE-TH",
                    "location_type": "main",
                    "location_status": "confirmed",

                    "source": {
                        "authority": self.AUTHORITY,
                        "source_url": self.SOURCE_URL,
                        "source_category": current_type,
                    },

                    "location_source_url": self.SOURCE_URL,
                    "location_source_authority": self.AUTHORITY,
                }
            )

        # Detect repeated institution names that differ only by
        # a trailing "in <location>". The official statistics may
        # list one institution once per campus/location.
        base_groups = {}

        for row in rows:
            match = re.match(
                r"^(?P<base>.+?)\s+in\s+(?P<city>[^,]+)$",
                row["name"],
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            base = match.group("base").strip()
            city = match.group("city").strip()

            base_groups.setdefault(base, []).append(
                (row, city)
            )

        for base, matches in base_groups.items():
            # Only collapse the suffix when the same base occurs
            # multiple times. A single "... in Erfurt/Gera" entry
            # remains part of the official institution name.
            if len(matches) < 2:
                continue

            for row, city in matches:
                row["name"] = base
                row["location_name"] = city
                row["city"] = city
                row["location_type"] = "campus"

        print(
            f"[TH] Parsed {len(rows)} institution rows "
            f"from official Thüringen statistics"
        )

        return rows
