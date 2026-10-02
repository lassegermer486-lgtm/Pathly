import re
from urllib.parse import urljoin, urlparse

import requests

from registry import http_client
from bs4 import BeautifulSoup

from registry.adapters.base import RegistryAdapter
from registry.utils.matching import match_name


class ThueringenAdapter(RegistryAdapter):

    SOURCE_URL = (
        "https://statistik.thueringen.de/DatenBank/"
        "TabAnzeige.asp?auswahlnr=hs2090"
        "&tabelle=NT001313"
        "&zeit=2024%7C%7Cws"
    )

    AUTHORITY = "Thüringer Landesamt für Statistik"

    # The statistics table has no websites. The state's study portal
    # (run by the Thuringian universities' marketing network under
    # supervision of the Thuringian science ministry) links every
    # institution profile to the institution's website.
    PORTAL_URL = (
        "https://campus-thueringen.de/hochschulen-in-thueringen/"
    )

    HEADERS = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    }

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
        response = http_client.get(
            self.SOURCE_URL,
            timeout=30,
            headers=self.HEADERS,
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

        self._attach_portal_websites(rows)

        with_url = sum(1 for row in rows if row["official_url"])

        print(
            f"[TH] Parsed {len(rows)} institution rows "
            f"({with_url} with website) "
            f"from official Thüringen statistics"
        )

        return rows

    def _attach_portal_websites(self, rows):
        try:
            portal = self._fetch_portal_websites()
        except requests.RequestException as exc:
            print(
                f"[WARN] TH: study portal unavailable, "
                f"websites stay empty | {exc}"
            )
            return

        for row in rows:
            portal_name = match_name(row["name"], list(portal))

            if portal_name is None:
                continue

            website, profile_url = portal[portal_name]
            row["official_url"] = website
            row["official_url_source"] = profile_url

    def _fetch_portal_websites(self):
        """
        Returns {portal institution name: (website, profile_url)}.
        """
        response = http_client.get(
            self.PORTAL_URL,
            timeout=30,
            headers=self.HEADERS,
        )
        response.raise_for_status()

        profiles = self.extract_portal_profiles(
            response.text,
            response.url,
        )

        result = {}

        for name, profile_url in profiles.items():
            try:
                profile = http_client.get(
                    profile_url,
                    timeout=30,
                    headers=self.HEADERS,
                )
                profile.raise_for_status()
            except requests.RequestException as exc:
                print(
                    f"[WARN] TH: portal profile failed: "
                    f"{profile_url} | {exc}"
                )
                continue

            website = self.extract_profile_website(profile.text)

            if website:
                result[name] = (website, profile_url)

        return result

    @classmethod
    def extract_portal_profiles(cls, html, base_url):
        """
        Institution profile links from the portal overview's main
        content. City pages are only linked from the navigation.
        """
        soup = BeautifulSoup(html, "html.parser")
        main = soup.find("main") or soup
        base_path = urlparse(base_url).path.rstrip("/") + "/"

        profiles = {}

        for link in main.find_all("a", href=True):
            url = urljoin(base_url, link["href"])
            path = urlparse(url).path

            if not path.startswith(base_path) or path == base_path:
                continue

            # Card links also contain the photo credit ("Bild: ...").
            name = cls._clean(link.get_text(" ", strip=True))
            name = re.sub(r"\s+Bild:.*$", "", name or "")

            if name and name not in profiles:
                profiles[name] = url

        return profiles

    @staticmethod
    def extract_profile_website(html):
        soup = BeautifulSoup(html, "html.parser")

        # The first direct link in ul.links is the website; social
        # media icons sit in a nested ul.social.
        link = soup.select_one("ul.links > li > a[href]")

        if link is None:
            return None

        href = link["href"].strip()

        if not href.startswith(("http://", "https://")):
            return None

        return href
