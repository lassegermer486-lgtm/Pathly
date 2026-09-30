import csv
import io
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests

from .base import RegistryAdapter


class NRWAdapter(RegistryAdapter):

    def fetch(self):
        url = self.config["url"]

        headers = {
            "User-Agent": self.config.get(
                "user_agent",
                "ProjectPathlyRegistry/0.1"
            )
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        # NRW declares UTF-8 but the current CSV is actually Windows-1252.
        encoding = self.config.get("encoding", "cp1252")
        text = response.content.decode(encoding)

        # Save immutable-ish raw snapshot for provenance/debugging.
        raw_dir = Path(self.config.get("_raw_dir", "data/raw"))
        raw_dir.mkdir(parents=True, exist_ok=True)

        snapshot = raw_dir / "DE-NW_hochschulstandorte.csv"
        snapshot.write_bytes(response.content)

        reader = csv.DictReader(
            io.StringIO(text),
            delimiter=";"
        )

        rows = []

        for row in reader:
            name = self._clean(row.get("Name der Hochschule"))
            if not name:
                continue

            website = self._normalize_url(
                self._clean(row.get("Website"))
            )

            rows.append({
                "source_id": self._clean(
                    row.get("Datei-interne ID")
                ),
                "name": name,
                "country": "DE",
                "state": "DE-NW",

                "category": self._clean(
                    row.get("Kategorie")
                ),

                "location_name": self._clean(
                    row.get("Standort")
                ),

                "street": self._clean(
                    row.get("Straße Nr.")
                ),

                "postal_code": self._clean(
                    row.get("PLZ")
                ),

                "city": self._clean(
                    row.get("Stadt")
                ),

                "phone": self._clean(
                    row.get("Tel.")
                ),

                "fax": self._clean(
                    row.get("Fax")
                ),

                "official_url": website,

                "source": {
                    "authority": self.config.get("authority"),
                    "url": url,
                    "source_type": "csv",
                    "retrieved_at": datetime.now(
                        timezone.utc
                    ).isoformat()
                }
            })

        print(
            f"[NRW] Parsed {len(rows)} source rows "
            f"from official CSV"
        )

        return rows

    @staticmethod
    def _clean(value):
        if value is None:
            return None

        value = value.strip()

        return value if value else None

    @staticmethod
    def _normalize_url(value):
        if not value:
            return None

        if not urlparse(value).scheme:
            return "https://" + value

        return value
