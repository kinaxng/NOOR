# Source Generated with Decompyle++
# File: translator.pyc (Python 3.13)

__doc__ = 'AI 字幕翻译模块 - 统一 OpenAI-Compatible API (同时支持 Ollama / OpenAI / 兼容接口)'
import os
import re
import logging
from abc import ABC, abstractmethod
from typing import Optional, List
import httpx
logger = None(__name__)
# WARNING: Decompyle incomplete
