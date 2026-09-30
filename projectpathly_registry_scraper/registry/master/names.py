"""Name and domain helpers used for duplicate detection."""
from __future__ import annotations

import re
from urllib.parse import urlsplit

from registry.normalize import normalize_url

_FOLD = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})

# Function words and generic institution words. Deliberately NOT included:
# words that distinguish institutions (technische, pädagogische, musik,
# evangelische, katholische, verwaltung, ...).
STOP_TOKENS = {
    "hochschule", "fachhochschule", "universitat", "university", "universities",
    "college", "school", "of", "for", "applied", "sciences", "science",
    "and", "und", "fur", "der", "die", "das", "des", "dem", "den", "the",
    "in", "im", "am", "an", "zu", "zur", "de", "fh", "hs", "uni",
    "private", "privat", "staatliche", "staatlich", "anerkannte",
    "wissenschaften", "angewandte", "angewandten", "gmbh", "ggmbh", "e", "v",
}

# Subject/denomination words shared by many unrelated institutions
# ("Evangelische Hochschule", "Hochschule für Technik und Wirtschaft").
# A name match needs at least one token that is neither this nor a place.
GENERIC_TOKENS = {
    "technik", "technische", "technologie", "wirtschaft", "okonomie", "oekonomie",
    "management", "business", "gestaltung", "design", "medien", "media", "kunst",
    "kunste", "bildende", "bildenden", "musik", "theater", "darstellende", "film",
    "fernsehen", "evangelische", "katholische", "kirchliche", "kirchenmusik",
    "theologische", "philosophisch", "verwaltung", "offentliche", "offentlichen",
    "polizei", "finanzen", "rechtspflege", "padagogische", "gesundheit", "soziales",
    "sozialwesen", "soziale", "informatik", "internationale", "international",
    "europaische", "europe", "freie", "digital", "akademie", "berufsakademie",
    "studien", "fern", "duale", "sport", "recht", "logistik", "pflege", "medizin",
    "ingenieur", "architektur", "bauwesen", "landwirtschaft", "forstwirtschaft",
    "umwelt", "graduate", "technical", "arts", "art", "music", "institut",
    "fachhochschule", "berufliche", "kunsthochschule", "musikhochschule",
}

_HEAD_WORDS = re.compile(
    r"hochschule|universit|university|akademie|institut|college|school",
    re.I,
)
_DEPARTMENT = re.compile(
    r"^(fachbereich|abteilung|standort|studienort|studienzentrum|campus)\b",
    re.I,
)


def fold(text: str) -> str:
    return text.lower().translate(_FOLD)


def tokens(text: str) -> list[str]:
    text = fold(text).replace("&", " und ")
    text = re.sub(r"university of applied sciences?", "hochschule", text)
    return [t for t in re.split(r"[^a-z0-9]+", text) if t]


def split_name(raw: str) -> dict:
    """
    Split a listed name into a clean base name plus what was removed:
      hints:  parenthesised text, e.g. abbreviation or city
      tail:   text after ' - ' / ' – ' / ' | ' (tagline or department)
    """
    name = raw.replace("​", "").strip()
    name = re.sub(r"\s*\*+\s*$", "", name)

    hints = re.findall(r"\(([^)]*)\)", name)
    name = re.sub(r"\s*\([^)]*\)", "", name)

    tail = None
    parts = re.split(r"\s+[-–|]\s+", name, maxsplit=1)
    # Only split when the left side is itself a complete institution name
    # ("AKAD – Hochschule Stuttgart" must stay intact).
    if len(parts) == 2 and _HEAD_WORDS.search(parts[0]):
        name, tail = parts[0].strip(), parts[1].strip()

    return {
        "base": re.sub(r"\s+", " ", name).strip(),
        "hints": [h.strip() for h in hints if h.strip()],
        "tail": tail,
        "is_department": bool(tail and _DEPARTMENT.match(tail)),
    }


def name_key(base_name: str) -> str:
    """Exact-comparison key of a cleaned name (stop words kept)."""
    return " ".join(tokens(base_name))


def core_tokens(base_name: str) -> frozenset[str]:
    return frozenset(t for t in tokens(base_name) if t not in STOP_TOKENS)


def head_class(base_name: str) -> str:
    """'uni' vs 'hs' — a Universität and a Hochschule of the same city differ."""
    t = set(tokens(base_name))
    return "uni" if t & {"universitat", "university", "universities"} else "hs"


# Land portals host many unrelated institutions; sharing them proves nothing.
SHARED_PORTALS = {
    "baden-wuerttemberg.de", "bayern.de", "berlin.de", "brandenburg.de",
    "bremen.de", "hamburg.de", "hessen.de", "mv-regierung.de", "niedersachsen.de",
    "nrw.de", "rlp.de", "saarland.de", "sachsen.de", "sachsen-anhalt.de",
    "schleswig-holstein.de", "thueringen.de",
}


def _labels(url: str | None) -> list[str]:
    if not url:
        return []
    netloc = urlsplit(normalize_url(url)).netloc.lower().split(":")[0]
    return netloc.removeprefix("www.").split(".") if netloc else []


def host(url: str | None) -> str | None:
    labels = _labels(url)
    h = ".".join(labels)
    return h if h and h not in SHARED_PORTALS else None


def root_domain(url: str | None) -> str | None:
    labels = _labels(url)
    if not labels:
        return None
    if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in {"co", "com", "ac", "org"}:
        root = ".".join(labels[-3:])
    else:
        root = ".".join(labels[-2:])
    return None if root in SHARED_PORTALS else root
