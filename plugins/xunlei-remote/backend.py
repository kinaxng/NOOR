from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

import httpx

from app.plugins.contracts import PluginTestResult


PLUGIN_ID = "xunlei-remote"
DEFAULT_ENTRY_PATH = "/webman/3rdparty/pan-xunlei-com/index.cgi/"


def _base(config: dict[str, Any]) -> str:
    return str(config.get("base_url") or "").strip().rstrip("/")


def _entry_path(config: dict[str, Any]) -> str:
    value = str(config.get("entry_path") or DEFAULT_ENTRY_PATH).strip()
    return "/" + value.strip("/") + "/"


def _api_url(config: dict[str, Any], path: str) -> str:
    base = _base(config)
    if not base:
        raise ValueError("请先填写群晖地址")
    return urljoin(base + "/", _entry_path(config).lstrip("/") + path.lstrip("/"))


def _verify(config: dict[str, Any]) -> bool:
    return bool(config.get("verify_tls", False))


def _timeout(config: dict[str, Any]) -> float:
    try:
        return max(5.0, min(float(config.get("timeout") or 20), 120.0))
    except (TypeError, ValueError):
        return 20.0


def _authorization(config: dict[str, Any]) -> str:
    value = str(config.get("authorization") or "").strip()
    if value.lower().startswith("authorization:"):
        value = value.split(":", 1)[1].strip()
    return value


def _headers(config: dict[str, Any], *, pan_auth: str = "") -> dict[str, str]:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (NOOR Xunlei Remote)",
        "Referer": _api_url(config, ""),
    }
    authorization = _authorization(config)
    if authorization:
        headers["Authorization"] = authorization
    if pan_auth:
        headers["pan-auth"] = pan_auth
    return headers


def _extract_pan_auth(text: str) -> str:
    patterns = (
        r'function\s+uiauth\s*\([^)]*\)\s*\{\s*return\s+["\']([^"\']+)',
        r'pan_auth\s*[:=]\s*["\']([^"\']+)',
        r'pan-auth\s*[:=]\s*["\']([^"\']+)',
    )
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return match.group(1).strip()
    raise ValueError("未能从迅雷 NAS 页面提取 pan_auth；可在插件配置中手动填写")


