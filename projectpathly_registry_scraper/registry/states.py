"""
The 16 German states.

`code`  official ISO 3166-2:DE code, used as the key in data and sources.yaml
`short` common abbreviation (2 or 3 letters, e.g. NRW), used for display and
        accepted on the command line
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    code: str
    short: str
    name: str

    @property
    def label(self) -> str:
        return f"{self.short:<3} {self.name} ({self.code})"


STATES = [
    State("DE-BW", "BW", "Baden-Württemberg"),
    State("DE-BY", "BY", "Bayern"),
    State("DE-BE", "BE", "Berlin"),
    State("DE-BB", "BB", "Brandenburg"),
    State("DE-HB", "HB", "Bremen"),
    State("DE-HH", "HH", "Hamburg"),
    State("DE-HE", "HE", "Hessen"),
    State("DE-MV", "MV", "Mecklenburg-Vorpommern"),
    State("DE-NI", "NI", "Niedersachsen"),
    State("DE-NW", "NRW", "Nordrhein-Westfalen"),
    State("DE-RP", "RP", "Rheinland-Pfalz"),
    State("DE-SL", "SL", "Saarland"),
    State("DE-SN", "SN", "Sachsen"),
    State("DE-ST", "ST", "Sachsen-Anhalt"),
    State("DE-SH", "SH", "Schleswig-Holstein"),
    State("DE-TH", "TH", "Thüringen"),
]

BY_CODE = {s.code: s for s in STATES}

_ALIASES = {}
for _s in STATES:
    for _alias in {_s.code, _s.code.removeprefix("DE-"), _s.short}:
        _ALIASES[_alias.upper()] = _s


def resolve(token: str) -> State:
    """'NRW', 'nw', 'DE-NW' -> State. Raises ValueError for unknown input."""
    state = _ALIASES.get(token.strip().upper())
    if state is None:
        valid = ", ".join(s.short for s in STATES)
        raise ValueError(f"unknown state '{token}' (valid: {valid})")
    return state


def short(code: str | None) -> str:
    state = BY_CODE.get(code or "")
    return state.short if state else (code or "?")
