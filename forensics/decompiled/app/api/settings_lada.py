# Source Generated with Decompyle++
# File: settings_lada.pyc (Python 3.13)

from __future__ import annotations
import os
import subprocess
from pathlib import Path
from typing import Any, Callable
LADA_ENCODING_PRESETS = [
    {
        'id': 'hevc-nvidia-gpu-hq',
        'name': 'HEVC (H.265) - High Quality',
        'desc': 'Nvidia GPU, High Quality, Medium File Size' },
    {
        'id': 'hevc-nvidia-gpu-balanced',
        'name': 'HEVC (H.265) - Balanced',
        'desc': 'Nvidia GPU, Excellent Quality, Smaller File Size' },
    {
        'id': 'hevc-nvidia-gpu-uhq',
        'name': 'HEVC (H.265) - Ultra HQ',
        'desc': 'Nvidia GPU, Indistinguishable Quality, Large File Size' },
    {
        'id': 'h264-nvidia-gpu-fast',
        'name': 'H.264 - Fast',
        'desc': 'Nvidia GPU, Fast, Medium File Size' },
    {
        'id': 'h264-cpu-fast',
        'name': 'H.264 - CPU Fast',
        'desc': 'x264 software encoder, Fast, Medium File Size' },
    {
        'id': 'h264-cpu-uhq',
        'name': 'H.264 - CPU Ultra HQ',
        'desc': 'x264 software encoder, Indistinguishable Quality, Slow, Very Large File Size' },
    {
        'id': 'av1-cpu-uhq',
        'name': 'AV1 - CPU Ultra HQ',
        'desc': 'SVT-AV1 software encoder, Indistinguishable Quality, Smaller File Size' }]
# WARNING: Decompyle incomplete
