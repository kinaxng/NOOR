"""Filename normalization shared by Whisper and subtitle ingestion."""
from __future__ import annotations

import re
from pathlib import Path


_MEDIA_SUFFIX_RE = re.compile(r"\.(?:mp4|mkv|avi|mov|wmv|flv|m4v)$", re.IGNORECASE)
_VERSION_SUFFIX_RE = re.compile(
    r"(?:[-_. ](?:破解|流出|中文字幕|中文|字幕|chs?|cht|cn|tw|zh(?:[-_](?:cn|tw|hans|hant))?|u|c|uc))$",
    re.IGNORECASE,
)


def clean_media_stem(name: str) -> str:
    """Remove known trailing media markers without eating normal words such as chain."""
    stem = _MEDIA_SUFFIX_RE.sub("", Path(name).name).strip()
    while True:
        cleaned = _VERSION_SUFFIX_RE.sub("", stem).rstrip("-_. ")
        if cleaned == stem:
            return stem
        stem = cleaned
