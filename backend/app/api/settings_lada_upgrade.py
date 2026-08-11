"""LADA upgrade support helpers, reconstructed from bytecode."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


PROXY_ENV_KEYS = ("http_proxy", "https_proxy", "http://proxy", "https://proxy")


def normalize_git_remote_url(url: str) -> str:
    value = (url or "").strip()
    prefixes = (
        "https://ghproxy.com/https://github.com/",
        "https://ghproxy.net/https://github.com/",
        "https://ghproxy.cc/https://github.com/",
        "https://hub.gitmirror.com/https://github.com/",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            return "https://github.com/" + value[len(prefix):].lstrip("/")
    malformed = "https://ghproxy.com/"
    if value.startswith(malformed) and "github.com/" not in value:
        return "https://github.com/" + value[len(malformed):].lstrip("/")
    return value


def github_mirror_url(mirror: str, github_url: str) -> str:
    mirror = (mirror or "https://ghproxy.com").strip().rstrip("/")
    github_url = normalize_git_remote_url(github_url).strip()
    if not github_url.startswith("https://github.com/") or "github.com" in mirror:
        return github_url
    return f"{mirror}/{github_url}"


def build_lada_upgrade_env(env: dict[str, str]) -> dict[str, str]:
    filtered = {}
    for key, value in env.items():
        if key.lower() not in PROXY_ENV_KEYS:
            filtered[key] = value
    filtered.pop("HTTP_PROXY", None)
    filtered.pop("HTTPS_PROXY", None)
    filtered.pop("http_proxy", None)
    filtered.pop("https_proxy", None)
    return filtered


def resolve_git_branch(branch_result: Any) -> str:
    if getattr(branch_result, "returncode", 1) == 0:
        branch = getattr(branch_result, "stdout", "").strip()
        if branch:
            return branch
    return "main"


def raise_for_git_pull_failure(
    stderr: str, *, lada_path: str, branch: str, log_mgr: Any
) -> None:
    stderr = stderr or ""
    lowered = stderr.lower()
    if "redirect" in lowered or "ghfast" in stderr:
        log_mgr.add_log("error", "[LADA] 升级失败：代理镜像重定向错误")
        raise HTTPException(
            status_code=500,
            detail=(
                "代理镜像重定向错误。GitHub 被重定向到了不可用的镜像。 请在代理软件中将 github.com 加入直连，或手动执行以下命令：\ncd "
                f"{lada_path} && git pull --ff-only origin {branch}"
            ),
        )
    if "Could not connect" in stderr or "timeout" in lowered or "curl 28" in stderr:
        log_mgr.add_log("error", "[LADA] 升级失败：无法连接 GitHub")
        raise HTTPException(
            status_code=500,
            detail="无法连接 GitHub。请检查网络代理设置，确保可以访问 github.com。",
        )
    log_mgr.add_log("error", f"[LADA] 升级失败 — {stderr[:100]}")
    raise HTTPException(status_code=500, detail=f"Git pull failed: {stderr}")


def should_add_break_system_packages(sys_module: Any) -> bool:
    return not hasattr(sys_module, "base_prefix") or (
        sys_module.prefix == getattr(sys_module, "base_prefix", sys_module.prefix)
    )
