from pathlib import Path
import io
import re

import requests
from pypdf import PdfReader

from registry.adapters.base import RegistryAdapter


class SaarlandAdapter(RegistryAdapter):
    PDF_URL = (
        "https://www.saarland.de/SharedDocs/Downloads/DE/mbk/"
        "Bildungsserver/unterricht.und-bildungsthemen/"
        "Berufstudienorientierung/ausbildungsstaettenverzeichnis.pdf"
        "?__blob=publicationFile&v=5"
    )

    FHSV_URL = "https://www.saarland.de/fhsv/DE/home/home_node.html"

    def __init__(self, state_code, config):
        super().__init__(state_code, config)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            )
        })

    def fetch(self):
        rows = self._fetch_pdf_rows()

        fhsv_row = self._fetch_fhsv()

        if fhsv_row:
            rows.append(fhsv_row)

        rows = self._deduplicate(rows)

        print(
            f"[SL] Parsed {len(rows)} institution candidates "
            f"from official Saarland sources"
        )

        return rows

    def _fetch_pdf_rows(self):
        cache_path = Path(
            "data/source_cache/DE-SL/ausbildungsstaettenverzeichnis.pdf"
        )

        try:
            response = self.session.get(self.PDF_URL, timeout=30)
            response.raise_for_status()

            pdf_data = response.content
            print("[SL] Using current official online PDF")

        except requests.RequestException as exc:
            if not cache_path.exists():
                raise RuntimeError(
                    "Saarland source unavailable and no cached official PDF exists"
                ) from exc

            pdf_data = cache_path.read_bytes()
            print(
                f"[SL] Online PDF unavailable ({exc}); "
                f"using cached official PDF: {cache_path}"
            )

        reader = PdfReader(io.BytesIO(pdf_data))

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

        lines = [
            self._clean(line)
            for line in text.splitlines()
        ]

        starts = [
            i
            for i, line in enumerate(lines)
            if re.match(r"^\d{5}\s+\S+", line)
        ]

        rows = []

        for pos, start in enumerate(starts):
            end = (
                starts[pos + 1]
                if pos + 1 < len(starts)
                else len(lines)
            )

            block = [
                line
                for line in lines[start:end]
                if line
            ]

            combined = " ".join(block)

            has_hs_code = bool(
                re.search(
                    r"\b(?:HS|FHS)\s*,",
                    combined,
                )
            )

            has_degree = bool(
                re.search(
                    r"\b(?:Bachelor|Master)\b",
                    combined,
                    re.I,
                )
            )

            has_university_name = bool(
                re.search(
                    r"\b(?:Hochschule|Universität)\b",
                    combined,
                    re.I,
                )
            )

            if has_hs_code and has_university_name:
                status = "confirmed"

            elif has_degree:
                status = "candidate"

            else:
                continue

            parsed = self._parse_record(
                block,
                status,
            )

            if parsed:
                rows.append(parsed)

        return rows

    def _parse_record(self, block, status):
        first = block[0]

        address_match = re.match(
            r"^(?P<postal>\d{5})\s+"
            r"(?P<city>[A-Za-zÄÖÜäöüß.\-]+)\s+"
            r"(?P<rest>.+)$",
            first,
        )

        if not address_match:
            return None

        postal_code = address_match.group("postal")
        city = address_match.group("city")
        rest = address_match.group("rest")

        content = [rest] + block[1:]

        name = self._extract_name(
            content,
            status,
        )

        if not name:
            return None

        return {
            "name": name,
            "official_url": None,
            "institution_type": self._institution_type(name),
            "ownership": self._ownership(block),
            "recognition_status": (
                "state"
                if status == "confirmed"
                else "unknown"
            ),
            "location_name": None,
            "city": city,
            "postal_code": postal_code,
            "location_state": "DE-SL",
            "location_type": "main",
            "location_status": status,
            "source": {
                "authority": "Saarland",
                "source_url": self.PDF_URL,
                "source_category": "official_state_directory",
            },
            "location_source_url": self.PDF_URL,
            "location_source_authority": "Saarland",
        }

    def _extract_name(self, content, status):
        cleaned = []

        for line in content:
            if not line:
                continue

            if line.startswith("-"):
                continue

            if re.match(r"^(?:HS|FHS|Akad|Vork)\b", line):
                continue

            if re.search(r"\b(?:Bachelor|Master)\b", line, re.I):
                continue

            if line.startswith("PLZ Ort Straße"):
                continue

            if line in {
                "berufsqualifizierend",
                "Träger",
                "G",
                "ö",
            }:
                continue

            if line.startswith("Nur "):
                continue

            if "örtliche Zuständigkeit" in line:
                continue

            cleaned.append(line)

        if not cleaned:
            return None

        # Confirmed records:
        # Prefer the complete line containing Hochschule/Universität.
        # For multi-line records this preserves prefixes such as
        # "Deutsche Hochschule ...".
        if status == "confirmed":
            for line in cleaned:
                if re.search(
                    r"\b(?:Hochschule|Universität)\b",
                    line,
                    re.I,
                ):
                    # If street information precedes the institution on
                    # the same line, remove the address structurally.
                    line = re.sub(
                        r"^.+?\b\d+(?:\s*-\s*\d+)?\s+"
                        r"(?=[A-ZÄÖÜ])",
                        "",
                        line,
                    )

                    # Generic PDF prefixes such as "Campus".
                    line = re.sub(
                        r"^Campus\s+",
                        "",
                        line,
                        flags=re.I,
                    )

                    return self._strip_metadata(line)

        # Degree-bearing candidates:
        # remove the street/address prefix, but preserve the complete
        # institution name.
        if status == "candidate":
            line = cleaned[0]

            line = re.sub(
                r"^.+?\b\d+[a-z]?\s+"
                r"(?=[A-ZÄÖÜ])",
                "",
                line,
            )

            return self._strip_metadata(line)

        return None

    @staticmethod
    def _strip_metadata(value):
        value = re.sub(
            r"\s+\b(?:HS|FHS)\s*,.*$",
            "",
            value,
        )

        return value.strip(" ,-")

    @staticmethod
    def _institution_type(name):
        lower = name.lower()

        if (
            "bildenden künste" in lower
            or "musik" in lower
        ):
            return "art_music"

        if "universität" in lower:
            return "university"

        if "hochschule" in lower:
            return "university_of_applied_sciences"

        return "unknown"

    @staticmethod
    def _ownership(block):
        combined = " ".join(block)

        if re.search(r"(?:^|\s)ö(?:\s|$)", combined):
            return "public"

        if re.search(r"(?:^|\s)G(?:\s|$)", combined):
            return "private_or_other"

        return "unknown"

    def _fetch_fhsv(self):
        """
        Source exception:
        The official Saarland FHSV website is protected against automated
        requests (HTTP 403), although it is publicly accessible in a browser.

        Therefore the institution is included explicitly for registry discovery.
        This is intentionally a single source exception, not a hardcoded
        Saarland institution list.
        """
        return {
            "name": "Fachhochschule für Verwaltung und Polizei",
            "official_url": self.FHSV_URL,
            "institution_type": "public_administration",
            "ownership": "public",
            "recognition_status": "confirmed",
            "city": "Saarbrücken",
            "location_state": "DE-SL",
            "location_type": "main",
            "location_status": "confirmed",
            "source": {
                "authority": "Saarland",
                "source_url": self.FHSV_URL,
                "source_category": "official_state_source_exception",
            },
        }

    def _deduplicate(self, rows):
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
