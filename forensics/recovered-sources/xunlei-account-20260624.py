        }
        try:
            async with await _client(config, timeout=float(config.get("timeout") or 30)) as client:
                pan_auth, device_id, device_info = await _context(config, client)
                downloads = device_info.get("downloads") if isinstance(device_info, dict) else []
                root_paths = []
                for item in downloads if isinstance(downloads, list) else []:
                    normalized = _normalize_download_path_item(item)
                    if normalized:
                        normalized["source"] = "device_info"
                        root_paths.append(normalized)
                history_paths = []
                try:
                    history = await _download_paths(config, client, pan_auth)
                    history_paths = history.get("paths") or []
                    out["download_paths_raw_count"] = len(history_paths)
                except Exception as path_exc:
                    out["download_paths_warning"] = str(path_exc)
                fallback_paths = root_paths if bool(payload.get("include_root_paths")) else []
                paths = _merge_paths(history_paths, fallback_paths)
                out["paths"] = paths
                out["root_paths"] = root_paths
                out["categories"] = [{"name": p["name"] or p["path"], "save_path": p["path"]} for p in paths]
                if paths and (not out["default_savepath"] or out["default_savepath"] == DEFAULT_SAVE_PATH):
                    preferred = next((p for p in paths if not p.get("is_root_path")), paths[0])
                    out["default_savepath"] = preferred["path"]
                out["device_id"] = device_id
                daily_limit = _extract_task_daily_limit(device_info)
                if daily_limit:
                    out["task_daily_limit"] = daily_limit
        except Exception as exc:
            out["warning"] = str(exc)
        return out
    async with await _client(config, timeout=float(config.get("timeout") or 30)) as client:
        pan_auth, device_id, device_info = await _context(config, client)
        if action == "account_static_info":
            timestamp = str(int(time.time() * 1000))
            return {"ok": True, "client_id": ACCOUNT_CLIENT_ID, "device_id": _account_device_id(config), "alg_version": ACCOUNT_ALG_VERSION, "algorithms_count": len(ACCOUNT_ALGORITHMS), "captcha_sign_sample": _account_captcha_sign(config, timestamp)}
        if action == "account_user_me":
            return await _account_user_me(config, client)
        if action == "account_clients":
            return await _account_clients(config, client)
        if action == "account_paths":
            return await _account_paths(config, client, payload)
        if action == "account_submit":
            return await _account_submit(config, client, payload)
        if action == "mobile_submit":
            return await _mobile_submit_download(config, client, payload)
        if action == "mobile_status":
            return await _mobile_status(config, client)
        if action == "try_speed_info":
            return await _try_speed_info(config, client, pan_auth)
        if action == "try_speed_config":
            return await _try_speed_config(config, client, pan_auth)
        if action == "try_speed_apply":
            return await _try_speed_apply(config, client, pan_auth)
        if action == "flow_info":
            return await _flow_info(config, client, pan_auth)
        if action == "device_info":
            out = {"ok": True, "device_id": device_id, "info": device_info}
            daily_limit = _extract_task_daily_limit(device_info)
            if daily_limit:
                out["task_daily_limit"] = daily_limit
            try:
                out.update(await _try_speed_info(config, client, pan_auth))
            except Exception as try_exc:
                out["try_speed_warning"] = str(try_exc)
            return out
        if action == "tasks":
            return await _tasks(
                config,
                client,
                pan_auth,
                device_id,
                phase=str(payload.get("phase") or "all"),
                limit=int(payload.get("limit") or 100),
                page_token=str(payload.get("page_token") or ""),
            )
        if action in {"pause_task", "resume_task", "retry_task", "delete_task_files"}:
            task_id = str(payload.get("id") or payload.get("task_id") or "").strip()
            if not task_id:
                raise ValueError("missing task id")
            phase = {"pause_task": "pause", "resume_task": "running", "retry_task": "running", "delete_task_files": "delete"}[action]
            return await _operate_task(config, client, pan_auth, device_id, task_id, phase)
        if action == "delete_tasks":
            ids_raw = payload.get("ids") or payload.get("task_ids") or payload.get("id") or payload.get("task_id")
            ids = [str(x).strip() for x in (ids_raw if isinstance(ids_raw, list) else [ids_raw]) if str(x or "").strip()]
            if not ids:
                raise ValueError("missing task id")
            return await _delete_tasks(config, client, pan_auth, device_id, ids, delete_files=bool(payload.get("delete_files")))
        if action == "files":
            return await _files(
                config,
                client,
                pan_auth,
                device_id,
                parent_id=str(payload.get("parent_id") or ""),
                limit=int(payload.get("limit") or 100),
                page_token=str(payload.get("page_token") or ""),
            )
        if action == "about":
            return await _about(config, client, pan_auth)
        if action == "device_config":
            return await _device_config(config, client, pan_auth)
        if action == "download_paths":
            return await _download_paths(config, client, pan_auth)
        if action == "create_download_path":
            return await _create_download_path(config, client, pan_auth, str(payload.get("path") or payload.get("real_path") or ""))
        if action == "browse_folders":
            return await _browse_folders(config, client, pan_auth, device_id, parent_id=str(payload.get("parent_id") or ""), limit=int(payload.get("limit") or 200))
        if action == "resource_info":
            url = str(payload.get("url") or payload.get("magnet") or "").strip()
            if not url:
                raise ValueError("missing url/magnet")
            info = await _resource_info(config, client, pan_auth, url)
            return {"ok": True, **{k: info[k] for k in ("files", "total_files", "total_size_bytes", "total_size_formatted")}}
    raise ValueError(f"unsupported action: {action}")
