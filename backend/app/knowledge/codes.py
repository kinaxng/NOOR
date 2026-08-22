from __future__ import annotations

import re
from pathlib import Path


STANDARD_CODE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,10})[-_ ]?(\d{2,7})(?:[-_ ]([A-Z]))?(?![A-Z0-9])", re.I)
FC2_CODE_RE = re.compile(r"(?<![A-Z0-9])(?:FC2[-_ ]*)?(?:PPV[-_ ]*)?(\d{4,9})(?!\d)", re.I)
FC2_MARKED_RE = re.compile(r"(?:FC2|PPV)", re.I)
DATED_SUFFIX_RE = re.compile(
    r"(?<!\d)(\d{6})[-_ ](\d{2,5})[-_ ](1PON|CARIB|10MU|PACOPACOMAMA)(?![A-Z0-9])",
    re.I,
)
DATED_PREFIX_RE = re.compile(
    r"(?<![A-Z0-9])(1PON|CARIB|10MU|PACOPACOMAMA)[-_ ](\d{6})[-_ ](\d{2,5})(?!\d)",
    re.I,
)


def _append(values: list[str], value: str) -> None:
    value = value.upper()
    if value and value not in values:
        values.append(value)


def extract_video_code_candidates(value: str) -> list[str]:
    """Return normalized AV code candidates from a title/path.

    Tracker names frequently remove separators or reverse the site/date parts.
    Keep all credible normalized forms so the knowledge graph can match local
    media with external resources without treating a local filename as the
    only canonical spelling.
    """

    raw = str(value or "").strip()
    if not raw:
        return []
    basename = raw.replace("\\", "/").rsplit("/", 1)[-1]
    text = f"{Path(basename).stem} {raw}"
    candidates: list[str] = []

    for match in DATED_SUFFIX_RE.finditer(text):
        date, sequence, site = match.groups()
        _append(candidates, f"{site}-{date}-{sequence}")
    for match in DATED_PREFIX_RE.finditer(text):
        site, date, sequence = match.groups()
        _append(candidates, f"{site}-{date}-{sequence}")

    if FC2_MARKED_RE.search(text):
        for match in FC2_CODE_RE.finditer(text):
            _append(candidates, f"FC2-PPV-{match.group(1)}")

    for match in STANDARD_CODE_RE.finditer(text):
        prefix, number, suffix = match.groups()
        prefix = prefix.upper()
        if prefix in {"FC", "FC2", "PPV"}:
            continue
        code = f"{prefix}-{number}"
        if suffix:
            _append(candidates, f"{code}-{suffix}")
        _append(candidates, code)

    return candidates


def extract_video_code(value: str) -> str | None:
    candidates = extract_video_code_candidates(value)
    return candidates[0] if candidates else None
