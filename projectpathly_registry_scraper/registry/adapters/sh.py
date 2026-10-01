import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class SchleswigHolsteinAdapter(RegistryAdapter):
    """
    Registry adapter for DE-SH.

    Official source:
    Land Schleswig-Holstein higher-education pages.

    Discovery strategy:
    - Parse structured university tab blocks.
    - Each institution is represented by:
        h2.l-tab-text__title.heading.inactive-control
        +
        following div.l-tab-text__wrapper.tabs-wrapper
    - Extract institution name from the heading and official website
      from the corresponding content block.

    Recall-first:
    Nationwide deduplication/validation happens later.
    """

    BASE = "https://www.schleswig-holstein.de"

    SOURCE_URLS = [
        (
            BASE
            + "/DE/landesregierung/themen/bildung-hochschulen/"
            "hochschule_allgemein/hochschulen/universitaeten"
        ),
        (
            BASE
            + "/DE/landesregierung/themen/bildung-hochschulen/"
            "hochschule_allgemein/hochschulen/staatliche_fachhochschulen"
        ),
        (
            BASE
            + "/DE/landesregierung/themen/bildung-hochschulen/"
            "hochschule_allgemein/hochschulen/kunst_musikhochschulen"
        ),
        (
            BASE
            + "/DE/landesregierung/themen/bildung-hochschulen/"
            "hochschule_allgemein/hochschulen/private_fachhochschulen"
        ),
        (
            BASE
            + "/DE/landesregierung/themen/bildung-hochschulen/"
            "hochschule_allgemein/hochschulen/besondere_hochschulen"
        ),
    ]

    AUTHORITY = "Land Schleswig-Holstein"

    def _get_soup(self, url):
        import hashlib
        import time
        from pathlib import Path

        cache_dir = Path("data/source_cache/DE-SH")
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache_name = hashlib.sha256(
            url.encode("utf-8")
        ).hexdigest()[:16] + ".html"

        cache_path = cache_dir / cache_name

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,*/*;q=0.8"
            ),
            "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            "Connection": "close",
        }

        last_error = None

        for attempt in range(1, 4):
            try:
                response = requests.get(
                    url,
                    timeout=30,
                    headers=headers,
                )
                response.raise_for_status()

                cache_path.write_text(
                    response.text,
                    encoding="utf-8",
                )

                print(f"[SH] LIVE  {url}")

                return BeautifulSoup(
                    response.text,
                    "html.parser",
                )

            except requests.RequestException as exc:
                last_error = exc

                print(
                    f"[SH] Request failed "
                    f"(attempt {attempt}/3): {url}"
                )

                if attempt < 3:
                    time.sleep(5 * attempt)

        if cache_path.exists():
            print(f"[SH] CACHE {url}")

            return BeautifulSoup(
                cache_path.read_text(encoding="utf-8"),
                "html.parser",
            )

        raise last_error

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _key(value):
        return re.sub(
            r"[^a-z0-9äöüß]+",
            "",
            value.lower(),
        )

    @staticmethod
    def _looks_like_institution(name):
        lower = name.lower()

        return any(
            term in lower
            for term in (
                "universität",
                "hochschule",
                "fachhochschule",
                "fh des bundes",
                "nordakademie",
            )
        )

    @staticmethod
    def _institution_type(name, context):
        combined = f"{name} {context}".lower()

        if (
            "verwaltung" in combined
            or "bundespolizei" in combined
        ):
            return "public_administration"

        if (
            "kunsthochschule" in combined
            or "musikhochschule" in combined
        ):
            return "art_music"

        if "universität" in name.lower():
            return "university"

        if (
            "fachhochschule" in combined
            or "hochschule" in name.lower()
            or "nordakademie" in name.lower()
        ):
            return "university_of_applied_sciences"

        return "unknown"

    @staticmethod
    def _ownership(name, context):
        combined = f"{name} {context}".lower()

        if any(
            term in combined
            for term in (
                "private",
                "privat",
                "staatlich anerkannt",
                "staatlich anerkannte",
                "gemeinnützige gmbh",
                "wirtschaftsakademie",
            )
        ):
            return "private"

        return "public"

    @staticmethod
    def _find_external_link(wrapper):
        """
        Find the institution website inside the institution's own content
        block. Ignore image/lightbox links and internal SH links.
        """

        candidates = []

        for link in wrapper.find_all("a", href=True):
            href = (link.get("href") or "").strip()

            if not href:
                continue

            lower = href.lower()

            # Skip image/lightbox/internal utility links
            if (
                "__blob=" in lower
                or "renderlightbox" in lower
                or href == "#"
            ):
                continue

            # Strong preference for explicitly marked external links
            if "ExternalLink" in link.get("class", []):
                candidates.append(link)
                continue

            if href.startswith("http://") or href.startswith("https://"):
                if "schleswig-holstein.de" not in lower:
                    candidates.append(link)

        if not candidates:
            return None

        # Usually the official institution link is the final external
        # text link in the block, after descriptive content.
        return candidates[-1]

    def _make_row(self, name, url, context, source_url):
        return {
            "name": name,
            "official_url": url,
            "institution_type":
                self._institution_type(name, context),
            "ownership":
                self._ownership(name, context),
            "recognition_status":
                "state_or_state_recognized",
            "city": None,
            "location_state": "DE-SH",
            "location_type": "main",
            "location_status": "structural",
            "source": {
                "authority": self.AUTHORITY,
                "source_url": source_url,
                "source_category":
                    "official_state_higher_education_landscape",
            },
        }

    def fetch(self):
        rows = []
        seen = set()

        for source_url in self.SOURCE_URLS:
            soup = self._get_soup(source_url)

            # Schleswig-Holstein server is sensitive to rapid sequential requests.
            import time
            time.sleep(5)

            headings = soup.select(
                "h2.l-tab-text__title.heading.inactive-control"
            )

            for heading in headings:
                name = self._clean(
                    heading.get_text(" ", strip=True)
                )

                if not name:
                    continue

                wrapper = heading.find_next_sibling(
                    "div",
                    class_="l-tab-text__wrapper",
                )

                if wrapper is None:
                    continue

                context = self._clean(
                    wrapper.get_text(" ", strip=True)
                )

                link = self._find_external_link(wrapper)

                if link is None:
                    continue

                url = urljoin(
                    source_url,
                    link.get("href", "").strip(),
                )

                key = self._key(name)

                if key in seen:
                    continue

                seen.add(key)

                rows.append(
                    self._make_row(
                        name=name,
                        url=url,
                        context=context,
                        source_url=source_url,
                    )
                )

        print(
            f"[SH] Parsed {len(rows)} institution candidates "
            f"from official Schleswig-Holstein sources"
        )

        return rows
