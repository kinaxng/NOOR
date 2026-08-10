# Source Generated with Decompyle++
# File: media_library.pyc (Python 3.13)

__doc__ = '\nMedia Library API — direct Emby/Jellyfin adapter.\n'
import os
import re
import shutil
import time
import mimetypes

ElementTree
from datetime import datetime, timezone
timezone = timezone
import xml.etree.ElementTree, etree
from pathlib import Path
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.api.endpoints.media_library_helpers import ADAPTER_NOT_ACTIVATED as _ADAPTER_NOT_ACTIVATED, VIDEO_EXTS, env_source_dir as _env_source_dir, config_path as _config_path, get_config as _get_config, headers as _headers, load_config as _load_config, map_path as _map_path, parse_item as _parse_item, parse_tags as _parse_tags, save_config as _save_config, server_url as _server_url
from app.api.endpoints.media_library_item_detail import get_item_impl, get_main_nfo_impl, get_siblings_impl
from app.api.endpoints.media_library_hardlinks import build_hardlink_groups_impl, enrich_hardlink_groups_impl, extract_code_from_path_impl, fetch_emby_item_info_impl, hardlink_groups_path_impl, load_hardlink_groups_impl, save_hardlink_groups_impl, scan_inodes_impl, scan_single_group_impl
# WARNING: Decompyle incomplete
