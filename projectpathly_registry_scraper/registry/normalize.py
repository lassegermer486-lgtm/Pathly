import re
from urllib.parse import urlsplit, urlunsplit

def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    return value or None

def normalize_url(url: str | None) -> str | None:
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    elif not url.startswith(("http://", "https://")):
        url = "https://" + url
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    # https://www.hs-pforzheim.de:443 -> https://www.hs-pforzheim.de
    if (scheme, netloc.rpartition(":")[2]) in (("https", "443"), ("http", "80")):
        netloc = netloc.rpartition(":")[0]
    return urlunsplit((scheme, netloc, parts.path.rstrip("/"), "", ""))

def domain_key(url: str | None) -> str | None:
    if not url:
        return None
    host = urlsplit(normalize_url(url)).netloc.lower()
    return host.removeprefix("www.")

def is_host_within(url: str | None, domain: str) -> bool:
    """
    True if the URL's host is `domain` itself or one of its subdomains.

    A substring check is not enough: "fu-berlin.de" contains "berlin.de"
    and "uni-saarland.de" contains "saarland.de", but neither belongs to
    the state portal.
    """
    if not url:
        return False
    host = (urlsplit(url.strip()).hostname or "").lower()
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)

SOCIAL_MEDIA_DOMAINS = (
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "tiktok.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "xing.com",
    "mastodon.social",
    "threads.net",
    "bsky.app",
)

def is_social_media_url(url: str | None) -> bool:
    return any(
        is_host_within(url, domain)
        for domain in SOCIAL_MEDIA_DOMAINS
    )

def university_name_key(name: str) -> str:
    s = name.lower()
    s = s.replace("&", " und ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^a-z0-9äöüß]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_postal_city(text: str):
    m = re.match(r"^\s*(\d{5})\s+(.+?)\s*$", text)
    return (m.group(1), m.group(2)) if m else (None, None)


def map_nrw_category(category: str | None) -> tuple[str, str]:
    """
    Map official NRW categories to Pathly's normalized
    institution_type and ownership fields.
    """
    mapping = {
        "Öffentlich-rechtliche Universitäten": (
            "university",
            "public"
        ),
        "Öffentlich-rechtliche Hochschulen für angewandte Wissenschaften": (
            "university_of_applied_sciences",
            "public"
        ),
        "Staatliche Kunst- und Musikhochschulen": (
            "art_music_university",
            "public"
        ),
        "Private und kirchliche Hochschulen": (
            "university",
            "private_or_church"
        ),
        "Verwaltungshochschulen": (
            "university_of_public_administration",
            "public"
        ),
    }

    return mapping.get(
        category,
        ("unknown", "unknown")
    )


def aggregate_nrw_universities(rows):
    """
    Convert NRW location rows into one record per university,
    preserving all locations.
    """

    universities = {}

    for row in rows:
        name = clean_text(row.get("name"))

        if not name:
            continue

        key = university_name_key(name)

        if key not in universities:
            institution_type, ownership = map_nrw_category(
                row.get("category")
            )

            universities[key] = {
                "name": name,
                "country": "DE",
                "state": "DE-NW",
                "institution_type": institution_type,
                "ownership": ownership,
                "recognition_status": "unknown",
                "official_url": normalize_url(
                    row.get("official_url")
                ),
                "locations": [],
                "source": row.get("source")
            }

        location_name = clean_text(
            row.get("location_name")
        )

        # Rows without an explicit location label represent
        # the main/default location in the source dataset.
        location_type = (
            "main"
            if location_name is None
            else "campus"
        )

        universities[key]["locations"].append({
            "name": location_name,
            "city": clean_text(row.get("city")),
            "postal_code": clean_text(
                row.get("postal_code")
            ),
            "street": clean_text(row.get("street")),
            "location_type": location_type
        })

    return list(universities.values())
