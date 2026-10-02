import re

import requests

from registry import http_client
from bs4 import BeautifulSoup

from .base import RegistryAdapter


class SachsenAnhaltAdapter(RegistryAdapter):
    """
    Registry adapter for DE-ST.

    Official source:
    Ministry of Science, Energy, Climate Protection and Environment
    of Saxony-Anhalt - Hochschullandschaft.

    Discovery strategy:
    1. Structured university blocks:
       div.text-image.block -> muse-h3 + muse-link
    2. Additional institutions:
       p -> strong + muse-link

    The adapter intentionally follows a recall-first strategy.
    Nationwide deduplication/validation happens later.
    """

    SOURCE_URL = (
        "https://mwu.sachsen-anhalt.de/"
        "wissenschaft/hochschulen/page/hochschullandschaft"
    )

    AUTHORITY = "Land Sachsen-Anhalt"

    def _get_soup(self):
        response = http_client.get(
            self.SOURCE_URL,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    @staticmethod
    def _clean(value):
        return re.sub(r"\s+", " ", value or "").strip()

    @staticmethod
    def _looks_like_institution(name):
        lower = name.lower()

        return any(
            term in lower
            for term in (
                "universität",
                "hochschule",
                "fachhochschule",
            )
        )

    @staticmethod
    def _clean_url(link):
        """
        Prefer the visible URL when it clearly contains a domain.

        This also protects against malformed source hrefs such as:
        https://www.uni-halle.dewww.uni-magdeburg.de
        """
        href = (link.get("href") or "").strip()

        visible = re.sub(
            r"\s+",
            "",
            link.get_text("", strip=True),
        )

        if visible.startswith("www."):
            return "https://" + visible.rstrip("/")

        if visible.startswith("http://") or visible.startswith("https://"):
            return visible.rstrip("/")

        return href.rstrip("/")

    @staticmethod
    def _institution_type(name):
        lower = name.lower()

        if "polizei" in lower:
            return "public_administration"

        if (
            "kunsthochschule" in lower
            or "kirchenmusik" in lower
        ):
            return "art_music"

        if "universität" in lower:
            return "university"

        if (
            "fachhochschule" in lower
            or "hochschule" in lower
        ):
            return "university_of_applied_sciences"

        return "unknown"

    @staticmethod
    def _ownership(name, context):
        combined = f"{name} {context}".lower()

        if (
            "kirchlicher trägerschaft" in combined
            or "evangelischen kirche" in combined
            or "kirchenmusik" in combined
            or "theologische hochschule" in combined
        ):
            return "church"

        if (
            "private hochschule" in combined
            or "privaten hochschule" in combined
        ):
            return "private"

        return "public"

    def _make_row(self, name, url, context):
        return {
            "name": self._clean(name),
            "official_url": url,
            "institution_type": self._institution_type(name),
            "ownership": self._ownership(name, context),
            "recognition_status": "state_or_state_recognized",
            "city": None,
            "location_state": "DE-ST",
            "location_type": "main",
            "location_status": "structural",
            "source": {
                "authority": self.AUTHORITY,
                "source_url": self.SOURCE_URL,
                "source_category":
                    "official_state_higher_education_landscape",
            },
        }

    def fetch(self):
        soup = self._get_soup()

        rows = []
        seen = set()

        def add(name, link, context):
            name = self._clean(name)

            if not name:
                return

            if not self._looks_like_institution(name):
                return

            key = re.sub(
                r"[^a-z0-9äöüß]+",
                "",
                name.lower(),
            )

            if key in seen:
                return

            url = self._clean_url(link)

            if not url:
                return

            seen.add(key)

            rows.append(
                self._make_row(
                    name=name,
                    url=url,
                    context=context,
                )
            )

        # ---------------------------------------------------------
        # Pattern A:
        # Main university blocks
        #
        # <div class="text-image block">
        #   <muse-h3>Hochschule ...</muse-h3>
        #   ...
        #   <muse-link>www...</muse-link>
        # </div>
        # ---------------------------------------------------------

        for block in soup.select("div.text-image.block"):
            heading = block.find("muse-h3")

            links = block.find_all(
                ["muse-link", "a"],
                href=True,
            )

            # A genuine institution block has one heading paired
            # with exactly one institutional website.
            # Collection blocks containing several institutions
            # are handled by Pattern B below.
            if not heading or len(links) != 1:
                continue

            link = links[0]

            name = self._clean(
                heading.get_text(" ", strip=True)
            )

            context = self._clean(
                block.get_text(" ", strip=True)
            )

            add(
                name=name,
                link=link,
                context=context,
            )

        # ---------------------------------------------------------
        # Pattern B:
        # Additional institutions in rich-text paragraphs
        #
        # <p>
        #   Die <strong>Hochschule ...</strong> ...
        #   <muse-link>www...</muse-link>
        # </p>
        # ---------------------------------------------------------

        for paragraph in soup.find_all("p"):
            link = paragraph.find(
                ["muse-link", "a"],
                href=True,
            )

            if not link:
                continue

            strong = paragraph.find("strong")

            if not strong:
                continue

            name = self._clean(
                strong.get_text(" ", strip=True)
            )

            context = self._clean(
                paragraph.get_text(" ", strip=True)
            )

            add(
                name=name,
                link=link,
                context=context,
            )

        print(
            f"[ST] Parsed {len(rows)} institution candidates "
            f"from official Sachsen-Anhalt source"
        )

        return rows
