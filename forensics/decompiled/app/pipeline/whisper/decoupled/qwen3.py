# Source Generated with Decompyle++
# File: qwen3.pyc (Python 3.13)

from __future__ import annotations
import importlib.util as importlib
import logging
import re
from pathlib import Path
from typing import Any
from types import AlignmentResult, WordTimestamp
logger = None(__name__)
_SENTENCE_END_RE = None('[。！？?!]$')
_SOFT_BREAK_RE = None('[、，,]$')
_HARD_BREAK_RE = None('[。！？?!」』\\"]$')
# WARNING: Decompyle incomplete
