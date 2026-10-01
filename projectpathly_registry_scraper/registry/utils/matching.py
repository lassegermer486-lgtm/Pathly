"""
Conservative name matching between two official sources of the same state.

Used when the discovery source has no websites (e.g. a statistics table)
and a second official page lists the websites under slightly different
names, e.g.

    "Duale Hochschule Eisenach-Gera"   <->  "Duale Hochschule Gera-Eisenach"
    "SRH University of Applied Sciences
     Heidelberg in Gera"               <->  "SRH University (privat)"

This is NOT nationwide deduplication. It only links records that the
caller already knows belong to the same state, and it refuses to match
when the evidence is weak or ambiguous.
"""

from __future__ import annotations

import re
import unicodedata


UMLAUTS = str.maketrans({
    "ä": "ae",
    "ö": "oe",
    "ü": "ue",
    "ß": "ss",
})

# Words that carry no identity on their own.
STOPWORDS = {
    "an", "am", "der", "die", "das", "des", "dem", "den",
    "und", "fuer", "zu", "im", "in",
    "of", "and", "for", "the",
    "campus", "standort", "privat",
    "gmbh", "ggmbh", "ev", "e", "v",
}

# Institution-type words. They count towards the overlap, so
# "Universität Erfurt" and "Fachhochschule Erfurt" stay apart, but they
# can never be the only shared evidence.
GENERIC_TOKENS = {
    "hochschule", "fachhochschule", "universitaet", "uni",
    "university", "universities", "college", "akademie",
    "technische", "technik", "applied", "sciences", "science",
    "wirtschaft", "kunst", "kuenste", "musik",
    "evangelische", "katholische", "internationale",
    "duale", "staatliche", "private", "oeffentliche",
}

MIN_CONTAINMENT = 0.8
MIN_SHARED_TOKENS = 2


def name_tokens(name: str | None) -> set[str]:
    if not name:
        return set()

    value = unicodedata.normalize("NFKC", name)
    value = value.replace("\xad", "")  # soft hyphen
    value = value.lower().translate(UMLAUTS)
    value = re.sub(r"\([^)]*\)", " ", value)

    return {
        token
        for token in re.split(r"[^a-z0-9]+", value)
        if token and token not in STOPWORDS
    }


def match_name(name: str, candidates: list[str]) -> str | None:
    """
    Return the single candidate that clearly names the same institution,
    or None.

    A candidate matches when
      - its token set is identical, or
      - the smaller token set is (almost) contained in the larger one,
        they share at least two tokens, and at least one shared token
        is not a generic institution-type word.

    Ties are treated as ambiguous and return None.
    """

    source = name_tokens(name)

    if not source:
        return None

    scored = []

    for candidate in candidates:
        tokens = name_tokens(candidate)

        if not tokens:
            continue

        if tokens == source:
            scored.append((2.0, candidate))
            continue

        shared = source & tokens

        if len(shared) < MIN_SHARED_TOKENS:
            continue

        if not shared - GENERIC_TOKENS:
            continue

        containment = len(shared) / min(len(source), len(tokens))

        if containment >= MIN_CONTAINMENT:
            scored.append((containment, candidate))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0], reverse=True)

    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None

    return scored[0][1]
