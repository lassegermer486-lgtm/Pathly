"""
Add or remove a dedup decision in the scraper's config/overrides.yaml.

The file is hand-maintained and carries explanatory comments, so it is edited
as text (a YAML dump would drop the comments). Every edit is verified by parsing
the result; if the parsed content is not exactly "old content plus/minus the
pair", nothing is written.
"""
from __future__ import annotations

import copy
import json
import re
from datetime import date
from pathlib import Path

import yaml

SECTIONS = ("merge", "keep_separate")

_TEMPLATE = (
    "# Manuelle Entscheidungen für die Master-Registry.\n"
    "merge:\n\nkeep_separate:\n\nrecords: {}\n"
)


class OverridesError(RuntimeError):
    pass


def _item_line(indent: str, a: str, b: str) -> str:
    # JSON strings are valid YAML double-quoted scalars.
    return f"{indent}- [{json.dumps(a, ensure_ascii=False)}, {json.dumps(b, ensure_ascii=False)}]"


def _same_pair(x, a: str, b: str) -> bool:
    return isinstance(x, (list, tuple)) and len(x) == 2 and {x[0], x[1]} == {a, b}


def _block(lines: list[str], section: str) -> tuple[int, int] | None:
    """(index of the 'section:' line, index after the last line of its block)."""
    start = next((i for i, l in enumerate(lines) if re.match(rf"^{re.escape(section)}\s*:", l)), None)
    if start is None:
        return None
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == "" or line[:1] in (" ", "\t", "#") or line.startswith("- "):
            end += 1
            continue
        break
    # Blank lines and top-level comments right before the next key belong to that key.
    while end > start + 1 and (lines[end - 1].strip() == "" or lines[end - 1].startswith("#")):
        end -= 1
    return start, end


def _parse(text: str) -> dict:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise OverridesError("overrides.yaml hat kein erwartetes Format (kein Mapping).")
    return data


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def add_pair(path: Path, section: str, a: str, b: str, note: str = "") -> bool:
    """Append [a, b] to `section`. Returns False if the pair was already there."""
    if section not in SECTIONS:
        raise OverridesError(f"Unbekannter Abschnitt: {section}")
    text = path.read_text(encoding="utf-8") if path.is_file() else _TEMPLATE
    before = _parse(text)
    if any(_same_pair(p, a, b) for p in before.get(section) or []):
        return False

    lines = text.split("\n")
    block = _block(lines, section)
    if block is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines += [f"{section}:"]
        block = (len(lines) - 1, len(lines))
    start, end = block

    inline = lines[start].split(":", 1)[1].split("#", 1)[0].strip()
    if inline in ("[]", "null", "~"):
        lines[start] = f"{section}:"
    elif inline:
        raise OverridesError(
            f"Der Abschnitt '{section}' steht in einer Zeile und kann nicht automatisch "
            "ergänzt werden. Bitte overrides.yaml von Hand anpassen.")

    indent = "  "
    for line in lines[start + 1:end]:
        if line.lstrip().startswith("- "):
            indent = line[:len(line) - len(line.lstrip())]

    note = " ".join((note or "").split())
    comment = f"{indent}# UI {date.today().isoformat()}" + (f": {note}" if note else "")
    lines[end:end] = [comment, _item_line(indent, a, b)]
    new_text = "\n".join(lines)

    expected = copy.deepcopy(before)
    expected[section] = list(expected.get(section) or []) + [[a, b]]
    if _parse(new_text) != expected:
        raise OverridesError("overrides.yaml konnte nicht sicher ergänzt werden; nichts geändert.")
    _write(path, new_text)
    return True


def remove_pair(path: Path, section: str, a: str, b: str) -> bool:
    """Remove [a, b] (either order) from `section`. Returns False if not present."""
    if section not in SECTIONS or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8")
    before = _parse(text)
    if not any(_same_pair(p, a, b) for p in before.get(section) or []):
        return False

    lines = text.split("\n")
    block = _block(lines, section)
    if block is None:
        raise OverridesError(f"Abschnitt '{section}' nicht gefunden.")
    start, end = block
    hit = None
    for i in range(start + 1, end):
        stripped = lines[i].strip()
        if not stripped.startswith("- "):
            continue
        try:
            parsed = yaml.safe_load(stripped)
        except yaml.YAMLError:
            continue
        if isinstance(parsed, list) and len(parsed) == 1 and _same_pair(parsed[0], a, b):
            hit = i
            break
    if hit is None:
        raise OverridesError(
            "Der Eintrag steht nicht in einer einzelnen Zeile und kann nicht automatisch "
            "entfernt werden. Bitte overrides.yaml von Hand anpassen.")

    first = hit - 1 if hit - 1 > start and lines[hit - 1].strip().startswith("# UI ") else hit
    del lines[first:hit + 1]
    new_text = "\n".join(lines)

    expected = copy.deepcopy(before)
    expected[section] = [p for p in expected[section] if not _same_pair(p, a, b)] or None
    if _parse(new_text) != expected:
        raise OverridesError("overrides.yaml konnte nicht sicher geändert werden; nichts geändert.")
    _write(path, new_text)
    return True