def _response_data(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {"data": data}
    if response.status_code >= 400:
        detail = str(data.get("message") or data.get("error") or response.text[:300] or response.reason_phrase)
        if response.status_code in (401, 403) or "unauthor" in detail.lower():
            raise ValueError("群晖登录态校验失败：请在插件配置里填写有效的 Authorization: Basic ... 认证令牌")
        raise ValueError(f"迅雷 NAS 请求失败 ({response.status_code})：{detail}")
    if data.get("error_code") not in (None, 0, "0"):
        raise ValueError(str(data.get("error") or data.get("error_description") or data.get("message") or data["error_code"]))
    return data


async def _client(config: dict[str, Any]) -> httpx.AsyncClient:
    if not _base(config):
        raise ValueError("请先填写群晖地址")
    if not _authorization(config):
        raise ValueError("请填写从迅雷 NAS 请求头复制的 Authorization: Basic ... 认证令牌")
    return httpx.AsyncClient(timeout=_timeout(config), verify=_verify(config), follow_redirects=True, trust_env=False)


async def _pan_auth(config: dict[str, Any], client: httpx.AsyncClient) -> str:
    configured = str(config.get("pan_auth") or "").strip()
    if configured:
        return configured
    response = await client.get(_api_url(config, ""), headers=_headers(config))
    if response.status_code >= 400:
        _response_data(response)
    return _extract_pan_auth(response.text)


def _device_id(value: Any) -> str:
    text = str(value or "").strip()
    if "#" in text:
        return text.rsplit("#", 1)[-1]
    return text


async def _context(config: dict[str, Any], client: httpx.AsyncClient) -> tuple[str, str, dict[str, Any]]:
    pan_auth = await _pan_auth(config, client)
    response = await client.post(
        _api_url(config, "device/info/watch"),
        headers=_headers(config, pan_auth=pan_auth),
        params={"pan_auth": pan_auth, "device_space": ""},
    )
    info = _response_data(response)
    target = info.get("target") or info.get("device_id") or (info.get("device") or {}).get("id")
    device_id = _device_id(target)
    if not device_id:
        raise ValueError("迅雷 NAS 未返回设备 ID")
    return pan_auth, device_id, info


def _space(device_id: str) -> str:
    return f"device_id#{device_id}" if device_id else ""


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    params = task.get("params") if isinstance(task.get("params"), dict) else {}
    return {
        "id": str(task.get("id") or task.get("task_id") or ""),
        "name": str(task.get("name") or task.get("file_name") or params.get("name") or ""),
        "phase": str(task.get("phase") or task.get("status") or ""),
        "progress": max(0.0, min(_number(task.get("progress") or params.get("progress")), 1.0)),
        "size": int(_number(task.get("file_size") or task.get("size"))),
        "downloaded": int(_number(task.get("downloaded_size") or task.get("downloaded"))),
        "speed": int(_number(task.get("speed") or task.get("download_speed"))),
        "url": str(task.get("url") or params.get("url") or ""),
        "savepath": str(task.get("savepath") or task.get("parent_path") or ""),
        "message": str(task.get("message") or task.get("error") or ""),
        "created_time": str(task.get("created_time") or task.get("created_at") or ""),
        "updated_time": str(task.get("updated_time") or task.get("updated_at") or ""),
        "raw": task,
    }


def _quota_message(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
    return any(token in text for token in ("task_create_count_limit", "daily_limit", "今日免费", "次数已用完", "quota"))


async def _tasks(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, *, phase: str = "all", limit: int = 100, page_token: str = "") -> dict[str, Any]:
    body = {"space": _space(device_id), "type": f"user#{phase or 'all'}", "limit": max(1, min(limit, 500))}
    if page_token:
        body["page_token"] = page_token
    response = await client.post(
        _api_url(config, "drive/v1/tasks"), headers=_headers(config, pan_auth=pan_auth),
        params={"pan_auth": pan_auth, "device_space": ""}, content=json.dumps(body, ensure_ascii=False),
    )
    data = _response_data(response)
    raw = data.get("tasks") if isinstance(data.get("tasks"), list) else []
    return {"ok": True, "tasks": [_normalize_task(item) for item in raw if isinstance(item, dict)], "next_page_token": str(data.get("next_page_token") or ""), "raw": data}


async def _resource_list(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, parent_id: str) -> list[dict[str, Any]]:
    body = {"space": _space(device_id), "parent_id": parent_id, "limit": 200}
    response = await client.post(
        _api_url(config, "drive/v1/resource/list"), headers=_headers(config, pan_auth=pan_auth),
        params={"pan_auth": pan_auth, "device_space": ""}, content=json.dumps(body, ensure_ascii=False),
    )
    data = _response_data(response)
    listing = data.get("list") if isinstance(data.get("list"), dict) else data
    resources = listing.get("resources") if isinstance(listing, dict) else []
    return [item for item in resources if isinstance(item, dict)] if isinstance(resources, list) else []


def _configured_folder_id(config: dict[str, Any], savepath: str) -> str:
    mappings = config.get("path_folder_ids")
    if isinstance(mappings, dict):
        wanted = savepath.rstrip("/")
        for path, folder_id in mappings.items():
            if str(path).rstrip("/") == wanted and str(folder_id).strip():
                return str(folder_id).strip()
    return ""


async def _resolve_parent_folder_id(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, savepath: str) -> str:
    configured = _configured_folder_id(config, savepath)
    if configured:
        return configured
    parts = [part for part in str(savepath or "").replace("\\", "/").split("/") if part]
    parent_id = ""
    for part in parts:
        resources = await _resource_list(config, client, pan_auth, device_id, parent_id)
        match = next((item for item in resources if str(item.get("name") or "") == part and (item.get("kind") in (None, "drive#folder", "folder") or bool(item.get("is_folder")))), None)
        if not match:
            raise ValueError(f"迅雷 NAS 中找不到保存目录：{savepath}。请先在迅雷目录中创建它或修正路径。")
        parent_id = str(match.get("id") or "").strip()
        if not parent_id:
            raise ValueError(f"迅雷 NAS 返回了无效目录：{savepath}")
    if not parent_id:
        raise ValueError("保存路径为空，且未配置默认目录 ID")
    return parent_id


async def _submit_download(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url") or payload.get("urls") or payload.get("magnet") or "").strip()
    if not url:
        raise ValueError("缺少下载链接")
    explicit_savepath = str(payload.get("savepath") or "").strip()
    default_savepath = str(config.get("savepath") or "").strip()
    savepath = explicit_savepath or default_savepath
    if savepath:
        parent_id = await _resolve_parent_folder_id(config, client, pan_auth, device_id, savepath)
    else:
        parent_id = str(config.get("mobile_parent_folder_id") or "").strip()
        if not parent_id:
            raise ValueError("未指定保存路径。为避免落入迅雷默认目录，NOOR 已阻止提交。")
    name = str(payload.get("rename") or payload.get("name") or payload.get("title") or "NOOR 下载").strip()
    body = {
        "space": _space(device_id), "type": "user#runner", "url": url,
        "name": name, "file_name": name, "parent_id": parent_id, "file_indices": "--1",
    }
    response = await client.post(
        _api_url(config, "drive/v1/task"), headers={**_headers(config, pan_auth=pan_auth), "Content-Type": "application/json"},
        params={"pan_auth": pan_auth, "device_space": ""}, content=json.dumps(body, ensure_ascii=False),
    )
    data = _response_data(response)
    if _quota_message(data):
        raise ValueError("迅雷今日免费下载任务次数已用完，已保留订阅，次日有可下载次数后会继续尝试推送。")
    return {"ok": True, "message": "已提交到迅雷 NAS", "task": data.get("task") or data, "savepath": savepath, "parent_id": parent_id}


async def _operate_task(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, task_id: str, phase: str) -> dict[str, Any]:
    body = {"space": _space(device_id), "id": task_id, "phase": phase}
    response = await client.patch(
        _api_url(config, "drive/v1/task"), headers={**_headers(config, pan_auth=pan_auth), "Content-Type": "application/json"},
        params={"pan_auth": pan_auth, "device_space": ""}, content=json.dumps(body, ensure_ascii=False),
    )
    data = _response_data(response)
    return {"ok": True, "task_id": task_id, "phase": phase, "result": data}


async def _delete_tasks(config: dict[str, Any], client: httpx.AsyncClient, pan_auth: str, device_id: str, ids: list[str], *, delete_files: bool = False) -> dict[str, Any]:
    results = []
    for task_id in ids:
        result = await _operate_task(config, client, pan_auth, device_id, task_id, "delete")
        results.append(result)
    return {"ok": True, "deleted": len(results), "delete_files": delete_files, "results": results}


async def test(config: dict[str, Any]) -> PluginTestResult:
    try:
        client = await _client(config)
        try:
            pan_auth, device_id, info = await _context(config, client)
        finally:
            await client.aclose()
        return PluginTestResult(ok=True, message="xunlei remote connected", details={"device_id": device_id, "pan_auth": bool(pan_auth), "daily_limit": _quota_message(info)})
    except Exception as exc:
        return PluginTestResult(ok=False, message=f"xunlei remote failed: {exc}")


async def submit_download(payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    client = await _client(config)
    try:
        pan_auth, device_id, _ = await _context(config, client)
        return await _submit_download(config, client, pan_auth, device_id, payload)
    finally:
        await client.aclose()


async def handle_action(action: str, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    payload = payload or {}
    if action == "download_options":
        return {"ok": True, "downloader": PLUGIN_ID, "default_savepath": str(config.get("savepath") or ""), "supports_categories": False, "supports_savepath": True, "supports_small_file_filter": False}
    if action == "test":
        result = await test(config)
        return {"ok": result.ok, "message": result.message, "details": result.details or {}}
    client = await _client(config)
    try:
        pan_auth, device_id, info = await _context(config, client)
        if action in {"overview", "tasks"}:
            out = await _tasks(config, client, pan_auth, device_id, phase=str(payload.get("phase") or "all"), limit=int(payload.get("limit") or 100), page_token=str(payload.get("page_token") or ""))
            out.update({"device_id": device_id, "task_daily_limit": _quota_message(info)})
            return out
        if action == "submit_download":
            return await _submit_download(config, client, pan_auth, device_id, payload)
        if action in {"pause_task", "resume_task", "retry_task", "delete_task_files"}:
            task_id = str(payload.get("id") or payload.get("task_id") or "").strip()
            if not task_id:
                raise ValueError("缺少任务 ID")
            if action == "retry_task" and _quota_message(info):
                raise ValueError("迅雷今日免费下载任务次数已用完；已阻止重试以避免迅雷 NAS 将失败任务从列表中移除。")
            phase = {"pause_task": "pause", "resume_task": "running", "retry_task": "running", "delete_task_files": "delete"}[action]
            return await _operate_task(config, client, pan_auth, device_id, task_id, phase)
        if action == "delete_tasks":
            raw = payload.get("ids") or payload.get("task_ids") or payload.get("id") or payload.get("task_id")
            ids = [str(item).strip() for item in raw] if isinstance(raw, list) else [str(raw or "").strip()]
            ids = [item for item in ids if item]
            if not ids:
                raise ValueError("缺少任务 ID")
            return await _delete_tasks(config, client, pan_auth, device_id, ids, delete_files=bool(payload.get("delete_files")))
        raise ValueError(f"不支持的迅雷操作：{action}")
    finally:
        await client.aclose()
