import { createHotContext as __vite__createHotContext } from "/@vite/client";import.meta.hot = __vite__createHotContext("/src/views/PluginHost.vue");import { defineComponent as _defineComponent } from "/node_modules/.vite/deps/vue.js?v=d223f038";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "/node_modules/.vite/deps/vue.js?v=d223f038";
import { useRoute } from "/node_modules/.vite/deps/vue-router.js?v=d223f038";
import api from "/src/api/index.ts";
import { useToast } from "/src/composables/useToast.ts";
import { useConfirm } from "/src/composables/useConfirm.ts";
const _sfc_main = /* @__PURE__ */ _defineComponent({
  __name: "PluginHost",
  setup(__props, { expose: __expose }) {
    __expose();
    const route = useRoute();
    const toast = useToast();
    const confirm = useConfirm();
    const host = ref(null);
    const loading = ref(false);
    const error = ref("");
    const pluginId = computed(() => String(route.params.pluginId || ""));
    let dispose = null;
    let styleEl = null;
    function clearMounted() {
      if (dispose) {
        try {
          dispose();
        } catch {
        }
        dispose = null;
      }
      if (styleEl) {
        styleEl.remove();
        styleEl = null;
      }
      if (host.value) host.value.innerHTML = "";
    }
    function makeButton(options = {}) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = ["noor-plugin-btn", options.tone === "primary" ? "noor-plugin-btn--primary" : "", options.tone === "danger" ? "noor-plugin-btn--danger" : "", options.className || ""].filter(Boolean).join(" ");
      btn.textContent = options.label || "";
      if (options.title) btn.title = options.title;
      if (options.disabled) btn.disabled = true;
      if (options.onClick) btn.onclick = options.onClick;
      return btn;
    }
    function makeInput(options = {}) {
      const input = document.createElement("input");
      input.className = ["noor-plugin-input", options.className || ""].filter(Boolean).join(" ");
      input.value = options.value ?? "";
      input.placeholder = options.placeholder || "";
      input.readOnly = !!options.readonly;
      input.oninput = () => options.onInput?.(input.value);
      return input;
    }
    function makeSelect(options = {}) {
      const select = document.createElement("select");
      select.className = ["noor-plugin-input", "noor-plugin-select", options.className || ""].filter(Boolean).join(" ");
      for (const item of options.options || []) {
        const opt = document.createElement("option");
        opt.value = String(item.value ?? "");
        opt.textContent = String(item.label ?? item.value ?? "");
        select.appendChild(opt);
      }
      select.value = options.value ?? "";
      select.onchange = () => options.onChange?.(select.value);
      return select;
    }
    function makeField(options = {}) {
      const field = document.createElement("label");
      field.className = ["noor-plugin-field", options.className || ""].filter(Boolean).join(" ");
      const label = document.createElement("span");
      label.className = "noor-plugin-field__label";
      label.textContent = options.label || "";
      field.appendChild(label);
      if (options.control) field.appendChild(options.control);
      if (options.hint) {
        const hint = document.createElement("small");
        hint.className = "noor-plugin-field__hint";
        hint.textContent = options.hint;
        field.appendChild(hint);
      }
      return field;
    }
    function makeModal(options = {}) {
      const mask = document.createElement("div");
      mask.className = "noor-plugin-modal-mask";
      const panel = document.createElement("div");
      panel.className = `noor-plugin-modal noor-plugin-modal--${options.width || "md"}`;
      const head = document.createElement("div");
      head.className = "noor-plugin-modal__head";
      const title = document.createElement("div");
      title.className = "noor-plugin-modal__title";
      title.textContent = options.title || "";
      const closeBtn = makeButton({ label: "×", title: "关闭", className: "noor-plugin-modal__close" });
      head.append(title, closeBtn);
      const body = document.createElement("div");
      body.className = "noor-plugin-modal__body";
      if (Array.isArray(options.content)) options.content.forEach((x) => body.appendChild(x));
      else if (options.content) body.appendChild(options.content);
      panel.append(head, body);
      const footer = document.createElement("div");
      footer.className = "noor-plugin-modal__actions";
      if (Array.isArray(options.footer)) options.footer.forEach((x) => footer.appendChild(x));
      else if (options.footer) footer.appendChild(options.footer);
      if (footer.childNodes.length) panel.appendChild(footer);
      mask.appendChild(panel);
      const close = () => {
        mask.remove();
        options.onClose?.();
      };
      closeBtn.onclick = close;
      mask.onclick = (event) => {
        if (event.target === mask && options.closeOnMask !== false) close();
      };
      document.body.appendChild(mask);
      return { el: mask, body, close };
    }
    function makePanel(options = {}) {
      const mask = document.createElement("div");
      mask.className = "noor-plugin-panel-mask";
      const panel = document.createElement("div");
      panel.className = ["noor-plugin-panel", options.className || ""].filter(Boolean).join(" ");
      const scroll = document.createElement("div");
      scroll.className = "noor-plugin-panel__scroll";
      const head = document.createElement("div");
      head.className = "detail-panel-topbar noor-plugin-panel__head";
      const meta = document.createElement("div");
      meta.className = "detail-panel-topbar__meta noor-plugin-panel__meta";
      if (options.eyebrow) {
        const eyebrow = document.createElement("span");
        eyebrow.className = "detail-panel-topbar__eyebrow noor-plugin-panel__eyebrow";
        eyebrow.textContent = options.eyebrow;
        meta.appendChild(eyebrow);
      }
      const title = document.createElement("div");
      title.className = "noor-plugin-panel__title";
      title.textContent = options.title || "";
      meta.appendChild(title);
      const closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "detail-panel-topbar__close noor-plugin-panel__close";
      closeBtn.title = "关闭";
      closeBtn.setAttribute("aria-label", "关闭");
      closeBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>`;
      head.append(meta, closeBtn);
      const body = document.createElement("div");
      body.className = "noor-plugin-panel__body";
      if (Array.isArray(options.content)) options.content.forEach((x) => body.appendChild(x));
      else if (options.content) body.appendChild(options.content);
      scroll.append(head, body);
      panel.appendChild(scroll);
      mask.appendChild(panel);
      const close = () => {
        mask.remove();
        options.onClose?.();
      };
      closeBtn.onclick = close;
      mask.onclick = (event) => {
        if (event.target === mask && options.closeOnMask !== false) close();
      };
      document.body.appendChild(mask);
      return { el: mask, body, close, panel };
    }
    function makeTabs(options = {}) {
      const wrap = document.createElement("div");
      wrap.className = "noor-plugin-tabs";
      const marker = document.createElement("span");
      marker.className = "noor-plugin-tabs__marker";
      wrap.appendChild(marker);
      const buttons = [];
      const getTabValue = (tab) => String(tab?.value ?? tab?.key ?? "");
      const initialTabs = Array.isArray(options.tabs) ? options.tabs : [];
      const initialValue = String(options.value ?? "") || getTabValue(initialTabs[0]);
      options.value = initialValue;
      let raf = 0;
      const refresh = () => {
        if (!wrap.isConnected) return;
        const activeValue = String(options.value ?? "");
        buttons.forEach((button) => button.classList.toggle("is-active", button.dataset.value === activeValue));
        const active = buttons.find((b) => b.dataset.value === activeValue) || buttons[0];
        if (!active) return;
        marker.style.width = `${active.offsetWidth}px`;
        marker.style.transform = `translateX(${active.offsetLeft}px)`;
      };
      const scheduleRefresh = () => {
        if (raf) cancelAnimationFrame(raf);
        raf = requestAnimationFrame(() => {
          raf = 0;
          refresh();
        });
      };
      for (const tab of initialTabs) {
        const value = getTabValue(tab);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = tab.label ?? value;
        btn.dataset.value = value;
        btn.className = "noor-plugin-tabs__item";
        btn.onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          if (String(options.value ?? "") === value) return;
          options.value = value;
          refresh();
          options.onChange?.(value);
          scheduleRefresh();
        };
        buttons.push(btn);
        wrap.appendChild(btn);
      }
      scheduleRefresh();
      requestAnimationFrame(() => {
        refresh();
        wrap.classList.add("noor-plugin-tabs--ready");
      });
      window.addEventListener("resize", scheduleRefresh);
      const setValue = (value) => {
        options.value = String(value);
        refresh();
      };
      const dispose2 = () => {
        if (raf) cancelAnimationFrame(raf);
        window.removeEventListener("resize", scheduleRefresh);
      };
      wrap.dispose = dispose2;
      wrap.__noorDispose = dispose2;
      wrap.__noorSetValue = setValue;
      return wrap;
    }
    function makePagination(options = {}) {
      const wrap = document.createElement("div");
      wrap.className = "noor-pagination noor-plugin-pagination";
      const page = Number(options.page || 1);
      const total = Math.max(1, Number(options.totalPages || 1));
      const go = (target) => {
        const next = Math.min(Math.max(1, target), total);
        if (next !== page) options.onPage?.(next);
      };
      const mk = (label, target, disabled = false, active = false) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = `noor-pagination__btn${active ? " noor-pagination__page is-active" : ""}`;
        btn.textContent = label;
        btn.disabled = disabled;
        btn.onclick = () => !disabled && go(target);
        return btn;
      };
      wrap.append(mk("上一页", page - 1, page <= 1));
      const siblingCount = Math.max(1, Number(options.siblingCount ?? 2));
      const start = Math.max(1, page - siblingCount);
      const end = Math.min(total, page + siblingCount);
      for (let p = start; p <= end; p++) wrap.append(mk(String(p), p, false, p === page));
      wrap.append(mk("下一页", page + 1, page >= total));
      const onKeydown = (event) => {
        if (options.keyboard === false) return;
        const target = event.target;
        if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
        if (event.key === "PageUp") {
          event.preventDefault();
          go(page - 1);
        } else if (event.key === "PageDown") {
          event.preventDefault();
          go(page + 1);
        } else if (event.key === "Home") {
          event.preventDefault();
          go(1);
        } else if (event.key === "End") {
          event.preventDefault();
          go(total);
        }
      };
      window.addEventListener("keydown", onKeydown);
      wrap.__noorDispose = () => window.removeEventListener("keydown", onKeydown);
      return wrap;
    }
    function makeSubmitButton(options = {}) {
      const btn = makeButton({ label: "", tone: "primary", className: ["noor-submit-btn", options.className || ""].filter(Boolean).join(" ") });
      const bar = document.createElement("i");
      bar.className = "noor-submit-btn__bar";
      const text = document.createElement("span");
      text.className = "noor-submit-btn__text";
      btn.append(bar, text);
      const normalize = (state) => state === "submitting" ? "running" : state || "idle";
      const labelFor = (state, progress = 0, label = "") => {
        if (label) return label;
        if (state === "success") return options.successLabel || "已完成";
        if (state === "error") return options.errorLabel || "失败";
        if (state === "running") return options.submittingLabel || options.runningLabel || (progress > 0 ? `${Math.round(progress)}%` : "提交中");
        return options.idleLabel || options.label || "提交";
      };
      const setState = (state, progress = 0, label = "") => {
        const next = normalize(state);
        const pct = Math.max(0, Math.min(100, Number(progress || 0)));
        btn.dataset.state = next;
        btn.classList.toggle("is-running", next === "running");
        btn.classList.toggle("is-success", next === "success");
        btn.classList.toggle("is-error", next === "error");
        btn.style.setProperty("--submit-progress", `${pct}%`);
        text.textContent = labelFor(next, pct, label);
        if (options.disableWhileRunning !== false && next === "running") btn.disabled = true;
        else if (next === "success" && options.disableOnSuccess !== false) btn.disabled = true;
        else btn.disabled = !!options.disabled;
      };
      btn.onclick = (event) => {
        if (btn.disabled) return;
        options.onClick?.(event);
      };
      btn.__setState = setState;
      setState(options.status || "idle", Number(options.progress || 0), options.labelOverride || "");
      return btn;
    }
    function appendChildren(parent, children) {
      if (!children) return parent;
      const list = Array.isArray(children) ? children : [children];
      for (const child of list) {
        if (!child) continue;
        if (child instanceof Node) parent.appendChild(child);
        else parent.appendChild(document.createTextNode(String(child)));
      }
      return parent;
    }
    function makeTopBar(options = {}) {
      const bar = document.createElement("div");
      bar.className = ["noor-plugin-topbar", options.className || ""].filter(Boolean).join(" ");
      const tabs = document.createElement("div");
      tabs.className = "noor-plugin-topbar__tabs";
      const actions = document.createElement("div");
      actions.className = "noor-plugin-topbar__actions";
      appendChildren(tabs, options.tabs || options.left);
      appendChildren(actions, options.actions || options.right);
      bar.append(tabs, actions);
      return { el: bar, tabs, actions };
    }
    function makeActionRow(options = {}) {
      const row = document.createElement("div");
      row.className = ["noor-plugin-action-row", options.className || ""].filter(Boolean).join(" ");
      appendChildren(row, options.children || options.items);
      return row;
    }
    function makeStatCard(options = {}) {
      const card = document.createElement(options.onClick ? "button" : "div");
      card.className = ["noor-plugin-stat-card", options.tone ? `noor-plugin-stat-card--${options.tone}` : "", options.className || ""].filter(Boolean).join(" ");
      if (options.onClick) {
        ;
        card.type = "button";
        card.onclick = options.onClick;
      }
      const label = document.createElement("span");
      label.className = "noor-plugin-stat-card__label";
      label.textContent = options.label || "";
      const value = document.createElement("strong");
      value.className = "noor-plugin-stat-card__value";
      value.textContent = String(options.value ?? "-");
      card.append(label, value);
      if (options.hint) {
        const hint = document.createElement("small");
        hint.className = "noor-plugin-stat-card__hint";
        hint.textContent = String(options.hint);
        card.appendChild(hint);
      }
      return card;
    }
    function makeStatGrid(options = {}) {
      const grid = document.createElement("div");
      grid.className = ["noor-plugin-stat-grid", options.className || ""].filter(Boolean).join(" ");
      const items = Array.isArray(options.items) ? options.items : [];
      for (const item of items) grid.appendChild(makeStatCard(item));
      return grid;
    }
    function makeMediaCard(options = {}) {
      const card = document.createElement(options.onClick ? "button" : options.href ? "a" : "div");
      card.className = ["noor-plugin-media-card", options.sharp ? "noor-plugin-media-card--sharp" : "", options.className || ""].filter(Boolean).join(" ");
      if (options.href) {
        ;
        card.href = options.href;
        card.target = options.target || "_self";
      }
      if (options.onClick) {
        ;
        card.type = "button";
        card.onclick = options.onClick;
      }
      const cover = document.createElement("div");
      cover.className = ["noor-plugin-media-card__cover", options.coverOnClick ? "is-clickable" : ""].filter(Boolean).join(" ");
      if (options.coverOnClick) cover.onclick = (e) => {
        e.stopPropagation();
        options.coverOnClick();
      };
      if (options.image || options.cover || options.coverUrl) {
        const img = document.createElement("img");
        img.src = options.image || options.cover || options.coverUrl;
        img.loading = options.loading || "lazy";
        cover.appendChild(img);
      } else {
        const ph = document.createElement("div");
        ph.className = "noor-plugin-media-card__placeholder";
        ph.textContent = options.placeholder || "NO IMAGE";
        cover.appendChild(ph);
      }
      const body = document.createElement("div");
      body.className = "noor-plugin-media-card__body";
      const title = document.createElement("div");
      title.className = ["noor-plugin-media-card__title", options.titleOnClick ? "is-clickable" : ""].filter(Boolean).join(" ");
      title.textContent = options.title || "";
      if (options.titleOnClick) title.onclick = (e) => {
        e.stopPropagation();
        options.titleOnClick();
      };
      body.appendChild(title);
      if (options.meta) {
        const meta = document.createElement("div");
        meta.className = "noor-plugin-media-card__meta";
        const metaItems = Array.isArray(options.meta) ? options.meta : [options.meta];
        for (const text of metaItems.filter(Boolean)) {
          const span = document.createElement("span");
          span.textContent = String(text);
          meta.appendChild(span);
        }
        body.appendChild(meta);
      }
      if (options.badges) {
        const badges = document.createElement("div");
        badges.className = "noor-plugin-media-card__badges";
        appendChildren(badges, options.badges);
        body.appendChild(badges);
      }
      if (options.actions) {
        const actions = document.createElement("div");
        actions.className = "noor-plugin-media-card__actions";
        appendChildren(actions, options.actions);
        body.appendChild(actions);
      }
      card.append(cover, body);
      return card;
    }
    function makeLoadingState(options = {}) {
      const d = document.createElement("div");
      d.className = ["noor-plugin-state", "noor-plugin-state--loading", options.className || ""].filter(Boolean).join(" ");
      const spinner = document.createElement("span");
      spinner.className = "noor-plugin-spinner";
      const text = document.createElement("span");
      text.textContent = options.text || "加载中…";
      d.append(spinner, text);
      return d;
    }
    function lastSavepathKey(downloaderId) {
      return `noor:last-download-savepath:${downloaderId || "default"}`;
    }
    function readLastSavepath(downloaderId) {
      try {
        return localStorage.getItem(lastSavepathKey(downloaderId)) || "";
      } catch {
        return "";
      }
    }
    function writeLastSavepath(downloaderId, value) {
      try {
        if (value) localStorage.setItem(lastSavepathKey(downloaderId), value);
      } catch {
      }
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[c]);
    }
    function renderResourcePreview(resourceState) {
      const d = document.createElement("div");
      d.className = "noor-downloader-preview";
      if (!resourceState.options?.supports_resource_preview) return d;
      if (resourceState.loading) {
        d.innerHTML = '<div class="noor-downloader-preview__head"><span>资源预览</span><em>读取中...</em></div>';
        return d;
      }
      if (resourceState.error) {
        d.innerHTML = `<div class="noor-downloader-preview__head"><span>资源预览</span><em class="is-error">${escapeHtml(resourceState.error)}</em></div>`;
        return d;
      }
      const files = Array.isArray(resourceState.data?.files) ? resourceState.data.files : [];
      if (!files.length) {
        d.innerHTML = '<div class="noor-downloader-preview__head"><span>资源预览</span><em>暂无文件信息</em></div>';
        return d;
      }
      const visible = files.slice(0, 6);
      d.innerHTML = `<div class="noor-downloader-preview__head"><span>资源预览</span><em>${escapeHtml(resourceState.data?.total_size_formatted || "")} · ${files.length} 个文件</em></div>
  <div class="noor-downloader-preview__files">${visible.map((file) => `<div class="noor-downloader-preview__file"><span>${escapeHtml(file.name || file.full_path || "")}</span><em>${escapeHtml(file.size_formatted || "")}</em></div>`).join("")}${files.length > visible.length ? `<div class="noor-downloader-preview__more">还有 ${files.length - visible.length} 个文件</div>` : ""}</div>`;
      return d;
    }
    function createDownloaderDialogContext(sourcePluginId) {
      let progressTimer = null;
      async function postJson(url, payload) {
        const res = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ payload })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data?.ok === false) throw new Error(data?.detail || data?.message || "请求失败");
        return data;
      }
      async function open(options = {}) {
        const allowBatchUrls = !!options.allowBatchUrls;
        const showDownloaderField = options.showDownloaderField !== false;
        const previewEnabled = options.preview !== false;
        const maxUrls = Number(options.maxUrls || 0);
        const submitIdleLabel = String(options.submitIdleLabel || (allowBatchUrls ? "创建任务" : "推送下载"));
        const submitSuccessLabel = String(options.submitSuccessLabel || (allowBatchUrls ? "创建成功" : "推送成功"));
        const submitErrorLabel = String(options.submitErrorLabel || (allowBatchUrls ? "创建失败" : "推送失败"));
        const submitPartialLabel = String(options.submitPartialLabel || "部分失败");
        const state = {
          downloaderId: String(options.downloaderId || "").trim(),
          title: String(options.title || ""),
          name: String(options.name || options.rename || options.title || ""),
          rename: String(options.rename || options.name || options.title || ""),
          titleOptions: Array.isArray(options.titleOptions) ? options.titleOptions.filter(Boolean) : [],
          titleMode: String(options.titleMode || ""),
          url: String(options.url || options.magnet || options.urls || ""),
          urlsText: String(options.urlsText || options.urls || options.url || options.magnet || ""),
          itemTitle: String(options.itemTitle || options.title || ""),
          fileIndices: "auto",
          savepath: "",
          selectedPath: "",
          category: "",
          minFileSizeMb: "",
          options: null,
          error: "",
          loading: true,
          previewLoading: false,
          previewError: "",
          previewData: null,
          submitStatus: "idle",
          submitProgress: 0,
          submitting: false,
          submitButton: null
        };
        if (!state.downloaderId) throw new Error("未绑定下载器");
        if (!allowBatchUrls && !state.url) throw new Error("缺少下载链接");
        if (!state.titleMode && state.titleOptions.length) state.titleMode = String(state.titleOptions[0]?.key || "");
        const modal = makeModal({
          title: String(options.modalTitle || (allowBatchUrls ? "新建下载任务" : "推送下载")),
          width: "md",
          closeOnMask: false,
          onClose: () => {
            if (state.submitting) return;
            if (progressTimer) window.clearInterval(progressTimer);
          }
        });
        async function loadOptions() {
          state.loading = true;
          state.error = "";
          render();
          try {
            const infoRes = await api.get(`/plugins/${state.downloaderId}/config`).then((r) => r.data).catch(() => null);
            const dlOptions = await postJson(`/api/plugins/${state.downloaderId}/actions/download_options`, {});
            state.options = dlOptions;
            state.downloaderName = infoRes?.plugin?.name || dlOptions.downloader || state.downloaderId;
            state.fileIndices = String(dlOptions.file_indices || state.fileIndices || "auto");
            state.category = String(dlOptions.default_category || "");
            state.savepath = readLastSavepath(state.downloaderId) || String(dlOptions.default_savepath || "");
            state.selectedPath = state.savepath;
            if (dlOptions.small_file_filter && typeof dlOptions.small_file_filter === "object") {
              const raw = dlOptions.small_file_filter.default_mb;
              state.minFileSizeMb = raw === void 0 || raw === null || raw === "" ? "" : String(raw);
            }
            const found = (dlOptions.categories || []).find((item) => item.name === state.category);
            if (found?.save_path && !state.savepath) state.savepath = String(found.save_path);
            if (!state.savepath) {
              const firstPath = Array.isArray(dlOptions.paths) ? dlOptions.paths.find((item) => item?.path)?.path : "";
              if (firstPath) {
                state.savepath = String(firstPath);
                state.selectedPath = state.savepath;
              }
            }
            if (previewEnabled && dlOptions.supports_resource_preview && !allowBatchUrls && state.url) await loadPreview();
          } catch (e) {
            state.error = e?.message || "下载器配置读取失败";
            state.options = { categories: [] };
          } finally {
            state.loading = false;
            render();
          }
        }
        async function loadPreview() {
          if (!state.options?.supports_resource_preview) return;
          state.previewLoading = true;
          state.previewError = "";
          state.previewData = null;
          render();
          try {
            const previewUrl = String(state.url || state.urlsText || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean)[0] || "";
            if (!previewUrl) return;
            state.previewData = await postJson(`/api/plugins/${state.downloaderId}/actions/resource_info`, { url: previewUrl, magnet: previewUrl });
          } catch (e) {
            state.previewError = e?.message || "资源预览失败";
          } finally {
            state.previewLoading = false;
            render();
          }
        }
        async function submit() {
          if (state.submitting) return;
          state.submitting = true;
          state.submitStatus = "running";
          state.submitProgress = 8;
          state.error = "";
          state.submitButton?.__setState?.("running", 8, "8%");
          render();
          progressTimer = window.setInterval(() => {
            if (!state.submitting || state.submitStatus !== "running") return;
            state.submitProgress = Math.min(92, Number(state.submitProgress || 0) + 8);
            state.submitButton?.__setState?.("running", state.submitProgress, `${Math.round(state.submitProgress)}%`);
          }, 180);
          try {
            const urlList = String(allowBatchUrls ? state.urlsText : state.url || state.urlsText || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
            if (!urlList.length) throw new Error("请填写下载链接");
            if (maxUrls > 0 && urlList.length > maxUrls) throw new Error(`单次最多添加 ${maxUrls} 条链接`);
            const firstUrl = urlList[0] || "";
            const payload = {
              url: firstUrl,
              urls: allowBatchUrls ? urlList.join("\n") : firstUrl,
              magnet: firstUrl,
              title: state.title,
              name: state.name,
              rename: state.options?.supports_rename ? state.rename : "",
              savepath: state.options?.supports_savepath ? state.savepath : "",
              category: state.options?.supports_categories ? state.category : "",
              file_indices: state.options?.supports_file_indices ? state.fileIndices : void 0,
              min_file_size_mb: state.options?.supports_small_file_filter ? state.minFileSizeMb : void 0,
              source_plugin: sourcePluginId
            };
            const result = await postJson(`/api/plugins/${state.downloaderId}/downloads`, payload);
            writeLastSavepath(state.downloaderId, state.savepath || "");
            const partialFailure = Number(result?.failure_count || 0) > 0;
            state.submitStatus = partialFailure ? "error" : "success";
            state.submitProgress = 100;
            if (partialFailure) {
              state.error = String(result?.message || `${result?.failure_count || 0} 条任务失败`);
              state.submitButton?.__setState?.("error", 100, submitPartialLabel);
            } else {
              state.submitButton?.__setState?.("success", 100, submitSuccessLabel);
            }
            render();
            return result;
          } catch (e) {
            state.error = e?.message || "推送失败";
            state.submitStatus = "error";
            state.submitProgress = 100;
            state.submitButton?.__setState?.("error", 100, "推送失败");
            render();
            throw e;
          } finally {
            state.submitting = false;
            if (progressTimer) {
              window.clearInterval(progressTimer);
              progressTimer = null;
            }
          }
        }
        function render() {
          const body = modal.body;
          body.innerHTML = "";
          if (state.error) body.appendChild(Object.assign(document.createElement("div"), { className: "noor-plugin-notice noor-plugin-notice--error", textContent: state.error }));
          const form = document.createElement("div");
          form.className = "noor-downloader-form";
          if (showDownloaderField) {
            const downloaderInput = makeInput({ value: state.downloaderName || state.downloaderId, readonly: true });
            form.appendChild(makeField({ label: "下载器", control: downloaderInput }));
          }
          if (allowBatchUrls) {
            const urlsInput = document.createElement("textarea");
            urlsInput.className = "noor-plugin-input noor-downloader-textarea";
            urlsInput.rows = Number(options.urlRows || 6);
            urlsInput.placeholder = String(options.urlPlaceholder || "每行一个 magnet / BT URL / 普通 URL");
            urlsInput.value = state.urlsText;
            urlsInput.oninput = () => {
              state.urlsText = urlsInput.value;
            };
            form.appendChild(makeField({
              label: options.urlLabel || "下载链接",
              hint: maxUrls > 0 ? `支持批量添加：每行一条，最多 ${maxUrls} 条。` : "支持批量添加：每行一条。",
              control: urlsInput
            }));
          }
          const categories = Array.isArray(state.options?.categories) ? state.options.categories : [];
          if (state.options?.supports_categories) {
            const categorySelect = makeSelect({
              value: state.category,
              options: [{ value: "", label: "不使用分类路径" }].concat(categories.map((item) => ({ value: item.name, label: `${item.name}${item.save_path ? ` · ${item.save_path}` : ""}` }))),
              onChange: (value) => {
                state.category = value;
                const found = categories.find((item) => item.name === value);
                if (found?.save_path) state.savepath = String(found.save_path);
                render();
              }
            });
            form.appendChild(makeField({ label: "分类 / 路径建议", control: categorySelect }));
          }
          const paths = Array.isArray(state.options?.paths) ? state.options.paths.filter((item) => item?.path) : [];
          if (state.options?.supports_savepath && paths.length) {
            const pathSelect = makeSelect({
              value: state.selectedPath || state.savepath,
              options: [{ value: "", label: "选择历史路径" }].concat(paths.map((item) => ({
                value: String(item.path || ""),
                label: String(item.name || item.path || "")
              }))),
              onChange: (value) => {
                state.selectedPath = value;
                if (value) state.savepath = value;
                render();
              }
            });
            form.appendChild(makeField({ label: "历史路径", control: pathSelect, hint: "选择后仍可继续编辑为更深层的子目录。" }));
          }
          if (state.options?.supports_rename) {
            const renameInput = makeInput({
              value: state.rename,
              placeholder: state.itemTitle || "下载任务名称",
              onInput: (value) => {
                state.rename = value;
                state.name = value;
              }
            });
            if (state.titleOptions.length > 1) {
              const titleModeSelect = makeSelect({
                value: state.titleMode || String(state.titleOptions[0]?.key || ""),
                options: state.titleOptions.map((item) => ({ value: String(item.key || item.label || item.value || ""), label: String(item.label || item.key || "") })),
                onChange: (value) => {
                  state.titleMode = value;
                  const found = state.titleOptions.find((item) => String(item.key || "") === value);
                  if (found?.value) {
                    state.rename = String(found.value);
                    state.name = String(found.value);
                  }
                  render();
                }
              });
              const combo = document.createElement("div");
              combo.className = "noor-downloader-title-combo";
              combo.append(renameInput, titleModeSelect);
              const activeHint = state.titleOptions.find((item) => String(item.key || "") === state.titleMode)?.hint || "优先使用智能命名";
              form.appendChild(makeField({ label: "下载任务名称", control: combo, hint: activeHint }));
            } else {
              form.appendChild(makeField({ label: "下载任务名称", control: renameInput }));
            }
          }
          if (state.options?.supports_savepath) {
            const savepathInput = makeInput({
              value: state.savepath,
              placeholder: "/downloads/av",
              onInput: (value) => {
                state.savepath = value;
                state.selectedPath = value;
              }
            });
            form.appendChild(makeField({ label: "下载路径", control: savepathInput, hint: "优先使用下载器插件返回的历史路径或默认路径。" }));
          }
          if (state.options?.supports_file_indices) {
            const fileOptions = Array.isArray(state.options?.file_indices_options) ? state.options.file_indices_options.filter(Boolean) : [];
            const fileControl = fileOptions.length ? makeSelect({
              value: state.fileIndices,
              options: fileOptions.map((item) => ({ value: String(item.value ?? ""), label: String(item.label ?? item.value ?? "") })),
              onChange: (value) => {
                state.fileIndices = value;
              }
            }) : makeInput({
              value: state.fileIndices,
              placeholder: "auto / --1 / 0 / 1,3",
              onInput: (value) => {
                state.fileIndices = value;
              }
            });
            const fileHint = fileOptions.find((item) => String(item.value ?? "") === String(state.fileIndices))?.hint || "";
            form.appendChild(makeField({ label: "文件选择", control: fileControl, hint: fileHint || void 0 }));
          }
          if (state.options?.supports_small_file_filter) {
            const filterInput = makeInput({
              value: state.minFileSizeMb,
              placeholder: String(state.options?.small_file_filter?.default_mb ?? "0"),
              onInput: (value) => {
                state.minFileSizeMb = value;
              }
            });
            const filterHint = state.options?.small_file_filter?.keep_subtitles ? "自动过滤小于该阈值的非字幕文件，字幕始终保留。填 0 表示关闭。" : "自动过滤小于该阈值的文件。填 0 表示关闭。";
            form.appendChild(makeField({ label: "自动过滤小文件（MB）", control: filterInput, hint: filterHint }));
          }
          body.appendChild(form);
          if (state.loading) body.appendChild(makeLoadingState({ text: "读取下载器配置中…" }));
          else if (state.options?.supports_resource_preview) {
            body.appendChild(renderResourcePreview({
              options: state.options,
              loading: state.previewLoading,
              error: state.previewError,
              data: state.previewData
            }));
          }
          const footer = document.createElement("div");
          footer.className = "noor-plugin-modal__actions";
          const cancel = makeButton({ label: "关闭", onClick: () => !state.submitting && modal.close() });
          const submitBtn = makeSubmitButton({
            idleLabel: submitIdleLabel,
            submittingLabel: "推送中",
            successLabel: submitSuccessLabel,
            errorLabel: submitErrorLabel,
            status: state.submitStatus,
            progress: state.submitProgress,
            className: "noor-downloader-submit",
            disabled: state.loading || !(allowBatchUrls ? String(state.urlsText || "").trim() : String(state.url || "").trim()) || !state.downloaderId || state.submitStatus === "success",
            onClick: async () => {
              try {
                const result = await submit();
                options.onSuccess?.(result);
              } catch (e) {
                options.onError?.(e);
              }
            }
          });
          state.submitButton = submitBtn;
          footer.append(cancel, submitBtn);
          const existingFooter = modal.el.querySelector(".noor-plugin-modal__actions");
          if (existingFooter) existingFooter.remove();
          modal.el.querySelector(".noor-plugin-modal")?.appendChild(footer);
        }
        await loadOptions();
        if (allowBatchUrls) {
          window.setTimeout(() => {
            const input = modal.body.querySelector(".noor-downloader-textarea");
            input?.focus();
          }, 0);
        }
        render();
        return modal;
      }
      return { open, openTask: open };
    }
    function sdkFor(id) {
      const pluginFetch = (path, init) => fetch(`/api/plugins/${id}${path}`, init);
      const downloads = createDownloaderDialogContext(id);
      return {
        pluginId: id,
        api: {
          plugin: pluginFetch,
          wsUrl: (path) => `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/plugins/${id}${path}`,
          get: (path, config) => api.get(path, config),
          post: (path, data, config) => api.post(path, data, config)
        },
        toast: {
          success: (msg) => toast.success(msg),
          error: (msg) => toast.error(msg),
          info: (msg) => toast.info(msg),
          warning: (msg) => toast.warning(msg)
        },
        downloads,
        ui: {
          button: makeButton,
          input: makeInput,
          select: makeSelect,
          field: makeField,
          modal: makeModal,
          panel: makePanel,
          tabs: makeTabs,
          pagination: makePagination,
          submitButton: makeSubmitButton,
          topBar: makeTopBar,
          actionRow: makeActionRow,
          statCard: makeStatCard,
          statGrid: makeStatGrid,
          mediaCard: makeMediaCard,
          loadingState: makeLoadingState,
          badge: (o) => {
            const b = document.createElement(o.onClick ? "button" : "span");
            b.className = ["noor-plugin-badge", o.tone ? `noor-plugin-badge--${o.tone}` : "", o.className || ""].filter(Boolean).join(" ");
            b.textContent = o.label || "";
            if (o.onClick) b.onclick = o.onClick;
            return b;
          },
          chip: (o) => {
            const b = makeButton({ label: o.label, className: ["noor-plugin-chip", o.active ? "is-active" : "", o.className || ""].filter(Boolean).join(" ") });
            b.onclick = o.onClick;
            return b;
          },
          notice: (o) => {
            const d = document.createElement("div");
            d.className = `noor-plugin-notice noor-plugin-notice--${o.tone || "info"}`;
            d.textContent = o.text || "";
            return d;
          },
          emptyState: (o) => {
            const d = document.createElement("div");
            d.className = "noor-plugin-state";
            d.textContent = o.text || "暂无内容";
            return d;
          },
          errorState: (o) => {
            const d = document.createElement("div");
            d.className = "noor-plugin-state noor-plugin-state--error";
            d.textContent = o.text || "加载失败";
            return d;
          },
          skeletonCard: (o) => {
            const d = document.createElement("div");
            d.className = `noor-plugin-skeleton ${o.className || ""}`;
            return d;
          },
          card: (o) => {
            const a = document.createElement(o.href ? "a" : "div");
            a.className = `noor-plugin-card ${o.className || ""}`;
            if (o.href) {
              a.href = o.href;
              a.target = o.target || "_self";
            }
            ;
            return a;
          },
          confirm: (o) => confirm.confirm({ title: o.title || "确认操作", message: o.message || "", confirmText: o.confirmText || "确认", danger: !!o.danger })
        }
      };
    }
    async function mountPlugin() {
      clearMounted();
      if (!pluginId.value || !host.value) return;
      loading.value = true;
      error.value = "";
      try {
        const info = await api.get(`/plugins/${pluginId.value}/config`).then((r) => r.data);
        const style = info?.plugin?.frontend?.style;
        if (style) {
          const bust = Date.now();
          styleEl = document.createElement("link");
          styleEl.rel = "stylesheet";
          styleEl.href = `/api/plugins/${pluginId.value}/assets/${style.replace(/^frontend\//, "")}?t=${bust}`;
          document.head.appendChild(styleEl);
        }
        const entry = info?.plugin?.frontend?.entry || "frontend/page.js";
        const mod = await import(
          /* @vite-ignore */
          `/api/plugins/${pluginId.value}/assets/${entry.replace(/^frontend\//, "")}?t=${Date.now()}`
        );
        await nextTick();
        const ret = await mod.mount(host.value, sdkFor(pluginId.value));
        if (typeof ret === "function") dispose = ret;
      } catch (e) {
        error.value = e?.response?.data?.detail || e?.message || "插件加载失败";
      } finally {
        loading.value = false;
      }
    }
    onMounted(mountPlugin);
    watch(pluginId, mountPlugin);
    onBeforeUnmount(clearMounted);
    const __returned__ = { route, toast, confirm, host, loading, error, pluginId, get dispose() {
      return dispose;
    }, set dispose(v) {
      dispose = v;
    }, get styleEl() {
      return styleEl;
    }, set styleEl(v) {
      styleEl = v;
    }, clearMounted, makeButton, makeInput, makeSelect, makeField, makeModal, makePanel, makeTabs, makePagination, makeSubmitButton, appendChildren, makeTopBar, makeActionRow, makeStatCard, makeStatGrid, makeMediaCard, makeLoadingState, lastSavepathKey, readLastSavepath, writeLastSavepath, escapeHtml, renderResourcePreview, createDownloaderDialogContext, sdkFor, mountPlugin };
    Object.defineProperty(__returned__, "__isScriptSetup", { enumerable: false, value: true });
    return __returned__;
  }
});
import { openBlock as _openBlock, createElementBlock as _createElementBlock, createCommentVNode as _createCommentVNode, toDisplayString as _toDisplayString, normalizeClass as _normalizeClass, createElementVNode as _createElementVNode } from "/node_modules/.vite/deps/vue.js?v=d223f038";
const _hoisted_1 = { class: "plugin-host-page" };
const _hoisted_2 = {
  key: 0,
  class: "plugin-host-state"
};
const _hoisted_3 = {
  key: 1,
  class: "plugin-host-state plugin-host-state--error"
};
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return _openBlock(), _createElementBlock("div", _hoisted_1, [
    $setup.loading ? (_openBlock(), _createElementBlock("div", _hoisted_2, "插件加载中")) : _createCommentVNode("v-if", true),
    $setup.error ? (_openBlock(), _createElementBlock(
      "div",
      _hoisted_3,
      _toDisplayString($setup.error),
      1
      /* TEXT */
    )) : _createCommentVNode("v-if", true),
    _createElementVNode(
      "div",
      {
        ref: "host",
        class: _normalizeClass(["plugin-host-mount", { "is-loading": $setup.loading }])
      },
      null,
      2
      /* CLASS */
    )
  ]);
}
import "/src/views/PluginHost.vue?vue&type=style&index=0&lang.css";
_sfc_main.__hmrId = "051f225f";
typeof __VUE_HMR_RUNTIME__ !== "undefined" && __VUE_HMR_RUNTIME__.createRecord(_sfc_main.__hmrId, _sfc_main);
import.meta.hot.on("file-changed", ({ file }) => {
  __VUE_HMR_RUNTIME__.CHANGED_FILE = file;
});
import.meta.hot.accept((mod) => {
  if (!mod) return;
  const { default: updated, _rerender_only } = mod;
  if (_rerender_only) {
    __VUE_HMR_RUNTIME__.rerender(updated.__hmrId, updated.render);
  } else {
    __VUE_HMR_RUNTIME__.reload(updated.__hmrId, updated);
  }
});
import _export_sfc from "/@id/__x00__plugin-vue:export-helper";
export default /* @__PURE__ */ _export_sfc(_sfc_main, [["render", _sfc_render], ["__file", "/home/kinax/noor-restored/frontend/src/views/PluginHost.vue"]]);

//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJtYXBwaW5ncyI6IjtBQUNBLFNBQVMsVUFBVSxVQUFVLGlCQUFpQixXQUFXLEtBQUssYUFBYTtBQUMzRSxTQUFTLGdCQUFnQjtBQUN6QixPQUFPLFNBQVM7QUFDaEIsU0FBUyxnQkFBZ0I7QUFDekIsU0FBUyxrQkFBa0I7Ozs7O0FBRTNCLFVBQU0sUUFBUSxTQUFTO0FBQ3ZCLFVBQU0sUUFBUSxTQUFTO0FBQ3ZCLFVBQU0sVUFBVSxXQUFXO0FBQzNCLFVBQU0sT0FBTyxJQUF3QixJQUFJO0FBQ3pDLFVBQU0sVUFBVSxJQUFJLEtBQUs7QUFDekIsVUFBTSxRQUFRLElBQUksRUFBRTtBQUNwQixVQUFNLFdBQVcsU0FBUyxNQUFNLE9BQU8sTUFBTSxPQUFPLFlBQVksRUFBRSxDQUFDO0FBQ25FLFFBQUksVUFBK0I7QUFDbkMsUUFBSSxVQUFrQztBQUV0QyxhQUFTLGVBQWU7QUFDdEIsVUFBSSxTQUFTO0FBQ1gsWUFBSTtBQUFFLGtCQUFRO0FBQUEsUUFBRSxRQUFRO0FBQUEsUUFBQztBQUN6QixrQkFBVTtBQUFBLE1BQ1o7QUFDQSxVQUFJLFNBQVM7QUFDWCxnQkFBUSxPQUFPO0FBQ2Ysa0JBQVU7QUFBQSxNQUNaO0FBQ0EsVUFBSSxLQUFLLE1BQU8sTUFBSyxNQUFNLFlBQVk7QUFBQSxJQUN6QztBQUVBLGFBQVMsV0FBVyxVQUFlLENBQUMsR0FBRztBQUNyQyxZQUFNLE1BQU0sU0FBUyxjQUFjLFFBQVE7QUFDM0MsVUFBSSxPQUFPO0FBQ1gsVUFBSSxZQUFZLENBQUMsbUJBQW1CLFFBQVEsU0FBUyxZQUFZLDZCQUE2QixJQUFJLFFBQVEsU0FBUyxXQUFXLDRCQUE0QixJQUFJLFFBQVEsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQy9NLFVBQUksY0FBYyxRQUFRLFNBQVM7QUFDbkMsVUFBSSxRQUFRLE1BQU8sS0FBSSxRQUFRLFFBQVE7QUFDdkMsVUFBSSxRQUFRLFNBQVUsS0FBSSxXQUFXO0FBQ3JDLFVBQUksUUFBUSxRQUFTLEtBQUksVUFBVSxRQUFRO0FBQzNDLGFBQU87QUFBQSxJQUNUO0FBRUEsYUFBUyxVQUFVLFVBQWUsQ0FBQyxHQUFHO0FBQ3BDLFlBQU0sUUFBUSxTQUFTLGNBQWMsT0FBTztBQUM1QyxZQUFNLFlBQVksQ0FBQyxxQkFBcUIsUUFBUSxhQUFhLEVBQUUsRUFBRSxPQUFPLE9BQU8sRUFBRSxLQUFLLEdBQUc7QUFDekYsWUFBTSxRQUFRLFFBQVEsU0FBUztBQUMvQixZQUFNLGNBQWMsUUFBUSxlQUFlO0FBQzNDLFlBQU0sV0FBVyxDQUFDLENBQUMsUUFBUTtBQUMzQixZQUFNLFVBQVUsTUFBTSxRQUFRLFVBQVUsTUFBTSxLQUFLO0FBQ25ELGFBQU87QUFBQSxJQUNUO0FBRUEsYUFBUyxXQUFXLFVBQWUsQ0FBQyxHQUFHO0FBQ3JDLFlBQU0sU0FBUyxTQUFTLGNBQWMsUUFBUTtBQUM5QyxhQUFPLFlBQVksQ0FBQyxxQkFBcUIsc0JBQXNCLFFBQVEsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQ2hILGlCQUFXLFFBQVEsUUFBUSxXQUFXLENBQUMsR0FBRztBQUN4QyxjQUFNLE1BQU0sU0FBUyxjQUFjLFFBQVE7QUFDM0MsWUFBSSxRQUFRLE9BQU8sS0FBSyxTQUFTLEVBQUU7QUFDbkMsWUFBSSxjQUFjLE9BQU8sS0FBSyxTQUFTLEtBQUssU0FBUyxFQUFFO0FBQ3ZELGVBQU8sWUFBWSxHQUFHO0FBQUEsTUFDeEI7QUFDQSxhQUFPLFFBQVEsUUFBUSxTQUFTO0FBQ2hDLGFBQU8sV0FBVyxNQUFNLFFBQVEsV0FBVyxPQUFPLEtBQUs7QUFDdkQsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLFVBQVUsVUFBZSxDQUFDLEdBQUc7QUFDcEMsWUFBTSxRQUFRLFNBQVMsY0FBYyxPQUFPO0FBQzVDLFlBQU0sWUFBWSxDQUFDLHFCQUFxQixRQUFRLGFBQWEsRUFBRSxFQUFFLE9BQU8sT0FBTyxFQUFFLEtBQUssR0FBRztBQUN6RixZQUFNLFFBQVEsU0FBUyxjQUFjLE1BQU07QUFDM0MsWUFBTSxZQUFZO0FBQ2xCLFlBQU0sY0FBYyxRQUFRLFNBQVM7QUFDckMsWUFBTSxZQUFZLEtBQUs7QUFDdkIsVUFBSSxRQUFRLFFBQVMsT0FBTSxZQUFZLFFBQVEsT0FBTztBQUN0RCxVQUFJLFFBQVEsTUFBTTtBQUNoQixjQUFNLE9BQU8sU0FBUyxjQUFjLE9BQU87QUFDM0MsYUFBSyxZQUFZO0FBQ2pCLGFBQUssY0FBYyxRQUFRO0FBQzNCLGNBQU0sWUFBWSxJQUFJO0FBQUEsTUFDeEI7QUFDQSxhQUFPO0FBQUEsSUFDVDtBQUVBLGFBQVMsVUFBVSxVQUFlLENBQUMsR0FBRztBQUNwQyxZQUFNLE9BQU8sU0FBUyxjQUFjLEtBQUs7QUFDekMsV0FBSyxZQUFZO0FBQ2pCLFlBQU0sUUFBUSxTQUFTLGNBQWMsS0FBSztBQUMxQyxZQUFNLFlBQVksd0NBQXdDLFFBQVEsU0FBUyxJQUFJO0FBQy9FLFlBQU0sT0FBTyxTQUFTLGNBQWMsS0FBSztBQUN6QyxXQUFLLFlBQVk7QUFDakIsWUFBTSxRQUFRLFNBQVMsY0FBYyxLQUFLO0FBQzFDLFlBQU0sWUFBWTtBQUNsQixZQUFNLGNBQWMsUUFBUSxTQUFTO0FBQ3JDLFlBQU0sV0FBVyxXQUFXLEVBQUUsT0FBTyxLQUFLLE9BQU8sTUFBTSxXQUFXLDJCQUEyQixDQUFDO0FBQzlGLFdBQUssT0FBTyxPQUFPLFFBQVE7QUFDM0IsWUFBTSxPQUFPLFNBQVMsY0FBYyxLQUFLO0FBQ3pDLFdBQUssWUFBWTtBQUNqQixVQUFJLE1BQU0sUUFBUSxRQUFRLE9BQU8sRUFBRyxTQUFRLFFBQVEsUUFBUSxDQUFDLE1BQVksS0FBSyxZQUFZLENBQUMsQ0FBQztBQUFBLGVBQ25GLFFBQVEsUUFBUyxNQUFLLFlBQVksUUFBUSxPQUFPO0FBQzFELFlBQU0sT0FBTyxNQUFNLElBQUk7QUFDdkIsWUFBTSxTQUFTLFNBQVMsY0FBYyxLQUFLO0FBQzNDLGFBQU8sWUFBWTtBQUNuQixVQUFJLE1BQU0sUUFBUSxRQUFRLE1BQU0sRUFBRyxTQUFRLE9BQU8sUUFBUSxDQUFDLE1BQVksT0FBTyxZQUFZLENBQUMsQ0FBQztBQUFBLGVBQ25GLFFBQVEsT0FBUSxRQUFPLFlBQVksUUFBUSxNQUFNO0FBQzFELFVBQUksT0FBTyxXQUFXLE9BQVEsT0FBTSxZQUFZLE1BQU07QUFDdEQsV0FBSyxZQUFZLEtBQUs7QUFDdEIsWUFBTSxRQUFRLE1BQU07QUFBRSxhQUFLLE9BQU87QUFBRyxnQkFBUSxVQUFVO0FBQUEsTUFBRTtBQUN6RCxlQUFTLFVBQVU7QUFDbkIsV0FBSyxVQUFVLFdBQVM7QUFBRSxZQUFJLE1BQU0sV0FBVyxRQUFRLFFBQVEsZ0JBQWdCLE1BQU8sT0FBTTtBQUFBLE1BQUU7QUFDOUYsZUFBUyxLQUFLLFlBQVksSUFBSTtBQUM5QixhQUFPLEVBQUUsSUFBSSxNQUFNLE1BQU0sTUFBTTtBQUFBLElBQ2pDO0FBRUEsYUFBUyxVQUFVLFVBQWUsQ0FBQyxHQUFHO0FBQ3BDLFlBQU0sT0FBTyxTQUFTLGNBQWMsS0FBSztBQUN6QyxXQUFLLFlBQVk7QUFDakIsWUFBTSxRQUFRLFNBQVMsY0FBYyxLQUFLO0FBQzFDLFlBQU0sWUFBWSxDQUFDLHFCQUFxQixRQUFRLGFBQWEsRUFBRSxFQUFFLE9BQU8sT0FBTyxFQUFFLEtBQUssR0FBRztBQUN6RixZQUFNLFNBQVMsU0FBUyxjQUFjLEtBQUs7QUFDM0MsYUFBTyxZQUFZO0FBQ25CLFlBQU0sT0FBTyxTQUFTLGNBQWMsS0FBSztBQUN6QyxXQUFLLFlBQVk7QUFDakIsWUFBTSxPQUFPLFNBQVMsY0FBYyxLQUFLO0FBQ3pDLFdBQUssWUFBWTtBQUNqQixVQUFJLFFBQVEsU0FBUztBQUNuQixjQUFNLFVBQVUsU0FBUyxjQUFjLE1BQU07QUFDN0MsZ0JBQVEsWUFBWTtBQUNwQixnQkFBUSxjQUFjLFFBQVE7QUFDOUIsYUFBSyxZQUFZLE9BQU87QUFBQSxNQUMxQjtBQUNBLFlBQU0sUUFBUSxTQUFTLGNBQWMsS0FBSztBQUMxQyxZQUFNLFlBQVk7QUFDbEIsWUFBTSxjQUFjLFFBQVEsU0FBUztBQUNyQyxXQUFLLFlBQVksS0FBSztBQUN0QixZQUFNLFdBQVcsU0FBUyxjQUFjLFFBQVE7QUFDaEQsZUFBUyxPQUFPO0FBQ2hCLGVBQVMsWUFBWTtBQUNyQixlQUFTLFFBQVE7QUFDakIsZUFBUyxhQUFhLGNBQWMsSUFBSTtBQUN4QyxlQUFTLFlBQVk7QUFDckIsV0FBSyxPQUFPLE1BQU0sUUFBUTtBQUMxQixZQUFNLE9BQU8sU0FBUyxjQUFjLEtBQUs7QUFDekMsV0FBSyxZQUFZO0FBQ2pCLFVBQUksTUFBTSxRQUFRLFFBQVEsT0FBTyxFQUFHLFNBQVEsUUFBUSxRQUFRLENBQUMsTUFBWSxLQUFLLFlBQVksQ0FBQyxDQUFDO0FBQUEsZUFDbkYsUUFBUSxRQUFTLE1BQUssWUFBWSxRQUFRLE9BQU87QUFDMUQsYUFBTyxPQUFPLE1BQU0sSUFBSTtBQUN4QixZQUFNLFlBQVksTUFBTTtBQUN4QixXQUFLLFlBQVksS0FBSztBQUN0QixZQUFNLFFBQVEsTUFBTTtBQUFFLGFBQUssT0FBTztBQUFHLGdCQUFRLFVBQVU7QUFBQSxNQUFFO0FBQ3pELGVBQVMsVUFBVTtBQUNuQixXQUFLLFVBQVUsV0FBUztBQUFFLFlBQUksTUFBTSxXQUFXLFFBQVEsUUFBUSxnQkFBZ0IsTUFBTyxPQUFNO0FBQUEsTUFBRTtBQUM5RixlQUFTLEtBQUssWUFBWSxJQUFJO0FBQzlCLGFBQU8sRUFBRSxJQUFJLE1BQU0sTUFBTSxPQUFPLE1BQU07QUFBQSxJQUN4QztBQUVBLGFBQVMsU0FBUyxVQUFlLENBQUMsR0FBRztBQUNuQyxZQUFNLE9BQU8sU0FBUyxjQUFjLEtBQUs7QUFDekMsV0FBSyxZQUFZO0FBQ2pCLFlBQU0sU0FBUyxTQUFTLGNBQWMsTUFBTTtBQUM1QyxhQUFPLFlBQVk7QUFDbkIsV0FBSyxZQUFZLE1BQU07QUFFdkIsWUFBTSxVQUErQixDQUFDO0FBQ3RDLFlBQU0sY0FBYyxDQUFDLFFBQWEsT0FBTyxLQUFLLFNBQVMsS0FBSyxPQUFPLEVBQUU7QUFDckUsWUFBTSxjQUFjLE1BQU0sUUFBUSxRQUFRLElBQUksSUFBSSxRQUFRLE9BQU8sQ0FBQztBQUNsRSxZQUFNLGVBQWUsT0FBTyxRQUFRLFNBQVMsRUFBRSxLQUFLLFlBQVksWUFBWSxDQUFDLENBQUM7QUFDOUUsY0FBUSxRQUFRO0FBQ2hCLFVBQUksTUFBTTtBQUVWLFlBQU0sVUFBVSxNQUFNO0FBQ3BCLFlBQUksQ0FBQyxLQUFLLFlBQWE7QUFDdkIsY0FBTSxjQUFjLE9BQU8sUUFBUSxTQUFTLEVBQUU7QUFDOUMsZ0JBQVEsUUFBUSxZQUFVLE9BQU8sVUFBVSxPQUFPLGFBQWEsT0FBTyxRQUFRLFVBQVUsV0FBVyxDQUFDO0FBQ3BHLGNBQU0sU0FBUyxRQUFRLEtBQUssT0FBSyxFQUFFLFFBQVEsVUFBVSxXQUFXLEtBQUssUUFBUSxDQUFDO0FBQzlFLFlBQUksQ0FBQyxPQUFRO0FBQ2IsZUFBTyxNQUFNLFFBQVEsR0FBRyxPQUFPLFdBQVc7QUFDMUMsZUFBTyxNQUFNLFlBQVksY0FBYyxPQUFPLFVBQVU7QUFBQSxNQUMxRDtBQUVBLFlBQU0sa0JBQWtCLE1BQU07QUFDNUIsWUFBSSxJQUFLLHNCQUFxQixHQUFHO0FBQ2pDLGNBQU0sc0JBQXNCLE1BQU07QUFBRSxnQkFBTTtBQUFHLGtCQUFRO0FBQUEsUUFBRSxDQUFDO0FBQUEsTUFDMUQ7QUFFQSxpQkFBVyxPQUFPLGFBQWE7QUFDN0IsY0FBTSxRQUFRLFlBQVksR0FBRztBQUM3QixjQUFNLE1BQU0sU0FBUyxjQUFjLFFBQVE7QUFDM0MsWUFBSSxPQUFPO0FBQ1gsWUFBSSxjQUFjLElBQUksU0FBUztBQUMvQixZQUFJLFFBQVEsUUFBUTtBQUNwQixZQUFJLFlBQVk7QUFDaEIsWUFBSSxVQUFVLENBQUMsVUFBVTtBQUN2QixnQkFBTSxlQUFlO0FBQ3JCLGdCQUFNLGdCQUFnQjtBQUN0QixjQUFJLE9BQU8sUUFBUSxTQUFTLEVBQUUsTUFBTSxNQUFPO0FBQzNDLGtCQUFRLFFBQVE7QUFDaEIsa0JBQVE7QUFDUixrQkFBUSxXQUFXLEtBQUs7QUFDeEIsMEJBQWdCO0FBQUEsUUFDbEI7QUFDQSxnQkFBUSxLQUFLLEdBQUc7QUFDaEIsYUFBSyxZQUFZLEdBQUc7QUFBQSxNQUN0QjtBQUVBLHNCQUFnQjtBQUNoQiw0QkFBc0IsTUFBTTtBQUMxQixnQkFBUTtBQUNSLGFBQUssVUFBVSxJQUFJLHlCQUF5QjtBQUFBLE1BQzlDLENBQUM7QUFDRCxhQUFPLGlCQUFpQixVQUFVLGVBQWU7QUFDakQsWUFBTSxXQUFXLENBQUMsVUFBa0I7QUFDbEMsZ0JBQVEsUUFBUSxPQUFPLEtBQUs7QUFDNUIsZ0JBQVE7QUFBQSxNQUNWO0FBQ0EsWUFBTUEsV0FBVSxNQUFNO0FBQ3BCLFlBQUksSUFBSyxzQkFBcUIsR0FBRztBQUNqQyxlQUFPLG9CQUFvQixVQUFVLGVBQWU7QUFBQSxNQUN0RDtBQUNBLFdBQUssVUFBVUE7QUFDZixXQUFLLGdCQUFnQkE7QUFDcEIsTUFBQyxLQUFhLGlCQUFpQjtBQUNoQyxhQUFPO0FBQUEsSUFDVDtBQUVBLGFBQVMsZUFBZSxVQUFlLENBQUMsR0FBRztBQUN6QyxZQUFNLE9BQU8sU0FBUyxjQUFjLEtBQUs7QUFDekMsV0FBSyxZQUFZO0FBQ2pCLFlBQU0sT0FBTyxPQUFPLFFBQVEsUUFBUSxDQUFDO0FBQ3JDLFlBQU0sUUFBUSxLQUFLLElBQUksR0FBRyxPQUFPLFFBQVEsY0FBYyxDQUFDLENBQUM7QUFDekQsWUFBTSxLQUFLLENBQUMsV0FBbUI7QUFDN0IsY0FBTSxPQUFPLEtBQUssSUFBSSxLQUFLLElBQUksR0FBRyxNQUFNLEdBQUcsS0FBSztBQUNoRCxZQUFJLFNBQVMsS0FBTSxTQUFRLFNBQVMsSUFBSTtBQUFBLE1BQzFDO0FBQ0EsWUFBTSxLQUFLLENBQUMsT0FBZSxRQUFnQixXQUFXLE9BQU8sU0FBUyxVQUFVO0FBQzlFLGNBQU0sTUFBTSxTQUFTLGNBQWMsUUFBUTtBQUMzQyxZQUFJLE9BQU87QUFDWCxZQUFJLFlBQVksdUJBQXVCLFNBQVMscUNBQXFDLEVBQUU7QUFDdkYsWUFBSSxjQUFjO0FBQ2xCLFlBQUksV0FBVztBQUNmLFlBQUksVUFBVSxNQUFNLENBQUMsWUFBWSxHQUFHLE1BQU07QUFDMUMsZUFBTztBQUFBLE1BQ1Q7QUFDQSxXQUFLLE9BQU8sR0FBRyxPQUFPLE9BQU8sR0FBRyxRQUFRLENBQUMsQ0FBQztBQUMxQyxZQUFNLGVBQWUsS0FBSyxJQUFJLEdBQUcsT0FBTyxRQUFRLGdCQUFnQixDQUFDLENBQUM7QUFDbEUsWUFBTSxRQUFRLEtBQUssSUFBSSxHQUFHLE9BQU8sWUFBWTtBQUM3QyxZQUFNLE1BQU0sS0FBSyxJQUFJLE9BQU8sT0FBTyxZQUFZO0FBQy9DLGVBQVMsSUFBSSxPQUFPLEtBQUssS0FBSyxJQUFLLE1BQUssT0FBTyxHQUFHLE9BQU8sQ0FBQyxHQUFHLEdBQUcsT0FBTyxNQUFNLElBQUksQ0FBQztBQUNsRixXQUFLLE9BQU8sR0FBRyxPQUFPLE9BQU8sR0FBRyxRQUFRLEtBQUssQ0FBQztBQUM5QyxZQUFNLFlBQVksQ0FBQyxVQUF5QjtBQUMxQyxZQUFJLFFBQVEsYUFBYSxNQUFPO0FBQ2hDLGNBQU0sU0FBUyxNQUFNO0FBQ3JCLFlBQUksVUFBVSxDQUFDLFNBQVMsWUFBWSxRQUFRLEVBQUUsU0FBUyxPQUFPLE9BQU8sRUFBRztBQUN4RSxZQUFJLE1BQU0sUUFBUSxVQUFVO0FBQUUsZ0JBQU0sZUFBZTtBQUFHLGFBQUcsT0FBTyxDQUFDO0FBQUEsUUFBRSxXQUMxRCxNQUFNLFFBQVEsWUFBWTtBQUFFLGdCQUFNLGVBQWU7QUFBRyxhQUFHLE9BQU8sQ0FBQztBQUFBLFFBQUUsV0FDakUsTUFBTSxRQUFRLFFBQVE7QUFBRSxnQkFBTSxlQUFlO0FBQUcsYUFBRyxDQUFDO0FBQUEsUUFBRSxXQUN0RCxNQUFNLFFBQVEsT0FBTztBQUFFLGdCQUFNLGVBQWU7QUFBRyxhQUFHLEtBQUs7QUFBQSxRQUFFO0FBQUEsTUFDcEU7QUFDQSxhQUFPLGlCQUFpQixXQUFXLFNBQVM7QUFDM0MsTUFBQyxLQUFhLGdCQUFnQixNQUFNLE9BQU8sb0JBQW9CLFdBQVcsU0FBUztBQUNwRixhQUFPO0FBQUEsSUFDVDtBQUVBLGFBQVMsaUJBQWlCLFVBQWUsQ0FBQyxHQUFHO0FBQzNDLFlBQU0sTUFBTSxXQUFXLEVBQUUsT0FBTyxJQUFJLE1BQU0sV0FBVyxXQUFXLENBQUMsbUJBQW1CLFFBQVEsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHLEVBQUUsQ0FBQztBQUN4SSxZQUFNLE1BQU0sU0FBUyxjQUFjLEdBQUc7QUFDdEMsVUFBSSxZQUFZO0FBQ2hCLFlBQU0sT0FBTyxTQUFTLGNBQWMsTUFBTTtBQUMxQyxXQUFLLFlBQVk7QUFDakIsVUFBSSxPQUFPLEtBQUssSUFBSTtBQUNwQixZQUFNLFlBQVksQ0FBQyxVQUFrQixVQUFVLGVBQWUsWUFBYSxTQUFTO0FBQ3BGLFlBQU0sV0FBVyxDQUFDLE9BQWUsV0FBVyxHQUFHLFFBQVEsT0FBTztBQUM1RCxZQUFJLE1BQU8sUUFBTztBQUNsQixZQUFJLFVBQVUsVUFBVyxRQUFPLFFBQVEsZ0JBQWdCO0FBQ3hELFlBQUksVUFBVSxRQUFTLFFBQU8sUUFBUSxjQUFjO0FBQ3BELFlBQUksVUFBVSxVQUFXLFFBQU8sUUFBUSxtQkFBbUIsUUFBUSxpQkFBaUIsV0FBVyxJQUFJLEdBQUcsS0FBSyxNQUFNLFFBQVEsQ0FBQyxNQUFNO0FBQ2hJLGVBQU8sUUFBUSxhQUFhLFFBQVEsU0FBUztBQUFBLE1BQy9DO0FBQ0EsWUFBTSxXQUFXLENBQUMsT0FBZSxXQUFXLEdBQUcsUUFBUSxPQUFPO0FBQzVELGNBQU0sT0FBTyxVQUFVLEtBQUs7QUFDNUIsY0FBTSxNQUFNLEtBQUssSUFBSSxHQUFHLEtBQUssSUFBSSxLQUFLLE9BQU8sWUFBWSxDQUFDLENBQUMsQ0FBQztBQUM1RCxZQUFJLFFBQVEsUUFBUTtBQUNwQixZQUFJLFVBQVUsT0FBTyxjQUFjLFNBQVMsU0FBUztBQUNyRCxZQUFJLFVBQVUsT0FBTyxjQUFjLFNBQVMsU0FBUztBQUNyRCxZQUFJLFVBQVUsT0FBTyxZQUFZLFNBQVMsT0FBTztBQUNqRCxZQUFJLE1BQU0sWUFBWSxxQkFBcUIsR0FBRyxHQUFHLEdBQUc7QUFDcEQsYUFBSyxjQUFjLFNBQVMsTUFBTSxLQUFLLEtBQUs7QUFDNUMsWUFBSSxRQUFRLHdCQUF3QixTQUFTLFNBQVMsVUFBVyxLQUFJLFdBQVc7QUFBQSxpQkFDdkUsU0FBUyxhQUFhLFFBQVEscUJBQXFCLE1BQU8sS0FBSSxXQUFXO0FBQUEsWUFDN0UsS0FBSSxXQUFXLENBQUMsQ0FBQyxRQUFRO0FBQUEsTUFDaEM7QUFDQSxVQUFJLFVBQVUsV0FBUztBQUNyQixZQUFJLElBQUksU0FBVTtBQUNsQixnQkFBUSxVQUFVLEtBQUs7QUFBQSxNQUN6QjtBQUNDLE1BQUMsSUFBWSxhQUFhO0FBQzNCLGVBQVMsUUFBUSxVQUFVLFFBQVEsT0FBTyxRQUFRLFlBQVksQ0FBQyxHQUFHLFFBQVEsaUJBQWlCLEVBQUU7QUFDN0YsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLGVBQWUsUUFBcUIsVUFBZ0I7QUFDM0QsVUFBSSxDQUFDLFNBQVUsUUFBTztBQUN0QixZQUFNLE9BQU8sTUFBTSxRQUFRLFFBQVEsSUFBSSxXQUFXLENBQUMsUUFBUTtBQUMzRCxpQkFBVyxTQUFTLE1BQU07QUFDeEIsWUFBSSxDQUFDLE1BQU87QUFDWixZQUFJLGlCQUFpQixLQUFNLFFBQU8sWUFBWSxLQUFLO0FBQUEsWUFDOUMsUUFBTyxZQUFZLFNBQVMsZUFBZSxPQUFPLEtBQUssQ0FBQyxDQUFDO0FBQUEsTUFDaEU7QUFDQSxhQUFPO0FBQUEsSUFDVDtBQUVBLGFBQVMsV0FBVyxVQUFlLENBQUMsR0FBRztBQUNyQyxZQUFNLE1BQU0sU0FBUyxjQUFjLEtBQUs7QUFDeEMsVUFBSSxZQUFZLENBQUMsc0JBQXNCLFFBQVEsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQ3hGLFlBQU0sT0FBTyxTQUFTLGNBQWMsS0FBSztBQUN6QyxXQUFLLFlBQVk7QUFDakIsWUFBTSxVQUFVLFNBQVMsY0FBYyxLQUFLO0FBQzVDLGNBQVEsWUFBWTtBQUNwQixxQkFBZSxNQUFNLFFBQVEsUUFBUSxRQUFRLElBQUk7QUFDakQscUJBQWUsU0FBUyxRQUFRLFdBQVcsUUFBUSxLQUFLO0FBQ3hELFVBQUksT0FBTyxNQUFNLE9BQU87QUFDeEIsYUFBTyxFQUFFLElBQUksS0FBSyxNQUFNLFFBQVE7QUFBQSxJQUNsQztBQUVBLGFBQVMsY0FBYyxVQUFlLENBQUMsR0FBRztBQUN4QyxZQUFNLE1BQU0sU0FBUyxjQUFjLEtBQUs7QUFDeEMsVUFBSSxZQUFZLENBQUMsMEJBQTBCLFFBQVEsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQzVGLHFCQUFlLEtBQUssUUFBUSxZQUFZLFFBQVEsS0FBSztBQUNyRCxhQUFPO0FBQUEsSUFDVDtBQUVBLGFBQVMsYUFBYSxVQUFlLENBQUMsR0FBRztBQUN2QyxZQUFNLE9BQU8sU0FBUyxjQUFjLFFBQVEsVUFBVSxXQUFXLEtBQUs7QUFDdEUsV0FBSyxZQUFZLENBQUMseUJBQXlCLFFBQVEsT0FBTywwQkFBMEIsUUFBUSxJQUFJLEtBQUssSUFBSSxRQUFRLGFBQWEsRUFBRSxFQUFFLE9BQU8sT0FBTyxFQUFFLEtBQUssR0FBRztBQUMxSixVQUFJLFFBQVEsU0FBUztBQUNuQjtBQUFDLFFBQUMsS0FBMkIsT0FBTztBQUNuQyxRQUFDLEtBQTJCLFVBQVUsUUFBUTtBQUFBLE1BQ2pEO0FBQ0EsWUFBTSxRQUFRLFNBQVMsY0FBYyxNQUFNO0FBQzNDLFlBQU0sWUFBWTtBQUNsQixZQUFNLGNBQWMsUUFBUSxTQUFTO0FBQ3JDLFlBQU0sUUFBUSxTQUFTLGNBQWMsUUFBUTtBQUM3QyxZQUFNLFlBQVk7QUFDbEIsWUFBTSxjQUFjLE9BQU8sUUFBUSxTQUFTLEdBQUc7QUFDL0MsV0FBSyxPQUFPLE9BQU8sS0FBSztBQUN4QixVQUFJLFFBQVEsTUFBTTtBQUNoQixjQUFNLE9BQU8sU0FBUyxjQUFjLE9BQU87QUFDM0MsYUFBSyxZQUFZO0FBQ2pCLGFBQUssY0FBYyxPQUFPLFFBQVEsSUFBSTtBQUN0QyxhQUFLLFlBQVksSUFBSTtBQUFBLE1BQ3ZCO0FBQ0EsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLGFBQWEsVUFBZSxDQUFDLEdBQUc7QUFDdkMsWUFBTSxPQUFPLFNBQVMsY0FBYyxLQUFLO0FBQ3pDLFdBQUssWUFBWSxDQUFDLHlCQUF5QixRQUFRLGFBQWEsRUFBRSxFQUFFLE9BQU8sT0FBTyxFQUFFLEtBQUssR0FBRztBQUM1RixZQUFNLFFBQVEsTUFBTSxRQUFRLFFBQVEsS0FBSyxJQUFJLFFBQVEsUUFBUSxDQUFDO0FBQzlELGlCQUFXLFFBQVEsTUFBTyxNQUFLLFlBQVksYUFBYSxJQUFJLENBQUM7QUFDN0QsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLGNBQWMsVUFBZSxDQUFDLEdBQUc7QUFDeEMsWUFBTSxPQUFPLFNBQVMsY0FBYyxRQUFRLFVBQVUsV0FBVyxRQUFRLE9BQU8sTUFBTSxLQUFLO0FBQzNGLFdBQUssWUFBWSxDQUFDLDBCQUEwQixRQUFRLFFBQVEsa0NBQWtDLElBQUksUUFBUSxhQUFhLEVBQUUsRUFBRSxPQUFPLE9BQU8sRUFBRSxLQUFLLEdBQUc7QUFDbkosVUFBSSxRQUFRLE1BQU07QUFDaEI7QUFBQyxRQUFDLEtBQTJCLE9BQU8sUUFBUTtBQUMzQyxRQUFDLEtBQTJCLFNBQVMsUUFBUSxVQUFVO0FBQUEsTUFDMUQ7QUFDQSxVQUFJLFFBQVEsU0FBUztBQUNuQjtBQUFDLFFBQUMsS0FBMkIsT0FBTztBQUNuQyxRQUFDLEtBQTJCLFVBQVUsUUFBUTtBQUFBLE1BQ2pEO0FBQ0EsWUFBTSxRQUFRLFNBQVMsY0FBYyxLQUFLO0FBQzFDLFlBQU0sWUFBWSxDQUFDLGlDQUFpQyxRQUFRLGVBQWUsaUJBQWlCLEVBQUUsRUFBRSxPQUFPLE9BQU8sRUFBRSxLQUFLLEdBQUc7QUFDeEgsVUFBSSxRQUFRLGFBQWMsT0FBTSxVQUFVLENBQUMsTUFBTTtBQUFFLFVBQUUsZ0JBQWdCO0FBQUcsZ0JBQVEsYUFBYTtBQUFBLE1BQUU7QUFDL0YsVUFBSSxRQUFRLFNBQVMsUUFBUSxTQUFTLFFBQVEsVUFBVTtBQUN0RCxjQUFNLE1BQU0sU0FBUyxjQUFjLEtBQUs7QUFDeEMsWUFBSSxNQUFNLFFBQVEsU0FBUyxRQUFRLFNBQVMsUUFBUTtBQUNwRCxZQUFJLFVBQVUsUUFBUSxXQUFXO0FBQ2pDLGNBQU0sWUFBWSxHQUFHO0FBQUEsTUFDdkIsT0FBTztBQUNMLGNBQU0sS0FBSyxTQUFTLGNBQWMsS0FBSztBQUN2QyxXQUFHLFlBQVk7QUFDZixXQUFHLGNBQWMsUUFBUSxlQUFlO0FBQ3hDLGNBQU0sWUFBWSxFQUFFO0FBQUEsTUFDdEI7QUFDQSxZQUFNLE9BQU8sU0FBUyxjQUFjLEtBQUs7QUFDekMsV0FBSyxZQUFZO0FBQ2pCLFlBQU0sUUFBUSxTQUFTLGNBQWMsS0FBSztBQUMxQyxZQUFNLFlBQVksQ0FBQyxpQ0FBaUMsUUFBUSxlQUFlLGlCQUFpQixFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQ3hILFlBQU0sY0FBYyxRQUFRLFNBQVM7QUFDckMsVUFBSSxRQUFRLGFBQWMsT0FBTSxVQUFVLENBQUMsTUFBTTtBQUFFLFVBQUUsZ0JBQWdCO0FBQUcsZ0JBQVEsYUFBYTtBQUFBLE1BQUU7QUFDL0YsV0FBSyxZQUFZLEtBQUs7QUFDdEIsVUFBSSxRQUFRLE1BQU07QUFDaEIsY0FBTSxPQUFPLFNBQVMsY0FBYyxLQUFLO0FBQ3pDLGFBQUssWUFBWTtBQUNqQixjQUFNLFlBQVksTUFBTSxRQUFRLFFBQVEsSUFBSSxJQUFJLFFBQVEsT0FBTyxDQUFDLFFBQVEsSUFBSTtBQUM1RSxtQkFBVyxRQUFRLFVBQVUsT0FBTyxPQUFPLEdBQUc7QUFDNUMsZ0JBQU0sT0FBTyxTQUFTLGNBQWMsTUFBTTtBQUMxQyxlQUFLLGNBQWMsT0FBTyxJQUFJO0FBQzlCLGVBQUssWUFBWSxJQUFJO0FBQUEsUUFDdkI7QUFDQSxhQUFLLFlBQVksSUFBSTtBQUFBLE1BQ3ZCO0FBQ0EsVUFBSSxRQUFRLFFBQVE7QUFDbEIsY0FBTSxTQUFTLFNBQVMsY0FBYyxLQUFLO0FBQzNDLGVBQU8sWUFBWTtBQUNuQix1QkFBZSxRQUFRLFFBQVEsTUFBTTtBQUNyQyxhQUFLLFlBQVksTUFBTTtBQUFBLE1BQ3pCO0FBQ0EsVUFBSSxRQUFRLFNBQVM7QUFDbkIsY0FBTSxVQUFVLFNBQVMsY0FBYyxLQUFLO0FBQzVDLGdCQUFRLFlBQVk7QUFDcEIsdUJBQWUsU0FBUyxRQUFRLE9BQU87QUFDdkMsYUFBSyxZQUFZLE9BQU87QUFBQSxNQUMxQjtBQUNBLFdBQUssT0FBTyxPQUFPLElBQUk7QUFDdkIsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLGlCQUFpQixVQUFlLENBQUMsR0FBRztBQUMzQyxZQUFNLElBQUksU0FBUyxjQUFjLEtBQUs7QUFDdEMsUUFBRSxZQUFZLENBQUMscUJBQXFCLDhCQUE4QixRQUFRLGFBQWEsRUFBRSxFQUFFLE9BQU8sT0FBTyxFQUFFLEtBQUssR0FBRztBQUNuSCxZQUFNLFVBQVUsU0FBUyxjQUFjLE1BQU07QUFDN0MsY0FBUSxZQUFZO0FBQ3BCLFlBQU0sT0FBTyxTQUFTLGNBQWMsTUFBTTtBQUMxQyxXQUFLLGNBQWMsUUFBUSxRQUFRO0FBQ25DLFFBQUUsT0FBTyxTQUFTLElBQUk7QUFDdEIsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLGdCQUFnQixjQUFzQjtBQUM3QyxhQUFPLCtCQUErQixnQkFBZ0IsU0FBUztBQUFBLElBQ2pFO0FBRUEsYUFBUyxpQkFBaUIsY0FBc0I7QUFDOUMsVUFBSTtBQUFFLGVBQU8sYUFBYSxRQUFRLGdCQUFnQixZQUFZLENBQUMsS0FBSztBQUFBLE1BQUcsUUFBUTtBQUFFLGVBQU87QUFBQSxNQUFHO0FBQUEsSUFDN0Y7QUFFQSxhQUFTLGtCQUFrQixjQUFzQixPQUFlO0FBQzlELFVBQUk7QUFDRixZQUFJLE1BQU8sY0FBYSxRQUFRLGdCQUFnQixZQUFZLEdBQUcsS0FBSztBQUFBLE1BQ3RFLFFBQVE7QUFBQSxNQUFDO0FBQUEsSUFDWDtBQUVBLGFBQVMsV0FBVyxPQUFZO0FBQzlCLGFBQU8sT0FBTyxTQUFTLEVBQUUsRUFBRSxRQUFRLFlBQVksUUFBTSxFQUFFLEtBQUssU0FBUyxLQUFLLFFBQVEsS0FBSyxRQUFRLEtBQUssU0FBUyxLQUFLLFNBQVMsR0FBRSxDQUFDLENBQUc7QUFBQSxJQUNuSTtBQUVBLGFBQVMsc0JBQXNCLGVBQW9CO0FBQ2pELFlBQU0sSUFBSSxTQUFTLGNBQWMsS0FBSztBQUN0QyxRQUFFLFlBQVk7QUFDZCxVQUFJLENBQUMsY0FBYyxTQUFTLDBCQUEyQixRQUFPO0FBQzlELFVBQUksY0FBYyxTQUFTO0FBQ3pCLFVBQUUsWUFBWTtBQUNkLGVBQU87QUFBQSxNQUNUO0FBQ0EsVUFBSSxjQUFjLE9BQU87QUFDdkIsVUFBRSxZQUFZLG9GQUFvRixXQUFXLGNBQWMsS0FBSyxDQUFDO0FBQ2pJLGVBQU87QUFBQSxNQUNUO0FBQ0EsWUFBTSxRQUFRLE1BQU0sUUFBUSxjQUFjLE1BQU0sS0FBSyxJQUFJLGNBQWMsS0FBSyxRQUFRLENBQUM7QUFDckYsVUFBSSxDQUFDLE1BQU0sUUFBUTtBQUNqQixVQUFFLFlBQVk7QUFDZCxlQUFPO0FBQUEsTUFDVDtBQUNBLFlBQU0sVUFBVSxNQUFNLE1BQU0sR0FBRyxDQUFDO0FBQ2hDLFFBQUUsWUFBWSxtRUFBbUUsV0FBVyxjQUFjLE1BQU0sd0JBQXdCLEVBQUUsQ0FBQyxNQUFNLE1BQU0sTUFBTTtBQUFBLGdEQUMvRyxRQUFRLElBQUksQ0FBQyxTQUFjLG9EQUFvRCxXQUFXLEtBQUssUUFBUSxLQUFLLGFBQWEsRUFBRSxDQUFDLGNBQWMsV0FBVyxLQUFLLGtCQUFrQixFQUFFLENBQUMsYUFBYSxFQUFFLEtBQUssRUFBRSxDQUFDLEdBQUcsTUFBTSxTQUFTLFFBQVEsU0FBUyxpREFBaUQsTUFBTSxTQUFTLFFBQVEsTUFBTSxlQUFlLEVBQUU7QUFDdFgsYUFBTztBQUFBLElBQ1Q7QUFFQSxhQUFTLDhCQUE4QixnQkFBd0I7QUFDN0QsVUFBSSxnQkFBK0I7QUFFbkMscUJBQWUsU0FBUyxLQUFhLFNBQWM7QUFDakQsY0FBTSxNQUFNLE1BQU0sTUFBTSxLQUFLO0FBQUEsVUFDM0IsUUFBUTtBQUFBLFVBQ1IsU0FBUyxFQUFFLGdCQUFnQixtQkFBbUI7QUFBQSxVQUM5QyxNQUFNLEtBQUssVUFBVSxFQUFFLFFBQVEsQ0FBQztBQUFBLFFBQ2xDLENBQUM7QUFDRCxjQUFNLE9BQU8sTUFBTSxJQUFJLEtBQUssRUFBRSxNQUFNLE9BQU8sQ0FBQyxFQUFFO0FBQzlDLFlBQUksQ0FBQyxJQUFJLE1BQU0sTUFBTSxPQUFPLE1BQU8sT0FBTSxJQUFJLE1BQU0sTUFBTSxVQUFVLE1BQU0sV0FBVyxNQUFNO0FBQzFGLGVBQU87QUFBQSxNQUNUO0FBRUEscUJBQWUsS0FBSyxVQUFlLENBQUMsR0FBRztBQUNyQyxjQUFNLGlCQUFpQixDQUFDLENBQUMsUUFBUTtBQUNqQyxjQUFNLHNCQUFzQixRQUFRLHdCQUF3QjtBQUM1RCxjQUFNLGlCQUFpQixRQUFRLFlBQVk7QUFDM0MsY0FBTSxVQUFVLE9BQU8sUUFBUSxXQUFXLENBQUM7QUFDM0MsY0FBTSxrQkFBa0IsT0FBTyxRQUFRLG9CQUFvQixpQkFBaUIsU0FBUyxPQUFPO0FBQzVGLGNBQU0scUJBQXFCLE9BQU8sUUFBUSx1QkFBdUIsaUJBQWlCLFNBQVMsT0FBTztBQUNsRyxjQUFNLG1CQUFtQixPQUFPLFFBQVEscUJBQXFCLGlCQUFpQixTQUFTLE9BQU87QUFDOUYsY0FBTSxxQkFBcUIsT0FBTyxRQUFRLHNCQUFzQixNQUFNO0FBQ3RFLGNBQU0sUUFBYTtBQUFBLFVBQ2pCLGNBQWMsT0FBTyxRQUFRLGdCQUFnQixFQUFFLEVBQUUsS0FBSztBQUFBLFVBQ3RELE9BQU8sT0FBTyxRQUFRLFNBQVMsRUFBRTtBQUFBLFVBQ2pDLE1BQU0sT0FBTyxRQUFRLFFBQVEsUUFBUSxVQUFVLFFBQVEsU0FBUyxFQUFFO0FBQUEsVUFDbEUsUUFBUSxPQUFPLFFBQVEsVUFBVSxRQUFRLFFBQVEsUUFBUSxTQUFTLEVBQUU7QUFBQSxVQUNwRSxjQUFjLE1BQU0sUUFBUSxRQUFRLFlBQVksSUFBSSxRQUFRLGFBQWEsT0FBTyxPQUFPLElBQUksQ0FBQztBQUFBLFVBQzVGLFdBQVcsT0FBTyxRQUFRLGFBQWEsRUFBRTtBQUFBLFVBQ3pDLEtBQUssT0FBTyxRQUFRLE9BQU8sUUFBUSxVQUFVLFFBQVEsUUFBUSxFQUFFO0FBQUEsVUFDL0QsVUFBVSxPQUFPLFFBQVEsWUFBWSxRQUFRLFFBQVEsUUFBUSxPQUFPLFFBQVEsVUFBVSxFQUFFO0FBQUEsVUFDeEYsV0FBVyxPQUFPLFFBQVEsYUFBYSxRQUFRLFNBQVMsRUFBRTtBQUFBLFVBQzFELGFBQWE7QUFBQSxVQUNiLFVBQVU7QUFBQSxVQUNWLGNBQWM7QUFBQSxVQUNkLFVBQVU7QUFBQSxVQUNWLGVBQWU7QUFBQSxVQUNmLFNBQVM7QUFBQSxVQUNULE9BQU87QUFBQSxVQUNQLFNBQVM7QUFBQSxVQUNULGdCQUFnQjtBQUFBLFVBQ2hCLGNBQWM7QUFBQSxVQUNkLGFBQWE7QUFBQSxVQUNiLGNBQWM7QUFBQSxVQUNkLGdCQUFnQjtBQUFBLFVBQ2hCLFlBQVk7QUFBQSxVQUNaLGNBQWM7QUFBQSxRQUNoQjtBQUVBLFlBQUksQ0FBQyxNQUFNLGFBQWMsT0FBTSxJQUFJLE1BQU0sUUFBUTtBQUNqRCxZQUFJLENBQUMsa0JBQWtCLENBQUMsTUFBTSxJQUFLLE9BQU0sSUFBSSxNQUFNLFFBQVE7QUFDM0QsWUFBSSxDQUFDLE1BQU0sYUFBYSxNQUFNLGFBQWEsT0FBUSxPQUFNLFlBQVksT0FBTyxNQUFNLGFBQWEsQ0FBQyxHQUFHLE9BQU8sRUFBRTtBQUU1RyxjQUFNLFFBQVEsVUFBVTtBQUFBLFVBQ3RCLE9BQU8sT0FBTyxRQUFRLGVBQWUsaUJBQWlCLFdBQVcsT0FBTztBQUFBLFVBQ3hFLE9BQU87QUFBQSxVQUNQLGFBQWE7QUFBQSxVQUNiLFNBQVMsTUFBTTtBQUNiLGdCQUFJLE1BQU0sV0FBWTtBQUN0QixnQkFBSSxjQUFlLFFBQU8sY0FBYyxhQUFhO0FBQUEsVUFDdkQ7QUFBQSxRQUNGLENBQUM7QUFFRCx1QkFBZSxjQUFjO0FBQzNCLGdCQUFNLFVBQVU7QUFDaEIsZ0JBQU0sUUFBUTtBQUNkLGlCQUFPO0FBQ1AsY0FBSTtBQUNGLGtCQUFNLFVBQVUsTUFBTSxJQUFJLElBQUksWUFBWSxNQUFNLFlBQVksU0FBUyxFQUFFLEtBQUssT0FBSyxFQUFFLElBQUksRUFBRSxNQUFNLE1BQU0sSUFBSTtBQUN6RyxrQkFBTSxZQUFZLE1BQU0sU0FBUyxnQkFBZ0IsTUFBTSxZQUFZLDZCQUE2QixDQUFDLENBQUM7QUFDbEcsa0JBQU0sVUFBVTtBQUNoQixrQkFBTSxpQkFBaUIsU0FBUyxRQUFRLFFBQVEsVUFBVSxjQUFjLE1BQU07QUFDOUUsa0JBQU0sY0FBYyxPQUFPLFVBQVUsZ0JBQWdCLE1BQU0sZUFBZSxNQUFNO0FBQ2hGLGtCQUFNLFdBQVcsT0FBTyxVQUFVLG9CQUFvQixFQUFFO0FBQ3hELGtCQUFNLFdBQVcsaUJBQWlCLE1BQU0sWUFBWSxLQUFLLE9BQU8sVUFBVSxvQkFBb0IsRUFBRTtBQUNoRyxrQkFBTSxlQUFlLE1BQU07QUFDM0IsZ0JBQUksVUFBVSxxQkFBcUIsT0FBTyxVQUFVLHNCQUFzQixVQUFVO0FBQ2xGLG9CQUFNLE1BQU0sVUFBVSxrQkFBa0I7QUFDeEMsb0JBQU0sZ0JBQWdCLFFBQVEsVUFBYSxRQUFRLFFBQVEsUUFBUSxLQUFLLEtBQUssT0FBTyxHQUFHO0FBQUEsWUFDekY7QUFDQSxrQkFBTSxTQUFTLFVBQVUsY0FBYyxDQUFDLEdBQUcsS0FBSyxDQUFDLFNBQWMsS0FBSyxTQUFTLE1BQU0sUUFBUTtBQUMzRixnQkFBSSxPQUFPLGFBQWEsQ0FBQyxNQUFNLFNBQVUsT0FBTSxXQUFXLE9BQU8sTUFBTSxTQUFTO0FBQ2hGLGdCQUFJLENBQUMsTUFBTSxVQUFVO0FBQ25CLG9CQUFNLFlBQVksTUFBTSxRQUFRLFVBQVUsS0FBSyxJQUFJLFVBQVUsTUFBTSxLQUFLLENBQUMsU0FBYyxNQUFNLElBQUksR0FBRyxPQUFPO0FBQzNHLGtCQUFJLFdBQVc7QUFDYixzQkFBTSxXQUFXLE9BQU8sU0FBUztBQUNqQyxzQkFBTSxlQUFlLE1BQU07QUFBQSxjQUM3QjtBQUFBLFlBQ0Y7QUFDQSxnQkFBSSxrQkFBa0IsVUFBVSw2QkFBNkIsQ0FBQyxrQkFBa0IsTUFBTSxJQUFLLE9BQU0sWUFBWTtBQUFBLFVBQy9HLFNBQVMsR0FBUTtBQUNmLGtCQUFNLFFBQVEsR0FBRyxXQUFXO0FBQzVCLGtCQUFNLFVBQVUsRUFBRSxZQUFZLENBQUMsRUFBRTtBQUFBLFVBQ25DLFVBQUU7QUFDQSxrQkFBTSxVQUFVO0FBQ2hCLG1CQUFPO0FBQUEsVUFDVDtBQUFBLFFBQ0Y7QUFFQSx1QkFBZSxjQUFjO0FBQzNCLGNBQUksQ0FBQyxNQUFNLFNBQVMsMEJBQTJCO0FBQy9DLGdCQUFNLGlCQUFpQjtBQUN2QixnQkFBTSxlQUFlO0FBQ3JCLGdCQUFNLGNBQWM7QUFDcEIsaUJBQU87QUFDUCxjQUFJO0FBQ0Ysa0JBQU0sYUFBYSxPQUFPLE1BQU0sT0FBTyxNQUFNLFlBQVksRUFBRSxFQUFFLE1BQU0sT0FBTyxFQUFFLElBQUksQ0FBQyxTQUFpQixLQUFLLEtBQUssQ0FBQyxFQUFFLE9BQU8sT0FBTyxFQUFFLENBQUMsS0FBSztBQUNySSxnQkFBSSxDQUFDLFdBQVk7QUFDakIsa0JBQU0sY0FBYyxNQUFNLFNBQVMsZ0JBQWdCLE1BQU0sWUFBWSwwQkFBMEIsRUFBRSxLQUFLLFlBQVksUUFBUSxXQUFXLENBQUM7QUFBQSxVQUN4SSxTQUFTLEdBQVE7QUFDZixrQkFBTSxlQUFlLEdBQUcsV0FBVztBQUFBLFVBQ3JDLFVBQUU7QUFDQSxrQkFBTSxpQkFBaUI7QUFDdkIsbUJBQU87QUFBQSxVQUNUO0FBQUEsUUFDRjtBQUVBLHVCQUFlLFNBQVM7QUFDdEIsY0FBSSxNQUFNLFdBQVk7QUFDdEIsZ0JBQU0sYUFBYTtBQUNuQixnQkFBTSxlQUFlO0FBQ3JCLGdCQUFNLGlCQUFpQjtBQUN2QixnQkFBTSxRQUFRO0FBQ2QsZ0JBQU0sY0FBYyxhQUFhLFdBQVcsR0FBRyxJQUFJO0FBQ25ELGlCQUFPO0FBQ1AsMEJBQWdCLE9BQU8sWUFBWSxNQUFNO0FBQ3ZDLGdCQUFJLENBQUMsTUFBTSxjQUFjLE1BQU0saUJBQWlCLFVBQVc7QUFDM0Qsa0JBQU0saUJBQWlCLEtBQUssSUFBSSxJQUFJLE9BQU8sTUFBTSxrQkFBa0IsQ0FBQyxJQUFJLENBQUM7QUFDekUsa0JBQU0sY0FBYyxhQUFhLFdBQVcsTUFBTSxnQkFBZ0IsR0FBRyxLQUFLLE1BQU0sTUFBTSxjQUFjLENBQUMsR0FBRztBQUFBLFVBQzFHLEdBQUcsR0FBRztBQUNOLGNBQUk7QUFDRixrQkFBTSxVQUFVLE9BQU8saUJBQWlCLE1BQU0sV0FBWSxNQUFNLE9BQU8sTUFBTSxZQUFZLEVBQUcsRUFDekYsTUFBTSxPQUFPLEVBQ2IsSUFBSSxDQUFDLFNBQWlCLEtBQUssS0FBSyxDQUFDLEVBQ2pDLE9BQU8sT0FBTztBQUNqQixnQkFBSSxDQUFDLFFBQVEsT0FBUSxPQUFNLElBQUksTUFBTSxTQUFTO0FBQzlDLGdCQUFJLFVBQVUsS0FBSyxRQUFRLFNBQVMsUUFBUyxPQUFNLElBQUksTUFBTSxVQUFVLE9BQU8sTUFBTTtBQUNwRixrQkFBTSxXQUFXLFFBQVEsQ0FBQyxLQUFLO0FBQy9CLGtCQUFNLFVBQVU7QUFBQSxjQUNkLEtBQUs7QUFBQSxjQUNMLE1BQU0saUJBQWlCLFFBQVEsS0FBSyxJQUFJLElBQUk7QUFBQSxjQUM1QyxRQUFRO0FBQUEsY0FDUixPQUFPLE1BQU07QUFBQSxjQUNiLE1BQU0sTUFBTTtBQUFBLGNBQ1osUUFBUSxNQUFNLFNBQVMsa0JBQWtCLE1BQU0sU0FBUztBQUFBLGNBQ3hELFVBQVUsTUFBTSxTQUFTLG9CQUFvQixNQUFNLFdBQVc7QUFBQSxjQUM5RCxVQUFVLE1BQU0sU0FBUyxzQkFBc0IsTUFBTSxXQUFXO0FBQUEsY0FDaEUsY0FBYyxNQUFNLFNBQVMsd0JBQXdCLE1BQU0sY0FBYztBQUFBLGNBQ3pFLGtCQUFrQixNQUFNLFNBQVMsNkJBQTZCLE1BQU0sZ0JBQWdCO0FBQUEsY0FDcEYsZUFBZTtBQUFBLFlBQ2pCO0FBQ0Esa0JBQU0sU0FBUyxNQUFNLFNBQVMsZ0JBQWdCLE1BQU0sWUFBWSxjQUFjLE9BQU87QUFDckYsOEJBQWtCLE1BQU0sY0FBYyxNQUFNLFlBQVksRUFBRTtBQUMxRCxrQkFBTSxpQkFBaUIsT0FBTyxRQUFRLGlCQUFpQixDQUFDLElBQUk7QUFDNUQsa0JBQU0sZUFBZSxpQkFBaUIsVUFBVTtBQUNoRCxrQkFBTSxpQkFBaUI7QUFDdkIsZ0JBQUksZ0JBQWdCO0FBQ2xCLG9CQUFNLFFBQVEsT0FBTyxRQUFRLFdBQVcsR0FBRyxRQUFRLGlCQUFpQixDQUFDLFFBQVE7QUFDN0Usb0JBQU0sY0FBYyxhQUFhLFNBQVMsS0FBSyxrQkFBa0I7QUFBQSxZQUNuRSxPQUFPO0FBQ0wsb0JBQU0sY0FBYyxhQUFhLFdBQVcsS0FBSyxrQkFBa0I7QUFBQSxZQUNyRTtBQUNBLG1CQUFPO0FBQ1AsbUJBQU87QUFBQSxVQUNULFNBQVMsR0FBUTtBQUNmLGtCQUFNLFFBQVEsR0FBRyxXQUFXO0FBQzVCLGtCQUFNLGVBQWU7QUFDckIsa0JBQU0saUJBQWlCO0FBQ3ZCLGtCQUFNLGNBQWMsYUFBYSxTQUFTLEtBQUssTUFBTTtBQUNyRCxtQkFBTztBQUNQLGtCQUFNO0FBQUEsVUFDUixVQUFFO0FBQ0Esa0JBQU0sYUFBYTtBQUNuQixnQkFBSSxlQUFlO0FBQ2pCLHFCQUFPLGNBQWMsYUFBYTtBQUNsQyw4QkFBZ0I7QUFBQSxZQUNsQjtBQUFBLFVBQ0Y7QUFBQSxRQUNGO0FBRUEsaUJBQVMsU0FBUztBQUNoQixnQkFBTSxPQUFPLE1BQU07QUFDbkIsZUFBSyxZQUFZO0FBQ2pCLGNBQUksTUFBTSxNQUFPLE1BQUssWUFBWSxPQUFPLE9BQU8sU0FBUyxjQUFjLEtBQUssR0FBRyxFQUFFLFdBQVcsZ0RBQWdELGFBQWEsTUFBTSxNQUFNLENBQUMsQ0FBQztBQUN2SyxnQkFBTSxPQUFPLFNBQVMsY0FBYyxLQUFLO0FBQ3pDLGVBQUssWUFBWTtBQUVqQixjQUFJLHFCQUFxQjtBQUN2QixrQkFBTSxrQkFBa0IsVUFBVSxFQUFFLE9BQU8sTUFBTSxrQkFBa0IsTUFBTSxjQUFjLFVBQVUsS0FBSyxDQUFDO0FBQ3ZHLGlCQUFLLFlBQVksVUFBVSxFQUFFLE9BQU8sT0FBTyxTQUFTLGdCQUFnQixDQUFDLENBQUM7QUFBQSxVQUN4RTtBQUVBLGNBQUksZ0JBQWdCO0FBQ2xCLGtCQUFNLFlBQVksU0FBUyxjQUFjLFVBQVU7QUFDbkQsc0JBQVUsWUFBWTtBQUN0QixzQkFBVSxPQUFPLE9BQU8sUUFBUSxXQUFXLENBQUM7QUFDNUMsc0JBQVUsY0FBYyxPQUFPLFFBQVEsa0JBQWtCLCtCQUErQjtBQUN4RixzQkFBVSxRQUFRLE1BQU07QUFDeEIsc0JBQVUsVUFBVSxNQUFNO0FBQUUsb0JBQU0sV0FBVyxVQUFVO0FBQUEsWUFBTTtBQUM3RCxpQkFBSyxZQUFZLFVBQVU7QUFBQSxjQUN6QixPQUFPLFFBQVEsWUFBWTtBQUFBLGNBQzNCLE1BQU0sVUFBVSxJQUFJLGtCQUFrQixPQUFPLFFBQVE7QUFBQSxjQUNyRCxTQUFTO0FBQUEsWUFDWCxDQUFDLENBQUM7QUFBQSxVQUNKO0FBRUEsZ0JBQU0sYUFBYSxNQUFNLFFBQVEsTUFBTSxTQUFTLFVBQVUsSUFBSSxNQUFNLFFBQVEsYUFBYSxDQUFDO0FBQzFGLGNBQUksTUFBTSxTQUFTLHFCQUFxQjtBQUN0QyxrQkFBTSxpQkFBaUIsV0FBVztBQUFBLGNBQ2hDLE9BQU8sTUFBTTtBQUFBLGNBQ2IsU0FBUyxDQUFDLEVBQUUsT0FBTyxJQUFJLE9BQU8sVUFBVSxDQUFDLEVBQUUsT0FBTyxXQUFXLElBQUksQ0FBQyxVQUFlLEVBQUUsT0FBTyxLQUFLLE1BQU0sT0FBTyxHQUFHLEtBQUssSUFBSSxHQUFHLEtBQUssWUFBWSxNQUFNLEtBQUssU0FBUyxLQUFLLEVBQUUsR0FBRyxFQUFFLENBQUM7QUFBQSxjQUM3SyxVQUFVLENBQUMsVUFBa0I7QUFDM0Isc0JBQU0sV0FBVztBQUNqQixzQkFBTSxRQUFRLFdBQVcsS0FBSyxDQUFDLFNBQWMsS0FBSyxTQUFTLEtBQUs7QUFDaEUsb0JBQUksT0FBTyxVQUFXLE9BQU0sV0FBVyxPQUFPLE1BQU0sU0FBUztBQUM3RCx1QkFBTztBQUFBLGNBQ1Q7QUFBQSxZQUNGLENBQUM7QUFDRCxpQkFBSyxZQUFZLFVBQVUsRUFBRSxPQUFPLGFBQWEsU0FBUyxlQUFlLENBQUMsQ0FBQztBQUFBLFVBQzdFO0FBRUEsZ0JBQU0sUUFBUSxNQUFNLFFBQVEsTUFBTSxTQUFTLEtBQUssSUFBSSxNQUFNLFFBQVEsTUFBTSxPQUFPLENBQUMsU0FBYyxNQUFNLElBQUksSUFBSSxDQUFDO0FBQzdHLGNBQUksTUFBTSxTQUFTLHFCQUFxQixNQUFNLFFBQVE7QUFDcEQsa0JBQU0sYUFBYSxXQUFXO0FBQUEsY0FDNUIsT0FBTyxNQUFNLGdCQUFnQixNQUFNO0FBQUEsY0FDbkMsU0FBUyxDQUFDLEVBQUUsT0FBTyxJQUFJLE9BQU8sU0FBUyxDQUFDLEVBQUUsT0FBTyxNQUFNLElBQUksQ0FBQyxVQUFlO0FBQUEsZ0JBQ3pFLE9BQU8sT0FBTyxLQUFLLFFBQVEsRUFBRTtBQUFBLGdCQUM3QixPQUFPLE9BQU8sS0FBSyxRQUFRLEtBQUssUUFBUSxFQUFFO0FBQUEsY0FDNUMsRUFBRSxDQUFDO0FBQUEsY0FDSCxVQUFVLENBQUMsVUFBa0I7QUFDM0Isc0JBQU0sZUFBZTtBQUNyQixvQkFBSSxNQUFPLE9BQU0sV0FBVztBQUM1Qix1QkFBTztBQUFBLGNBQ1Q7QUFBQSxZQUNGLENBQUM7QUFDRCxpQkFBSyxZQUFZLFVBQVUsRUFBRSxPQUFPLFFBQVEsU0FBUyxZQUFZLE1BQU0scUJBQXFCLENBQUMsQ0FBQztBQUFBLFVBQ2hHO0FBRUEsY0FBSSxNQUFNLFNBQVMsaUJBQWlCO0FBQ2xDLGtCQUFNLGNBQWMsVUFBVTtBQUFBLGNBQzVCLE9BQU8sTUFBTTtBQUFBLGNBQ2IsYUFBYSxNQUFNLGFBQWE7QUFBQSxjQUNoQyxTQUFTLENBQUMsVUFBa0I7QUFDMUIsc0JBQU0sU0FBUztBQUNmLHNCQUFNLE9BQU87QUFBQSxjQUNmO0FBQUEsWUFDRixDQUFDO0FBQ0QsZ0JBQUksTUFBTSxhQUFhLFNBQVMsR0FBRztBQUNqQyxvQkFBTSxrQkFBa0IsV0FBVztBQUFBLGdCQUNqQyxPQUFPLE1BQU0sYUFBYSxPQUFPLE1BQU0sYUFBYSxDQUFDLEdBQUcsT0FBTyxFQUFFO0FBQUEsZ0JBQ2pFLFNBQVMsTUFBTSxhQUFhLElBQUksQ0FBQyxVQUFlLEVBQUUsT0FBTyxPQUFPLEtBQUssT0FBTyxLQUFLLFNBQVMsS0FBSyxTQUFTLEVBQUUsR0FBRyxPQUFPLE9BQU8sS0FBSyxTQUFTLEtBQUssT0FBTyxFQUFFLEVBQUUsRUFBRTtBQUFBLGdCQUMzSixVQUFVLENBQUMsVUFBa0I7QUFDM0Isd0JBQU0sWUFBWTtBQUNsQix3QkFBTSxRQUFRLE1BQU0sYUFBYSxLQUFLLENBQUMsU0FBYyxPQUFPLEtBQUssT0FBTyxFQUFFLE1BQU0sS0FBSztBQUNyRixzQkFBSSxPQUFPLE9BQU87QUFDaEIsMEJBQU0sU0FBUyxPQUFPLE1BQU0sS0FBSztBQUNqQywwQkFBTSxPQUFPLE9BQU8sTUFBTSxLQUFLO0FBQUEsa0JBQ2pDO0FBQ0EseUJBQU87QUFBQSxnQkFDVDtBQUFBLGNBQ0YsQ0FBQztBQUNELG9CQUFNLFFBQVEsU0FBUyxjQUFjLEtBQUs7QUFDMUMsb0JBQU0sWUFBWTtBQUNsQixvQkFBTSxPQUFPLGFBQWEsZUFBZTtBQUN6QyxvQkFBTSxhQUFhLE1BQU0sYUFBYSxLQUFLLENBQUMsU0FBYyxPQUFPLEtBQUssT0FBTyxFQUFFLE1BQU0sTUFBTSxTQUFTLEdBQUcsUUFBUTtBQUMvRyxtQkFBSyxZQUFZLFVBQVUsRUFBRSxPQUFPLFVBQVUsU0FBUyxPQUFPLE1BQU0sV0FBVyxDQUFDLENBQUM7QUFBQSxZQUNuRixPQUFPO0FBQ0wsbUJBQUssWUFBWSxVQUFVLEVBQUUsT0FBTyxVQUFVLFNBQVMsWUFBWSxDQUFDLENBQUM7QUFBQSxZQUN2RTtBQUFBLFVBQ0Y7QUFFQSxjQUFJLE1BQU0sU0FBUyxtQkFBbUI7QUFDcEMsa0JBQU0sZ0JBQWdCLFVBQVU7QUFBQSxjQUM5QixPQUFPLE1BQU07QUFBQSxjQUNiLGFBQWE7QUFBQSxjQUNiLFNBQVMsQ0FBQyxVQUFrQjtBQUMxQixzQkFBTSxXQUFXO0FBQ2pCLHNCQUFNLGVBQWU7QUFBQSxjQUN2QjtBQUFBLFlBQ0YsQ0FBQztBQUNELGlCQUFLLFlBQVksVUFBVSxFQUFFLE9BQU8sUUFBUSxTQUFTLGVBQWUsTUFBTSx5QkFBeUIsQ0FBQyxDQUFDO0FBQUEsVUFDdkc7QUFFQSxjQUFJLE1BQU0sU0FBUyx1QkFBdUI7QUFDeEMsa0JBQU0sY0FBYyxNQUFNLFFBQVEsTUFBTSxTQUFTLG9CQUFvQixJQUFJLE1BQU0sUUFBUSxxQkFBcUIsT0FBTyxPQUFPLElBQUksQ0FBQztBQUMvSCxrQkFBTSxjQUFjLFlBQVksU0FDNUIsV0FBVztBQUFBLGNBQ1QsT0FBTyxNQUFNO0FBQUEsY0FDYixTQUFTLFlBQVksSUFBSSxDQUFDLFVBQWUsRUFBRSxPQUFPLE9BQU8sS0FBSyxTQUFTLEVBQUUsR0FBRyxPQUFPLE9BQU8sS0FBSyxTQUFTLEtBQUssU0FBUyxFQUFFLEVBQUUsRUFBRTtBQUFBLGNBQzVILFVBQVUsQ0FBQyxVQUFrQjtBQUFFLHNCQUFNLGNBQWM7QUFBQSxjQUFNO0FBQUEsWUFDM0QsQ0FBQyxJQUNELFVBQVU7QUFBQSxjQUNSLE9BQU8sTUFBTTtBQUFBLGNBQ2IsYUFBYTtBQUFBLGNBQ2IsU0FBUyxDQUFDLFVBQWtCO0FBQUUsc0JBQU0sY0FBYztBQUFBLGNBQU07QUFBQSxZQUMxRCxDQUFDO0FBQ0wsa0JBQU0sV0FBVyxZQUFZLEtBQUssQ0FBQyxTQUFjLE9BQU8sS0FBSyxTQUFTLEVBQUUsTUFBTSxPQUFPLE1BQU0sV0FBVyxDQUFDLEdBQUcsUUFBUTtBQUNsSCxpQkFBSyxZQUFZLFVBQVUsRUFBRSxPQUFPLFFBQVEsU0FBUyxhQUFhLE1BQU0sWUFBWSxPQUFVLENBQUMsQ0FBQztBQUFBLFVBQ2xHO0FBRUEsY0FBSSxNQUFNLFNBQVMsNEJBQTRCO0FBQzdDLGtCQUFNLGNBQWMsVUFBVTtBQUFBLGNBQzVCLE9BQU8sTUFBTTtBQUFBLGNBQ2IsYUFBYSxPQUFPLE1BQU0sU0FBUyxtQkFBbUIsY0FBYyxHQUFHO0FBQUEsY0FDdkUsU0FBUyxDQUFDLFVBQWtCO0FBQUUsc0JBQU0sZ0JBQWdCO0FBQUEsY0FBTTtBQUFBLFlBQzVELENBQUM7QUFDRCxrQkFBTSxhQUFhLE1BQU0sU0FBUyxtQkFBbUIsaUJBQ2pELHFDQUNBO0FBQ0osaUJBQUssWUFBWSxVQUFVLEVBQUUsT0FBTyxlQUFlLFNBQVMsYUFBYSxNQUFNLFdBQVcsQ0FBQyxDQUFDO0FBQUEsVUFDOUY7QUFFQSxlQUFLLFlBQVksSUFBSTtBQUNyQixjQUFJLE1BQU0sUUFBUyxNQUFLLFlBQVksaUJBQWlCLEVBQUUsTUFBTSxZQUFZLENBQUMsQ0FBQztBQUFBLG1CQUNsRSxNQUFNLFNBQVMsMkJBQTJCO0FBQ2pELGlCQUFLLFlBQVksc0JBQXNCO0FBQUEsY0FDckMsU0FBUyxNQUFNO0FBQUEsY0FDZixTQUFTLE1BQU07QUFBQSxjQUNmLE9BQU8sTUFBTTtBQUFBLGNBQ2IsTUFBTSxNQUFNO0FBQUEsWUFDZCxDQUFDLENBQUM7QUFBQSxVQUNKO0FBRUEsZ0JBQU0sU0FBUyxTQUFTLGNBQWMsS0FBSztBQUMzQyxpQkFBTyxZQUFZO0FBQ25CLGdCQUFNLFNBQVMsV0FBVyxFQUFFLE9BQU8sTUFBTSxTQUFTLE1BQU0sQ0FBQyxNQUFNLGNBQWMsTUFBTSxNQUFNLEVBQUUsQ0FBQztBQUM1RixnQkFBTSxZQUFZLGlCQUFpQjtBQUFBLFlBQ2pDLFdBQVc7QUFBQSxZQUNYLGlCQUFpQjtBQUFBLFlBQ2pCLGNBQWM7QUFBQSxZQUNkLFlBQVk7QUFBQSxZQUNaLFFBQVEsTUFBTTtBQUFBLFlBQ2QsVUFBVSxNQUFNO0FBQUEsWUFDaEIsV0FBVztBQUFBLFlBQ1gsVUFBVSxNQUFNLFdBQVcsRUFBRSxpQkFBaUIsT0FBTyxNQUFNLFlBQVksRUFBRSxFQUFFLEtBQUssSUFBSSxPQUFPLE1BQU0sT0FBTyxFQUFFLEVBQUUsS0FBSyxNQUFNLENBQUMsTUFBTSxnQkFBZ0IsTUFBTSxpQkFBaUI7QUFBQSxZQUNySyxTQUFTLFlBQVk7QUFDbkIsa0JBQUk7QUFDRixzQkFBTSxTQUFTLE1BQU0sT0FBTztBQUM1Qix3QkFBUSxZQUFZLE1BQU07QUFBQSxjQUM1QixTQUFTLEdBQVE7QUFDZix3QkFBUSxVQUFVLENBQUM7QUFBQSxjQUNyQjtBQUFBLFlBQ0Y7QUFBQSxVQUNGLENBQUM7QUFDRCxnQkFBTSxlQUFlO0FBQ3JCLGlCQUFPLE9BQU8sUUFBUSxTQUFTO0FBQy9CLGdCQUFNLGlCQUFpQixNQUFNLEdBQUcsY0FBYyw2QkFBNkI7QUFDM0UsY0FBSSxlQUFnQixnQkFBZSxPQUFPO0FBQzFDLGdCQUFNLEdBQUcsY0FBYyxvQkFBb0IsR0FBRyxZQUFZLE1BQU07QUFBQSxRQUNsRTtBQUVBLGNBQU0sWUFBWTtBQUNsQixZQUFJLGdCQUFnQjtBQUNsQixpQkFBTyxXQUFXLE1BQU07QUFDdEIsa0JBQU0sUUFBUSxNQUFNLEtBQUssY0FBYywyQkFBMkI7QUFDbEUsbUJBQU8sTUFBTTtBQUFBLFVBQ2YsR0FBRyxDQUFDO0FBQUEsUUFDTjtBQUNBLGVBQU87QUFDUCxlQUFPO0FBQUEsTUFDVDtBQUVBLGFBQU8sRUFBRSxNQUFNLFVBQVUsS0FBSztBQUFBLElBQ2hDO0FBRUEsYUFBUyxPQUFPLElBQVk7QUFDMUIsWUFBTSxjQUFjLENBQUMsTUFBYyxTQUF1QixNQUFNLGdCQUFnQixFQUFFLEdBQUcsSUFBSSxJQUFJLElBQUk7QUFDakcsWUFBTSxZQUFZLDhCQUE4QixFQUFFO0FBQ2xELGFBQU87QUFBQSxRQUNMLFVBQVU7QUFBQSxRQUNWLEtBQUs7QUFBQSxVQUNILFFBQVE7QUFBQSxVQUNSLE9BQU8sQ0FBQyxTQUFpQixHQUFHLFNBQVMsYUFBYSxXQUFXLFFBQVEsSUFBSSxNQUFNLFNBQVMsSUFBSSxnQkFBZ0IsRUFBRSxHQUFHLElBQUk7QUFBQSxVQUNySCxLQUFLLENBQUMsTUFBYyxXQUFpQixJQUFJLElBQUksTUFBTSxNQUFNO0FBQUEsVUFDekQsTUFBTSxDQUFDLE1BQWMsTUFBWSxXQUFpQixJQUFJLEtBQUssTUFBTSxNQUFNLE1BQU07QUFBQSxRQUMvRTtBQUFBLFFBQ0EsT0FBTztBQUFBLFVBQ0wsU0FBUyxDQUFDLFFBQWdCLE1BQU0sUUFBUSxHQUFHO0FBQUEsVUFDM0MsT0FBTyxDQUFDLFFBQWdCLE1BQU0sTUFBTSxHQUFHO0FBQUEsVUFDdkMsTUFBTSxDQUFDLFFBQWdCLE1BQU0sS0FBSyxHQUFHO0FBQUEsVUFDckMsU0FBUyxDQUFDLFFBQWdCLE1BQU0sUUFBUSxHQUFHO0FBQUEsUUFDN0M7QUFBQSxRQUNBO0FBQUEsUUFDQSxJQUFJO0FBQUEsVUFDRixRQUFRO0FBQUEsVUFDUixPQUFPO0FBQUEsVUFDUCxRQUFRO0FBQUEsVUFDUixPQUFPO0FBQUEsVUFDUCxPQUFPO0FBQUEsVUFDUCxPQUFPO0FBQUEsVUFDUCxNQUFNO0FBQUEsVUFDTixZQUFZO0FBQUEsVUFDWixjQUFjO0FBQUEsVUFDZCxRQUFRO0FBQUEsVUFDUixXQUFXO0FBQUEsVUFDWCxVQUFVO0FBQUEsVUFDVixVQUFVO0FBQUEsVUFDVixXQUFXO0FBQUEsVUFDWCxjQUFjO0FBQUEsVUFDZCxPQUFPLENBQUMsTUFBVztBQUFFLGtCQUFNLElBQUksU0FBUyxjQUFjLEVBQUUsVUFBVSxXQUFXLE1BQU07QUFBRyxjQUFFLFlBQVksQ0FBQyxxQkFBcUIsRUFBRSxPQUFPLHNCQUFzQixFQUFFLElBQUksS0FBSyxJQUFJLEVBQUUsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHO0FBQUcsY0FBRSxjQUFjLEVBQUUsU0FBUztBQUFJLGdCQUFJLEVBQUUsUUFBUyxDQUFDLEVBQXdCLFVBQVUsRUFBRTtBQUFTLG1CQUFPO0FBQUEsVUFBRTtBQUFBLFVBQzNULE1BQU0sQ0FBQyxNQUFXO0FBQUUsa0JBQU0sSUFBSSxXQUFXLEVBQUUsT0FBTyxFQUFFLE9BQU8sV0FBVyxDQUFDLG9CQUFvQixFQUFFLFNBQVMsY0FBYyxJQUFJLEVBQUUsYUFBYSxFQUFFLEVBQUUsT0FBTyxPQUFPLEVBQUUsS0FBSyxHQUFHLEVBQUUsQ0FBQztBQUFHLGNBQUUsVUFBVSxFQUFFO0FBQVMsbUJBQU87QUFBQSxVQUFFO0FBQUEsVUFDek0sUUFBUSxDQUFDLE1BQVc7QUFBRSxrQkFBTSxJQUFJLFNBQVMsY0FBYyxLQUFLO0FBQUcsY0FBRSxZQUFZLDBDQUEwQyxFQUFFLFFBQVEsTUFBTTtBQUFJLGNBQUUsY0FBYyxFQUFFLFFBQVE7QUFBSSxtQkFBTztBQUFBLFVBQUU7QUFBQSxVQUNsTCxZQUFZLENBQUMsTUFBVztBQUFFLGtCQUFNLElBQUksU0FBUyxjQUFjLEtBQUs7QUFBRyxjQUFFLFlBQVk7QUFBcUIsY0FBRSxjQUFjLEVBQUUsUUFBUTtBQUFRLG1CQUFPO0FBQUEsVUFBRTtBQUFBLFVBQ2pKLFlBQVksQ0FBQyxNQUFXO0FBQUUsa0JBQU0sSUFBSSxTQUFTLGNBQWMsS0FBSztBQUFHLGNBQUUsWUFBWTtBQUE4QyxjQUFFLGNBQWMsRUFBRSxRQUFRO0FBQVEsbUJBQU87QUFBQSxVQUFFO0FBQUEsVUFDMUssY0FBYyxDQUFDLE1BQVc7QUFBRSxrQkFBTSxJQUFJLFNBQVMsY0FBYyxLQUFLO0FBQUcsY0FBRSxZQUFZLHdCQUF3QixFQUFFLGFBQWEsRUFBRTtBQUFJLG1CQUFPO0FBQUEsVUFBRTtBQUFBLFVBQ3pJLE1BQU0sQ0FBQyxNQUFXO0FBQUUsa0JBQU0sSUFBSSxTQUFTLGNBQWMsRUFBRSxPQUFPLE1BQU0sS0FBSztBQUFHLGNBQUUsWUFBWSxvQkFBb0IsRUFBRSxhQUFhLEVBQUU7QUFBSSxnQkFBSSxFQUFFLE1BQU07QUFBRSxjQUFDLEVBQXdCLE9BQU8sRUFBRTtBQUFNLGNBQUMsRUFBd0IsU0FBUyxFQUFFLFVBQVU7QUFBQSxZQUFRO0FBQUM7QUFBRSxtQkFBTztBQUFBLFVBQUU7QUFBQSxVQUMzUCxTQUFTLENBQUMsTUFBVyxRQUFRLFFBQVEsRUFBRSxPQUFPLEVBQUUsU0FBUyxRQUFRLFNBQVMsRUFBRSxXQUFXLElBQUksYUFBYSxFQUFFLGVBQWUsTUFBTSxRQUFRLENBQUMsQ0FBQyxFQUFFLE9BQU8sQ0FBQztBQUFBLFFBQ3JKO0FBQUEsTUFDRjtBQUFBLElBQ0Y7QUFFQSxtQkFBZSxjQUFjO0FBQzNCLG1CQUFhO0FBQ2IsVUFBSSxDQUFDLFNBQVMsU0FBUyxDQUFDLEtBQUssTUFBTztBQUNwQyxjQUFRLFFBQVE7QUFDaEIsWUFBTSxRQUFRO0FBQ2QsVUFBSTtBQUNGLGNBQU0sT0FBTyxNQUFNLElBQUksSUFBSSxZQUFZLFNBQVMsS0FBSyxTQUFTLEVBQUUsS0FBSyxPQUFLLEVBQUUsSUFBSTtBQUNoRixjQUFNLFFBQVEsTUFBTSxRQUFRLFVBQVU7QUFDdEMsWUFBSSxPQUFPO0FBQ1QsZ0JBQU0sT0FBTyxLQUFLLElBQUk7QUFDdEIsb0JBQVUsU0FBUyxjQUFjLE1BQU07QUFDdkMsa0JBQVEsTUFBTTtBQUNkLGtCQUFRLE9BQU8sZ0JBQWdCLFNBQVMsS0FBSyxXQUFXLE1BQU0sUUFBUSxlQUFlLEVBQUUsQ0FBQyxNQUFNLElBQUk7QUFDbEcsbUJBQVMsS0FBSyxZQUFZLE9BQU87QUFBQSxRQUNuQztBQUNBLGNBQU0sUUFBUSxNQUFNLFFBQVEsVUFBVSxTQUFTO0FBQy9DLGNBQU0sTUFBTSxNQUFNO0FBQUE7QUFBQSxVQUEwQixnQkFBZ0IsU0FBUyxLQUFLLFdBQVcsTUFBTSxRQUFRLGVBQWUsRUFBRSxDQUFDLE1BQU0sS0FBSyxJQUFJLENBQUM7QUFBQTtBQUNySSxjQUFNLFNBQVM7QUFDZixjQUFNLE1BQU0sTUFBTSxJQUFJLE1BQU0sS0FBSyxPQUFPLE9BQU8sU0FBUyxLQUFLLENBQUM7QUFDOUQsWUFBSSxPQUFPLFFBQVEsV0FBWSxXQUFVO0FBQUEsTUFDM0MsU0FBUyxHQUFRO0FBQ2YsY0FBTSxRQUFRLEdBQUcsVUFBVSxNQUFNLFVBQVUsR0FBRyxXQUFXO0FBQUEsTUFDM0QsVUFBRTtBQUNBLGdCQUFRLFFBQVE7QUFBQSxNQUNsQjtBQUFBLElBQ0Y7QUFFQSxjQUFVLFdBQVc7QUFDckIsVUFBTSxVQUFVLFdBQVc7QUFDM0Isb0JBQWdCLFlBQVk7Ozs7Ozs7Ozs7Ozs7OztxQkFJckIsT0FBTSxtQkFBa0I7OztFQUNQLE9BQU07Ozs7RUFDUixPQUFNOzs7dUJBRjFCLG9CQUlNLE9BSk4sWUFJTTtBQUFBLElBSE8sZ0NBQVgsb0JBQXlELE9BQXpELFlBQThDLE9BQUs7SUFDeEMsOEJBQVg7QUFBQSxNQUFzRjtBQUFBLE1BQXRGO0FBQUEsTUFBc0YsaUJBQWQsWUFBSztBQUFBO0FBQUE7QUFBQTtJQUM3RTtBQUFBLE1BQStFO0FBQUE7QUFBQSxRQUExRSxLQUFJO0FBQUEsUUFBTyxPQUFLLGlCQUFDLHFCQUFtQixnQkFBeUIsZUFBTztBQUFBIiwibmFtZXMiOlsiZGlzcG9zZSJdLCJpZ25vcmVMaXN0IjpbXSwic291cmNlcyI6WyJQbHVnaW5Ib3N0LnZ1ZSJdLCJzb3VyY2VzQ29udGVudCI6WyI8c2NyaXB0IHNldHVwIGxhbmc9XCJ0c1wiPlxuaW1wb3J0IHsgY29tcHV0ZWQsIG5leHRUaWNrLCBvbkJlZm9yZVVubW91bnQsIG9uTW91bnRlZCwgcmVmLCB3YXRjaCB9IGZyb20gJ3Z1ZSdcbmltcG9ydCB7IHVzZVJvdXRlIH0gZnJvbSAndnVlLXJvdXRlcidcbmltcG9ydCBhcGkgZnJvbSAnLi4vYXBpJ1xuaW1wb3J0IHsgdXNlVG9hc3QgfSBmcm9tICcuLi9jb21wb3NhYmxlcy91c2VUb2FzdCdcbmltcG9ydCB7IHVzZUNvbmZpcm0gfSBmcm9tICcuLi9jb21wb3NhYmxlcy91c2VDb25maXJtJ1xuXG5jb25zdCByb3V0ZSA9IHVzZVJvdXRlKClcbmNvbnN0IHRvYXN0ID0gdXNlVG9hc3QoKVxuY29uc3QgY29uZmlybSA9IHVzZUNvbmZpcm0oKVxuY29uc3QgaG9zdCA9IHJlZjxIVE1MRWxlbWVudCB8IG51bGw+KG51bGwpXG5jb25zdCBsb2FkaW5nID0gcmVmKGZhbHNlKVxuY29uc3QgZXJyb3IgPSByZWYoJycpXG5jb25zdCBwbHVnaW5JZCA9IGNvbXB1dGVkKCgpID0+IFN0cmluZyhyb3V0ZS5wYXJhbXMucGx1Z2luSWQgfHwgJycpKVxubGV0IGRpc3Bvc2U6IG51bGwgfCAoKCkgPT4gdm9pZCkgPSBudWxsXG5sZXQgc3R5bGVFbDogSFRNTExpbmtFbGVtZW50IHwgbnVsbCA9IG51bGxcblxuZnVuY3Rpb24gY2xlYXJNb3VudGVkKCkge1xuICBpZiAoZGlzcG9zZSkge1xuICAgIHRyeSB7IGRpc3Bvc2UoKSB9IGNhdGNoIHt9XG4gICAgZGlzcG9zZSA9IG51bGxcbiAgfVxuICBpZiAoc3R5bGVFbCkge1xuICAgIHN0eWxlRWwucmVtb3ZlKClcbiAgICBzdHlsZUVsID0gbnVsbFxuICB9XG4gIGlmIChob3N0LnZhbHVlKSBob3N0LnZhbHVlLmlubmVySFRNTCA9ICcnXG59XG5cbmZ1bmN0aW9uIG1ha2VCdXR0b24ob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3QgYnRuID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJylcbiAgYnRuLnR5cGUgPSAnYnV0dG9uJ1xuICBidG4uY2xhc3NOYW1lID0gWydub29yLXBsdWdpbi1idG4nLCBvcHRpb25zLnRvbmUgPT09ICdwcmltYXJ5JyA/ICdub29yLXBsdWdpbi1idG4tLXByaW1hcnknIDogJycsIG9wdGlvbnMudG9uZSA9PT0gJ2RhbmdlcicgPyAnbm9vci1wbHVnaW4tYnRuLS1kYW5nZXInIDogJycsIG9wdGlvbnMuY2xhc3NOYW1lIHx8ICcnXS5maWx0ZXIoQm9vbGVhbikuam9pbignICcpXG4gIGJ0bi50ZXh0Q29udGVudCA9IG9wdGlvbnMubGFiZWwgfHwgJydcbiAgaWYgKG9wdGlvbnMudGl0bGUpIGJ0bi50aXRsZSA9IG9wdGlvbnMudGl0bGVcbiAgaWYgKG9wdGlvbnMuZGlzYWJsZWQpIGJ0bi5kaXNhYmxlZCA9IHRydWVcbiAgaWYgKG9wdGlvbnMub25DbGljaykgYnRuLm9uY2xpY2sgPSBvcHRpb25zLm9uQ2xpY2tcbiAgcmV0dXJuIGJ0blxufVxuXG5mdW5jdGlvbiBtYWtlSW5wdXQob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3QgaW5wdXQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdpbnB1dCcpXG4gIGlucHV0LmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4taW5wdXQnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBpbnB1dC52YWx1ZSA9IG9wdGlvbnMudmFsdWUgPz8gJydcbiAgaW5wdXQucGxhY2Vob2xkZXIgPSBvcHRpb25zLnBsYWNlaG9sZGVyIHx8ICcnXG4gIGlucHV0LnJlYWRPbmx5ID0gISFvcHRpb25zLnJlYWRvbmx5XG4gIGlucHV0Lm9uaW5wdXQgPSAoKSA9PiBvcHRpb25zLm9uSW5wdXQ/LihpbnB1dC52YWx1ZSlcbiAgcmV0dXJuIGlucHV0XG59XG5cbmZ1bmN0aW9uIG1ha2VTZWxlY3Qob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3Qgc2VsZWN0ID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc2VsZWN0JylcbiAgc2VsZWN0LmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4taW5wdXQnLCAnbm9vci1wbHVnaW4tc2VsZWN0Jywgb3B0aW9ucy5jbGFzc05hbWUgfHwgJyddLmZpbHRlcihCb29sZWFuKS5qb2luKCcgJylcbiAgZm9yIChjb25zdCBpdGVtIG9mIG9wdGlvbnMub3B0aW9ucyB8fCBbXSkge1xuICAgIGNvbnN0IG9wdCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ29wdGlvbicpXG4gICAgb3B0LnZhbHVlID0gU3RyaW5nKGl0ZW0udmFsdWUgPz8gJycpXG4gICAgb3B0LnRleHRDb250ZW50ID0gU3RyaW5nKGl0ZW0ubGFiZWwgPz8gaXRlbS52YWx1ZSA/PyAnJylcbiAgICBzZWxlY3QuYXBwZW5kQ2hpbGQob3B0KVxuICB9XG4gIHNlbGVjdC52YWx1ZSA9IG9wdGlvbnMudmFsdWUgPz8gJydcbiAgc2VsZWN0Lm9uY2hhbmdlID0gKCkgPT4gb3B0aW9ucy5vbkNoYW5nZT8uKHNlbGVjdC52YWx1ZSlcbiAgcmV0dXJuIHNlbGVjdFxufVxuXG5mdW5jdGlvbiBtYWtlRmllbGQob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3QgZmllbGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdsYWJlbCcpXG4gIGZpZWxkLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tZmllbGQnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBjb25zdCBsYWJlbCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3NwYW4nKVxuICBsYWJlbC5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tZmllbGRfX2xhYmVsJ1xuICBsYWJlbC50ZXh0Q29udGVudCA9IG9wdGlvbnMubGFiZWwgfHwgJydcbiAgZmllbGQuYXBwZW5kQ2hpbGQobGFiZWwpXG4gIGlmIChvcHRpb25zLmNvbnRyb2wpIGZpZWxkLmFwcGVuZENoaWxkKG9wdGlvbnMuY29udHJvbClcbiAgaWYgKG9wdGlvbnMuaGludCkge1xuICAgIGNvbnN0IGhpbnQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzbWFsbCcpXG4gICAgaGludC5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tZmllbGRfX2hpbnQnXG4gICAgaGludC50ZXh0Q29udGVudCA9IG9wdGlvbnMuaGludFxuICAgIGZpZWxkLmFwcGVuZENoaWxkKGhpbnQpXG4gIH1cbiAgcmV0dXJuIGZpZWxkXG59XG5cbmZ1bmN0aW9uIG1ha2VNb2RhbChvcHRpb25zOiBhbnkgPSB7fSkge1xuICBjb25zdCBtYXNrID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgbWFzay5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tbW9kYWwtbWFzaydcbiAgY29uc3QgcGFuZWwgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBwYW5lbC5jbGFzc05hbWUgPSBgbm9vci1wbHVnaW4tbW9kYWwgbm9vci1wbHVnaW4tbW9kYWwtLSR7b3B0aW9ucy53aWR0aCB8fCAnbWQnfWBcbiAgY29uc3QgaGVhZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGhlYWQuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLW1vZGFsX19oZWFkJ1xuICBjb25zdCB0aXRsZSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIHRpdGxlLmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1tb2RhbF9fdGl0bGUnXG4gIHRpdGxlLnRleHRDb250ZW50ID0gb3B0aW9ucy50aXRsZSB8fCAnJ1xuICBjb25zdCBjbG9zZUJ0biA9IG1ha2VCdXR0b24oeyBsYWJlbDogJ8OXJywgdGl0bGU6ICflhbPpl60nLCBjbGFzc05hbWU6ICdub29yLXBsdWdpbi1tb2RhbF9fY2xvc2UnIH0pXG4gIGhlYWQuYXBwZW5kKHRpdGxlLCBjbG9zZUJ0bilcbiAgY29uc3QgYm9keSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGJvZHkuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLW1vZGFsX19ib2R5J1xuICBpZiAoQXJyYXkuaXNBcnJheShvcHRpb25zLmNvbnRlbnQpKSBvcHRpb25zLmNvbnRlbnQuZm9yRWFjaCgoeDogTm9kZSkgPT4gYm9keS5hcHBlbmRDaGlsZCh4KSlcbiAgZWxzZSBpZiAob3B0aW9ucy5jb250ZW50KSBib2R5LmFwcGVuZENoaWxkKG9wdGlvbnMuY29udGVudClcbiAgcGFuZWwuYXBwZW5kKGhlYWQsIGJvZHkpXG4gIGNvbnN0IGZvb3RlciA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGZvb3Rlci5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tbW9kYWxfX2FjdGlvbnMnXG4gIGlmIChBcnJheS5pc0FycmF5KG9wdGlvbnMuZm9vdGVyKSkgb3B0aW9ucy5mb290ZXIuZm9yRWFjaCgoeDogTm9kZSkgPT4gZm9vdGVyLmFwcGVuZENoaWxkKHgpKVxuICBlbHNlIGlmIChvcHRpb25zLmZvb3RlcikgZm9vdGVyLmFwcGVuZENoaWxkKG9wdGlvbnMuZm9vdGVyKVxuICBpZiAoZm9vdGVyLmNoaWxkTm9kZXMubGVuZ3RoKSBwYW5lbC5hcHBlbmRDaGlsZChmb290ZXIpXG4gIG1hc2suYXBwZW5kQ2hpbGQocGFuZWwpXG4gIGNvbnN0IGNsb3NlID0gKCkgPT4geyBtYXNrLnJlbW92ZSgpOyBvcHRpb25zLm9uQ2xvc2U/LigpIH1cbiAgY2xvc2VCdG4ub25jbGljayA9IGNsb3NlXG4gIG1hc2sub25jbGljayA9IGV2ZW50ID0+IHsgaWYgKGV2ZW50LnRhcmdldCA9PT0gbWFzayAmJiBvcHRpb25zLmNsb3NlT25NYXNrICE9PSBmYWxzZSkgY2xvc2UoKSB9XG4gIGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQobWFzaylcbiAgcmV0dXJuIHsgZWw6IG1hc2ssIGJvZHksIGNsb3NlIH1cbn1cblxuZnVuY3Rpb24gbWFrZVBhbmVsKG9wdGlvbnM6IGFueSA9IHt9KSB7XG4gIGNvbnN0IG1hc2sgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBtYXNrLmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1wYW5lbC1tYXNrJ1xuICBjb25zdCBwYW5lbCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIHBhbmVsLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tcGFuZWwnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBjb25zdCBzY3JvbGwgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBzY3JvbGwuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXBhbmVsX19zY3JvbGwnXG4gIGNvbnN0IGhlYWQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBoZWFkLmNsYXNzTmFtZSA9ICdkZXRhaWwtcGFuZWwtdG9wYmFyIG5vb3ItcGx1Z2luLXBhbmVsX19oZWFkJ1xuICBjb25zdCBtZXRhID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgbWV0YS5jbGFzc05hbWUgPSAnZGV0YWlsLXBhbmVsLXRvcGJhcl9fbWV0YSBub29yLXBsdWdpbi1wYW5lbF9fbWV0YSdcbiAgaWYgKG9wdGlvbnMuZXllYnJvdykge1xuICAgIGNvbnN0IGV5ZWJyb3cgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzcGFuJylcbiAgICBleWVicm93LmNsYXNzTmFtZSA9ICdkZXRhaWwtcGFuZWwtdG9wYmFyX19leWVicm93IG5vb3ItcGx1Z2luLXBhbmVsX19leWVicm93J1xuICAgIGV5ZWJyb3cudGV4dENvbnRlbnQgPSBvcHRpb25zLmV5ZWJyb3dcbiAgICBtZXRhLmFwcGVuZENoaWxkKGV5ZWJyb3cpXG4gIH1cbiAgY29uc3QgdGl0bGUgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICB0aXRsZS5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tcGFuZWxfX3RpdGxlJ1xuICB0aXRsZS50ZXh0Q29udGVudCA9IG9wdGlvbnMudGl0bGUgfHwgJydcbiAgbWV0YS5hcHBlbmRDaGlsZCh0aXRsZSlcbiAgY29uc3QgY2xvc2VCdG4gPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKVxuICBjbG9zZUJ0bi50eXBlID0gJ2J1dHRvbidcbiAgY2xvc2VCdG4uY2xhc3NOYW1lID0gJ2RldGFpbC1wYW5lbC10b3BiYXJfX2Nsb3NlIG5vb3ItcGx1Z2luLXBhbmVsX19jbG9zZSdcbiAgY2xvc2VCdG4udGl0bGUgPSAn5YWz6ZetJ1xuICBjbG9zZUJ0bi5zZXRBdHRyaWJ1dGUoJ2FyaWEtbGFiZWwnLCAn5YWz6ZetJylcbiAgY2xvc2VCdG4uaW5uZXJIVE1MID0gYDxzdmcgeG1sbnM9XCJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2Z1wiIHdpZHRoPVwiMjBcIiBoZWlnaHQ9XCIyMFwiIGZpbGw9XCJub25lXCIgdmlld0JveD1cIjAgMCAyNCAyNFwiIHN0cm9rZT1cImN1cnJlbnRDb2xvclwiPjxwYXRoIHN0cm9rZS1saW5lY2FwPVwicm91bmRcIiBzdHJva2UtbGluZWpvaW49XCJyb3VuZFwiIHN0cm9rZS13aWR0aD1cIjJcIiBkPVwiTTYgMThMMTggNk02IDZsMTIgMTJcIi8+PC9zdmc+YFxuICBoZWFkLmFwcGVuZChtZXRhLCBjbG9zZUJ0bilcbiAgY29uc3QgYm9keSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGJvZHkuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXBhbmVsX19ib2R5J1xuICBpZiAoQXJyYXkuaXNBcnJheShvcHRpb25zLmNvbnRlbnQpKSBvcHRpb25zLmNvbnRlbnQuZm9yRWFjaCgoeDogTm9kZSkgPT4gYm9keS5hcHBlbmRDaGlsZCh4KSlcbiAgZWxzZSBpZiAob3B0aW9ucy5jb250ZW50KSBib2R5LmFwcGVuZENoaWxkKG9wdGlvbnMuY29udGVudClcbiAgc2Nyb2xsLmFwcGVuZChoZWFkLCBib2R5KVxuICBwYW5lbC5hcHBlbmRDaGlsZChzY3JvbGwpXG4gIG1hc2suYXBwZW5kQ2hpbGQocGFuZWwpXG4gIGNvbnN0IGNsb3NlID0gKCkgPT4geyBtYXNrLnJlbW92ZSgpOyBvcHRpb25zLm9uQ2xvc2U/LigpIH1cbiAgY2xvc2VCdG4ub25jbGljayA9IGNsb3NlXG4gIG1hc2sub25jbGljayA9IGV2ZW50ID0+IHsgaWYgKGV2ZW50LnRhcmdldCA9PT0gbWFzayAmJiBvcHRpb25zLmNsb3NlT25NYXNrICE9PSBmYWxzZSkgY2xvc2UoKSB9XG4gIGRvY3VtZW50LmJvZHkuYXBwZW5kQ2hpbGQobWFzaylcbiAgcmV0dXJuIHsgZWw6IG1hc2ssIGJvZHksIGNsb3NlLCBwYW5lbCB9XG59XG5cbmZ1bmN0aW9uIG1ha2VUYWJzKG9wdGlvbnM6IGFueSA9IHt9KSB7XG4gIGNvbnN0IHdyYXAgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKSBhcyBIVE1MRGl2RWxlbWVudCAmIHsgZGlzcG9zZT86ICgpID0+IHZvaWQ7IF9fbm9vckRpc3Bvc2U/OiAoKSA9PiB2b2lkIH1cbiAgd3JhcC5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tdGFicydcbiAgY29uc3QgbWFya2VyID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc3BhbicpXG4gIG1hcmtlci5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tdGFic19fbWFya2VyJ1xuICB3cmFwLmFwcGVuZENoaWxkKG1hcmtlcilcblxuICBjb25zdCBidXR0b25zOiBIVE1MQnV0dG9uRWxlbWVudFtdID0gW11cbiAgY29uc3QgZ2V0VGFiVmFsdWUgPSAodGFiOiBhbnkpID0+IFN0cmluZyh0YWI/LnZhbHVlID8/IHRhYj8ua2V5ID8/ICcnKVxuICBjb25zdCBpbml0aWFsVGFicyA9IEFycmF5LmlzQXJyYXkob3B0aW9ucy50YWJzKSA/IG9wdGlvbnMudGFicyA6IFtdXG4gIGNvbnN0IGluaXRpYWxWYWx1ZSA9IFN0cmluZyhvcHRpb25zLnZhbHVlID8/ICcnKSB8fCBnZXRUYWJWYWx1ZShpbml0aWFsVGFic1swXSlcbiAgb3B0aW9ucy52YWx1ZSA9IGluaXRpYWxWYWx1ZVxuICBsZXQgcmFmID0gMFxuXG4gIGNvbnN0IHJlZnJlc2ggPSAoKSA9PiB7XG4gICAgaWYgKCF3cmFwLmlzQ29ubmVjdGVkKSByZXR1cm5cbiAgICBjb25zdCBhY3RpdmVWYWx1ZSA9IFN0cmluZyhvcHRpb25zLnZhbHVlID8/ICcnKVxuICAgIGJ1dHRvbnMuZm9yRWFjaChidXR0b24gPT4gYnV0dG9uLmNsYXNzTGlzdC50b2dnbGUoJ2lzLWFjdGl2ZScsIGJ1dHRvbi5kYXRhc2V0LnZhbHVlID09PSBhY3RpdmVWYWx1ZSkpXG4gICAgY29uc3QgYWN0aXZlID0gYnV0dG9ucy5maW5kKGIgPT4gYi5kYXRhc2V0LnZhbHVlID09PSBhY3RpdmVWYWx1ZSkgfHwgYnV0dG9uc1swXVxuICAgIGlmICghYWN0aXZlKSByZXR1cm5cbiAgICBtYXJrZXIuc3R5bGUud2lkdGggPSBgJHthY3RpdmUub2Zmc2V0V2lkdGh9cHhgXG4gICAgbWFya2VyLnN0eWxlLnRyYW5zZm9ybSA9IGB0cmFuc2xhdGVYKCR7YWN0aXZlLm9mZnNldExlZnR9cHgpYFxuICB9XG5cbiAgY29uc3Qgc2NoZWR1bGVSZWZyZXNoID0gKCkgPT4ge1xuICAgIGlmIChyYWYpIGNhbmNlbEFuaW1hdGlvbkZyYW1lKHJhZilcbiAgICByYWYgPSByZXF1ZXN0QW5pbWF0aW9uRnJhbWUoKCkgPT4geyByYWYgPSAwOyByZWZyZXNoKCkgfSlcbiAgfVxuXG4gIGZvciAoY29uc3QgdGFiIG9mIGluaXRpYWxUYWJzKSB7XG4gICAgY29uc3QgdmFsdWUgPSBnZXRUYWJWYWx1ZSh0YWIpXG4gICAgY29uc3QgYnRuID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnYnV0dG9uJylcbiAgICBidG4udHlwZSA9ICdidXR0b24nXG4gICAgYnRuLnRleHRDb250ZW50ID0gdGFiLmxhYmVsID8/IHZhbHVlXG4gICAgYnRuLmRhdGFzZXQudmFsdWUgPSB2YWx1ZVxuICAgIGJ0bi5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tdGFic19faXRlbSdcbiAgICBidG4ub25jbGljayA9IChldmVudCkgPT4ge1xuICAgICAgZXZlbnQucHJldmVudERlZmF1bHQoKVxuICAgICAgZXZlbnQuc3RvcFByb3BhZ2F0aW9uKClcbiAgICAgIGlmIChTdHJpbmcob3B0aW9ucy52YWx1ZSA/PyAnJykgPT09IHZhbHVlKSByZXR1cm5cbiAgICAgIG9wdGlvbnMudmFsdWUgPSB2YWx1ZVxuICAgICAgcmVmcmVzaCgpXG4gICAgICBvcHRpb25zLm9uQ2hhbmdlPy4odmFsdWUpXG4gICAgICBzY2hlZHVsZVJlZnJlc2goKVxuICAgIH1cbiAgICBidXR0b25zLnB1c2goYnRuKVxuICAgIHdyYXAuYXBwZW5kQ2hpbGQoYnRuKVxuICB9XG5cbiAgc2NoZWR1bGVSZWZyZXNoKClcbiAgcmVxdWVzdEFuaW1hdGlvbkZyYW1lKCgpID0+IHtcbiAgICByZWZyZXNoKClcbiAgICB3cmFwLmNsYXNzTGlzdC5hZGQoJ25vb3ItcGx1Z2luLXRhYnMtLXJlYWR5JylcbiAgfSlcbiAgd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoJ3Jlc2l6ZScsIHNjaGVkdWxlUmVmcmVzaClcbiAgY29uc3Qgc2V0VmFsdWUgPSAodmFsdWU6IHN0cmluZykgPT4ge1xuICAgIG9wdGlvbnMudmFsdWUgPSBTdHJpbmcodmFsdWUpXG4gICAgcmVmcmVzaCgpXG4gIH1cbiAgY29uc3QgZGlzcG9zZSA9ICgpID0+IHtcbiAgICBpZiAocmFmKSBjYW5jZWxBbmltYXRpb25GcmFtZShyYWYpXG4gICAgd2luZG93LnJlbW92ZUV2ZW50TGlzdGVuZXIoJ3Jlc2l6ZScsIHNjaGVkdWxlUmVmcmVzaClcbiAgfVxuICB3cmFwLmRpc3Bvc2UgPSBkaXNwb3NlXG4gIHdyYXAuX19ub29yRGlzcG9zZSA9IGRpc3Bvc2VcbiAgOyh3cmFwIGFzIGFueSkuX19ub29yU2V0VmFsdWUgPSBzZXRWYWx1ZVxuICByZXR1cm4gd3JhcFxufVxuXG5mdW5jdGlvbiBtYWtlUGFnaW5hdGlvbihvcHRpb25zOiBhbnkgPSB7fSkge1xuICBjb25zdCB3cmFwID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgd3JhcC5jbGFzc05hbWUgPSAnbm9vci1wYWdpbmF0aW9uIG5vb3ItcGx1Z2luLXBhZ2luYXRpb24nXG4gIGNvbnN0IHBhZ2UgPSBOdW1iZXIob3B0aW9ucy5wYWdlIHx8IDEpXG4gIGNvbnN0IHRvdGFsID0gTWF0aC5tYXgoMSwgTnVtYmVyKG9wdGlvbnMudG90YWxQYWdlcyB8fCAxKSlcbiAgY29uc3QgZ28gPSAodGFyZ2V0OiBudW1iZXIpID0+IHtcbiAgICBjb25zdCBuZXh0ID0gTWF0aC5taW4oTWF0aC5tYXgoMSwgdGFyZ2V0KSwgdG90YWwpXG4gICAgaWYgKG5leHQgIT09IHBhZ2UpIG9wdGlvbnMub25QYWdlPy4obmV4dClcbiAgfVxuICBjb25zdCBtayA9IChsYWJlbDogc3RyaW5nLCB0YXJnZXQ6IG51bWJlciwgZGlzYWJsZWQgPSBmYWxzZSwgYWN0aXZlID0gZmFsc2UpID0+IHtcbiAgICBjb25zdCBidG4gPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdidXR0b24nKVxuICAgIGJ0bi50eXBlID0gJ2J1dHRvbidcbiAgICBidG4uY2xhc3NOYW1lID0gYG5vb3ItcGFnaW5hdGlvbl9fYnRuJHthY3RpdmUgPyAnIG5vb3ItcGFnaW5hdGlvbl9fcGFnZSBpcy1hY3RpdmUnIDogJyd9YFxuICAgIGJ0bi50ZXh0Q29udGVudCA9IGxhYmVsXG4gICAgYnRuLmRpc2FibGVkID0gZGlzYWJsZWRcbiAgICBidG4ub25jbGljayA9ICgpID0+ICFkaXNhYmxlZCAmJiBnbyh0YXJnZXQpXG4gICAgcmV0dXJuIGJ0blxuICB9XG4gIHdyYXAuYXBwZW5kKG1rKCfkuIrkuIDpobUnLCBwYWdlIC0gMSwgcGFnZSA8PSAxKSlcbiAgY29uc3Qgc2libGluZ0NvdW50ID0gTWF0aC5tYXgoMSwgTnVtYmVyKG9wdGlvbnMuc2libGluZ0NvdW50ID8/IDIpKVxuICBjb25zdCBzdGFydCA9IE1hdGgubWF4KDEsIHBhZ2UgLSBzaWJsaW5nQ291bnQpXG4gIGNvbnN0IGVuZCA9IE1hdGgubWluKHRvdGFsLCBwYWdlICsgc2libGluZ0NvdW50KVxuICBmb3IgKGxldCBwID0gc3RhcnQ7IHAgPD0gZW5kOyBwKyspIHdyYXAuYXBwZW5kKG1rKFN0cmluZyhwKSwgcCwgZmFsc2UsIHAgPT09IHBhZ2UpKVxuICB3cmFwLmFwcGVuZChtaygn5LiL5LiA6aG1JywgcGFnZSArIDEsIHBhZ2UgPj0gdG90YWwpKVxuICBjb25zdCBvbktleWRvd24gPSAoZXZlbnQ6IEtleWJvYXJkRXZlbnQpID0+IHtcbiAgICBpZiAob3B0aW9ucy5rZXlib2FyZCA9PT0gZmFsc2UpIHJldHVyblxuICAgIGNvbnN0IHRhcmdldCA9IGV2ZW50LnRhcmdldCBhcyBIVE1MRWxlbWVudCB8IG51bGxcbiAgICBpZiAodGFyZ2V0ICYmIFsnSU5QVVQnLCAnVEVYVEFSRUEnLCAnU0VMRUNUJ10uaW5jbHVkZXModGFyZ2V0LnRhZ05hbWUpKSByZXR1cm5cbiAgICBpZiAoZXZlbnQua2V5ID09PSAnUGFnZVVwJykgeyBldmVudC5wcmV2ZW50RGVmYXVsdCgpOyBnbyhwYWdlIC0gMSkgfVxuICAgIGVsc2UgaWYgKGV2ZW50LmtleSA9PT0gJ1BhZ2VEb3duJykgeyBldmVudC5wcmV2ZW50RGVmYXVsdCgpOyBnbyhwYWdlICsgMSkgfVxuICAgIGVsc2UgaWYgKGV2ZW50LmtleSA9PT0gJ0hvbWUnKSB7IGV2ZW50LnByZXZlbnREZWZhdWx0KCk7IGdvKDEpIH1cbiAgICBlbHNlIGlmIChldmVudC5rZXkgPT09ICdFbmQnKSB7IGV2ZW50LnByZXZlbnREZWZhdWx0KCk7IGdvKHRvdGFsKSB9XG4gIH1cbiAgd2luZG93LmFkZEV2ZW50TGlzdGVuZXIoJ2tleWRvd24nLCBvbktleWRvd24pXG4gIDsod3JhcCBhcyBhbnkpLl9fbm9vckRpc3Bvc2UgPSAoKSA9PiB3aW5kb3cucmVtb3ZlRXZlbnRMaXN0ZW5lcigna2V5ZG93bicsIG9uS2V5ZG93bilcbiAgcmV0dXJuIHdyYXBcbn1cblxuZnVuY3Rpb24gbWFrZVN1Ym1pdEJ1dHRvbihvcHRpb25zOiBhbnkgPSB7fSkge1xuICBjb25zdCBidG4gPSBtYWtlQnV0dG9uKHsgbGFiZWw6ICcnLCB0b25lOiAncHJpbWFyeScsIGNsYXNzTmFtZTogWydub29yLXN1Ym1pdC1idG4nLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKSB9KVxuICBjb25zdCBiYXIgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdpJylcbiAgYmFyLmNsYXNzTmFtZSA9ICdub29yLXN1Ym1pdC1idG5fX2JhcidcbiAgY29uc3QgdGV4dCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3NwYW4nKVxuICB0ZXh0LmNsYXNzTmFtZSA9ICdub29yLXN1Ym1pdC1idG5fX3RleHQnXG4gIGJ0bi5hcHBlbmQoYmFyLCB0ZXh0KVxuICBjb25zdCBub3JtYWxpemUgPSAoc3RhdGU6IHN0cmluZykgPT4gc3RhdGUgPT09ICdzdWJtaXR0aW5nJyA/ICdydW5uaW5nJyA6IChzdGF0ZSB8fCAnaWRsZScpXG4gIGNvbnN0IGxhYmVsRm9yID0gKHN0YXRlOiBzdHJpbmcsIHByb2dyZXNzID0gMCwgbGFiZWwgPSAnJykgPT4ge1xuICAgIGlmIChsYWJlbCkgcmV0dXJuIGxhYmVsXG4gICAgaWYgKHN0YXRlID09PSAnc3VjY2VzcycpIHJldHVybiBvcHRpb25zLnN1Y2Nlc3NMYWJlbCB8fCAn5bey5a6M5oiQJ1xuICAgIGlmIChzdGF0ZSA9PT0gJ2Vycm9yJykgcmV0dXJuIG9wdGlvbnMuZXJyb3JMYWJlbCB8fCAn5aSx6LSlJ1xuICAgIGlmIChzdGF0ZSA9PT0gJ3J1bm5pbmcnKSByZXR1cm4gb3B0aW9ucy5zdWJtaXR0aW5nTGFiZWwgfHwgb3B0aW9ucy5ydW5uaW5nTGFiZWwgfHwgKHByb2dyZXNzID4gMCA/IGAke01hdGgucm91bmQocHJvZ3Jlc3MpfSVgIDogJ+aPkOS6pOS4rScpXG4gICAgcmV0dXJuIG9wdGlvbnMuaWRsZUxhYmVsIHx8IG9wdGlvbnMubGFiZWwgfHwgJ+aPkOS6pCdcbiAgfVxuICBjb25zdCBzZXRTdGF0ZSA9IChzdGF0ZTogc3RyaW5nLCBwcm9ncmVzcyA9IDAsIGxhYmVsID0gJycpID0+IHtcbiAgICBjb25zdCBuZXh0ID0gbm9ybWFsaXplKHN0YXRlKVxuICAgIGNvbnN0IHBjdCA9IE1hdGgubWF4KDAsIE1hdGgubWluKDEwMCwgTnVtYmVyKHByb2dyZXNzIHx8IDApKSlcbiAgICBidG4uZGF0YXNldC5zdGF0ZSA9IG5leHRcbiAgICBidG4uY2xhc3NMaXN0LnRvZ2dsZSgnaXMtcnVubmluZycsIG5leHQgPT09ICdydW5uaW5nJylcbiAgICBidG4uY2xhc3NMaXN0LnRvZ2dsZSgnaXMtc3VjY2VzcycsIG5leHQgPT09ICdzdWNjZXNzJylcbiAgICBidG4uY2xhc3NMaXN0LnRvZ2dsZSgnaXMtZXJyb3InLCBuZXh0ID09PSAnZXJyb3InKVxuICAgIGJ0bi5zdHlsZS5zZXRQcm9wZXJ0eSgnLS1zdWJtaXQtcHJvZ3Jlc3MnLCBgJHtwY3R9JWApXG4gICAgdGV4dC50ZXh0Q29udGVudCA9IGxhYmVsRm9yKG5leHQsIHBjdCwgbGFiZWwpXG4gICAgaWYgKG9wdGlvbnMuZGlzYWJsZVdoaWxlUnVubmluZyAhPT0gZmFsc2UgJiYgbmV4dCA9PT0gJ3J1bm5pbmcnKSBidG4uZGlzYWJsZWQgPSB0cnVlXG4gICAgZWxzZSBpZiAobmV4dCA9PT0gJ3N1Y2Nlc3MnICYmIG9wdGlvbnMuZGlzYWJsZU9uU3VjY2VzcyAhPT0gZmFsc2UpIGJ0bi5kaXNhYmxlZCA9IHRydWVcbiAgICBlbHNlIGJ0bi5kaXNhYmxlZCA9ICEhb3B0aW9ucy5kaXNhYmxlZFxuICB9XG4gIGJ0bi5vbmNsaWNrID0gZXZlbnQgPT4ge1xuICAgIGlmIChidG4uZGlzYWJsZWQpIHJldHVyblxuICAgIG9wdGlvbnMub25DbGljaz8uKGV2ZW50KVxuICB9XG4gIDsoYnRuIGFzIGFueSkuX19zZXRTdGF0ZSA9IHNldFN0YXRlXG4gIHNldFN0YXRlKG9wdGlvbnMuc3RhdHVzIHx8ICdpZGxlJywgTnVtYmVyKG9wdGlvbnMucHJvZ3Jlc3MgfHwgMCksIG9wdGlvbnMubGFiZWxPdmVycmlkZSB8fCAnJylcbiAgcmV0dXJuIGJ0blxufVxuXG5mdW5jdGlvbiBhcHBlbmRDaGlsZHJlbihwYXJlbnQ6IEhUTUxFbGVtZW50LCBjaGlsZHJlbj86IGFueSkge1xuICBpZiAoIWNoaWxkcmVuKSByZXR1cm4gcGFyZW50XG4gIGNvbnN0IGxpc3QgPSBBcnJheS5pc0FycmF5KGNoaWxkcmVuKSA/IGNoaWxkcmVuIDogW2NoaWxkcmVuXVxuICBmb3IgKGNvbnN0IGNoaWxkIG9mIGxpc3QpIHtcbiAgICBpZiAoIWNoaWxkKSBjb250aW51ZVxuICAgIGlmIChjaGlsZCBpbnN0YW5jZW9mIE5vZGUpIHBhcmVudC5hcHBlbmRDaGlsZChjaGlsZClcbiAgICBlbHNlIHBhcmVudC5hcHBlbmRDaGlsZChkb2N1bWVudC5jcmVhdGVUZXh0Tm9kZShTdHJpbmcoY2hpbGQpKSlcbiAgfVxuICByZXR1cm4gcGFyZW50XG59XG5cbmZ1bmN0aW9uIG1ha2VUb3BCYXIob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3QgYmFyID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgYmFyLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tdG9wYmFyJywgb3B0aW9ucy5jbGFzc05hbWUgfHwgJyddLmZpbHRlcihCb29sZWFuKS5qb2luKCcgJylcbiAgY29uc3QgdGFicyA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIHRhYnMuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXRvcGJhcl9fdGFicydcbiAgY29uc3QgYWN0aW9ucyA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGFjdGlvbnMuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXRvcGJhcl9fYWN0aW9ucydcbiAgYXBwZW5kQ2hpbGRyZW4odGFicywgb3B0aW9ucy50YWJzIHx8IG9wdGlvbnMubGVmdClcbiAgYXBwZW5kQ2hpbGRyZW4oYWN0aW9ucywgb3B0aW9ucy5hY3Rpb25zIHx8IG9wdGlvbnMucmlnaHQpXG4gIGJhci5hcHBlbmQodGFicywgYWN0aW9ucylcbiAgcmV0dXJuIHsgZWw6IGJhciwgdGFicywgYWN0aW9ucyB9XG59XG5cbmZ1bmN0aW9uIG1ha2VBY3Rpb25Sb3cob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3Qgcm93ID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgcm93LmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tYWN0aW9uLXJvdycsIG9wdGlvbnMuY2xhc3NOYW1lIHx8ICcnXS5maWx0ZXIoQm9vbGVhbikuam9pbignICcpXG4gIGFwcGVuZENoaWxkcmVuKHJvdywgb3B0aW9ucy5jaGlsZHJlbiB8fCBvcHRpb25zLml0ZW1zKVxuICByZXR1cm4gcm93XG59XG5cbmZ1bmN0aW9uIG1ha2VTdGF0Q2FyZChvcHRpb25zOiBhbnkgPSB7fSkge1xuICBjb25zdCBjYXJkID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudChvcHRpb25zLm9uQ2xpY2sgPyAnYnV0dG9uJyA6ICdkaXYnKSBhcyBIVE1MRWxlbWVudFxuICBjYXJkLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tc3RhdC1jYXJkJywgb3B0aW9ucy50b25lID8gYG5vb3ItcGx1Z2luLXN0YXQtY2FyZC0tJHtvcHRpb25zLnRvbmV9YCA6ICcnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBpZiAob3B0aW9ucy5vbkNsaWNrKSB7XG4gICAgOyhjYXJkIGFzIEhUTUxCdXR0b25FbGVtZW50KS50eXBlID0gJ2J1dHRvbidcbiAgICA7KGNhcmQgYXMgSFRNTEJ1dHRvbkVsZW1lbnQpLm9uY2xpY2sgPSBvcHRpb25zLm9uQ2xpY2tcbiAgfVxuICBjb25zdCBsYWJlbCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3NwYW4nKVxuICBsYWJlbC5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tc3RhdC1jYXJkX19sYWJlbCdcbiAgbGFiZWwudGV4dENvbnRlbnQgPSBvcHRpb25zLmxhYmVsIHx8ICcnXG4gIGNvbnN0IHZhbHVlID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc3Ryb25nJylcbiAgdmFsdWUuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXN0YXQtY2FyZF9fdmFsdWUnXG4gIHZhbHVlLnRleHRDb250ZW50ID0gU3RyaW5nKG9wdGlvbnMudmFsdWUgPz8gJy0nKVxuICBjYXJkLmFwcGVuZChsYWJlbCwgdmFsdWUpXG4gIGlmIChvcHRpb25zLmhpbnQpIHtcbiAgICBjb25zdCBoaW50ID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc21hbGwnKVxuICAgIGhpbnQuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXN0YXQtY2FyZF9faGludCdcbiAgICBoaW50LnRleHRDb250ZW50ID0gU3RyaW5nKG9wdGlvbnMuaGludClcbiAgICBjYXJkLmFwcGVuZENoaWxkKGhpbnQpXG4gIH1cbiAgcmV0dXJuIGNhcmRcbn1cblxuZnVuY3Rpb24gbWFrZVN0YXRHcmlkKG9wdGlvbnM6IGFueSA9IHt9KSB7XG4gIGNvbnN0IGdyaWQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBncmlkLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tc3RhdC1ncmlkJywgb3B0aW9ucy5jbGFzc05hbWUgfHwgJyddLmZpbHRlcihCb29sZWFuKS5qb2luKCcgJylcbiAgY29uc3QgaXRlbXMgPSBBcnJheS5pc0FycmF5KG9wdGlvbnMuaXRlbXMpID8gb3B0aW9ucy5pdGVtcyA6IFtdXG4gIGZvciAoY29uc3QgaXRlbSBvZiBpdGVtcykgZ3JpZC5hcHBlbmRDaGlsZChtYWtlU3RhdENhcmQoaXRlbSkpXG4gIHJldHVybiBncmlkXG59XG5cbmZ1bmN0aW9uIG1ha2VNZWRpYUNhcmQob3B0aW9uczogYW55ID0ge30pIHtcbiAgY29uc3QgY2FyZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQob3B0aW9ucy5vbkNsaWNrID8gJ2J1dHRvbicgOiBvcHRpb25zLmhyZWYgPyAnYScgOiAnZGl2JykgYXMgSFRNTEVsZW1lbnRcbiAgY2FyZC5jbGFzc05hbWUgPSBbJ25vb3ItcGx1Z2luLW1lZGlhLWNhcmQnLCBvcHRpb25zLnNoYXJwID8gJ25vb3ItcGx1Z2luLW1lZGlhLWNhcmQtLXNoYXJwJyA6ICcnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBpZiAob3B0aW9ucy5ocmVmKSB7XG4gICAgOyhjYXJkIGFzIEhUTUxBbmNob3JFbGVtZW50KS5ocmVmID0gb3B0aW9ucy5ocmVmXG4gICAgOyhjYXJkIGFzIEhUTUxBbmNob3JFbGVtZW50KS50YXJnZXQgPSBvcHRpb25zLnRhcmdldCB8fCAnX3NlbGYnXG4gIH1cbiAgaWYgKG9wdGlvbnMub25DbGljaykge1xuICAgIDsoY2FyZCBhcyBIVE1MQnV0dG9uRWxlbWVudCkudHlwZSA9ICdidXR0b24nXG4gICAgOyhjYXJkIGFzIEhUTUxCdXR0b25FbGVtZW50KS5vbmNsaWNrID0gb3B0aW9ucy5vbkNsaWNrXG4gIH1cbiAgY29uc3QgY292ZXIgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBjb3Zlci5jbGFzc05hbWUgPSBbJ25vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX2NvdmVyJywgb3B0aW9ucy5jb3Zlck9uQ2xpY2sgPyAnaXMtY2xpY2thYmxlJyA6ICcnXS5maWx0ZXIoQm9vbGVhbikuam9pbignICcpXG4gIGlmIChvcHRpb25zLmNvdmVyT25DbGljaykgY292ZXIub25jbGljayA9IChlKSA9PiB7IGUuc3RvcFByb3BhZ2F0aW9uKCk7IG9wdGlvbnMuY292ZXJPbkNsaWNrKCkgfVxuICBpZiAob3B0aW9ucy5pbWFnZSB8fCBvcHRpb25zLmNvdmVyIHx8IG9wdGlvbnMuY292ZXJVcmwpIHtcbiAgICBjb25zdCBpbWcgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdpbWcnKVxuICAgIGltZy5zcmMgPSBvcHRpb25zLmltYWdlIHx8IG9wdGlvbnMuY292ZXIgfHwgb3B0aW9ucy5jb3ZlclVybFxuICAgIGltZy5sb2FkaW5nID0gb3B0aW9ucy5sb2FkaW5nIHx8ICdsYXp5J1xuICAgIGNvdmVyLmFwcGVuZENoaWxkKGltZylcbiAgfSBlbHNlIHtcbiAgICBjb25zdCBwaCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgcGguY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX3BsYWNlaG9sZGVyJ1xuICAgIHBoLnRleHRDb250ZW50ID0gb3B0aW9ucy5wbGFjZWhvbGRlciB8fCAnTk8gSU1BR0UnXG4gICAgY292ZXIuYXBwZW5kQ2hpbGQocGgpXG4gIH1cbiAgY29uc3QgYm9keSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gIGJvZHkuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX2JvZHknXG4gIGNvbnN0IHRpdGxlID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgdGl0bGUuY2xhc3NOYW1lID0gWydub29yLXBsdWdpbi1tZWRpYS1jYXJkX190aXRsZScsIG9wdGlvbnMudGl0bGVPbkNsaWNrID8gJ2lzLWNsaWNrYWJsZScgOiAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICB0aXRsZS50ZXh0Q29udGVudCA9IG9wdGlvbnMudGl0bGUgfHwgJydcbiAgaWYgKG9wdGlvbnMudGl0bGVPbkNsaWNrKSB0aXRsZS5vbmNsaWNrID0gKGUpID0+IHsgZS5zdG9wUHJvcGFnYXRpb24oKTsgb3B0aW9ucy50aXRsZU9uQ2xpY2soKSB9XG4gIGJvZHkuYXBwZW5kQ2hpbGQodGl0bGUpXG4gIGlmIChvcHRpb25zLm1ldGEpIHtcbiAgICBjb25zdCBtZXRhID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2JylcbiAgICBtZXRhLmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1tZWRpYS1jYXJkX19tZXRhJ1xuICAgIGNvbnN0IG1ldGFJdGVtcyA9IEFycmF5LmlzQXJyYXkob3B0aW9ucy5tZXRhKSA/IG9wdGlvbnMubWV0YSA6IFtvcHRpb25zLm1ldGFdXG4gICAgZm9yIChjb25zdCB0ZXh0IG9mIG1ldGFJdGVtcy5maWx0ZXIoQm9vbGVhbikpIHtcbiAgICAgIGNvbnN0IHNwYW4gPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzcGFuJylcbiAgICAgIHNwYW4udGV4dENvbnRlbnQgPSBTdHJpbmcodGV4dClcbiAgICAgIG1ldGEuYXBwZW5kQ2hpbGQoc3BhbilcbiAgICB9XG4gICAgYm9keS5hcHBlbmRDaGlsZChtZXRhKVxuICB9XG4gIGlmIChvcHRpb25zLmJhZGdlcykge1xuICAgIGNvbnN0IGJhZGdlcyA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgYmFkZ2VzLmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1tZWRpYS1jYXJkX19iYWRnZXMnXG4gICAgYXBwZW5kQ2hpbGRyZW4oYmFkZ2VzLCBvcHRpb25zLmJhZGdlcylcbiAgICBib2R5LmFwcGVuZENoaWxkKGJhZGdlcylcbiAgfVxuICBpZiAob3B0aW9ucy5hY3Rpb25zKSB7XG4gICAgY29uc3QgYWN0aW9ucyA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgYWN0aW9ucy5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fYWN0aW9ucydcbiAgICBhcHBlbmRDaGlsZHJlbihhY3Rpb25zLCBvcHRpb25zLmFjdGlvbnMpXG4gICAgYm9keS5hcHBlbmRDaGlsZChhY3Rpb25zKVxuICB9XG4gIGNhcmQuYXBwZW5kKGNvdmVyLCBib2R5KVxuICByZXR1cm4gY2FyZFxufVxuXG5mdW5jdGlvbiBtYWtlTG9hZGluZ1N0YXRlKG9wdGlvbnM6IGFueSA9IHt9KSB7XG4gIGNvbnN0IGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBkLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tc3RhdGUnLCAnbm9vci1wbHVnaW4tc3RhdGUtLWxvYWRpbmcnLCBvcHRpb25zLmNsYXNzTmFtZSB8fCAnJ10uZmlsdGVyKEJvb2xlYW4pLmpvaW4oJyAnKVxuICBjb25zdCBzcGlubmVyID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnc3BhbicpXG4gIHNwaW5uZXIuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLXNwaW5uZXInXG4gIGNvbnN0IHRleHQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdzcGFuJylcbiAgdGV4dC50ZXh0Q29udGVudCA9IG9wdGlvbnMudGV4dCB8fCAn5Yqg6L295Lit4oCmJ1xuICBkLmFwcGVuZChzcGlubmVyLCB0ZXh0KVxuICByZXR1cm4gZFxufVxuXG5mdW5jdGlvbiBsYXN0U2F2ZXBhdGhLZXkoZG93bmxvYWRlcklkOiBzdHJpbmcpIHtcbiAgcmV0dXJuIGBub29yOmxhc3QtZG93bmxvYWQtc2F2ZXBhdGg6JHtkb3dubG9hZGVySWQgfHwgJ2RlZmF1bHQnfWBcbn1cblxuZnVuY3Rpb24gcmVhZExhc3RTYXZlcGF0aChkb3dubG9hZGVySWQ6IHN0cmluZykge1xuICB0cnkgeyByZXR1cm4gbG9jYWxTdG9yYWdlLmdldEl0ZW0obGFzdFNhdmVwYXRoS2V5KGRvd25sb2FkZXJJZCkpIHx8ICcnIH0gY2F0Y2ggeyByZXR1cm4gJycgfVxufVxuXG5mdW5jdGlvbiB3cml0ZUxhc3RTYXZlcGF0aChkb3dubG9hZGVySWQ6IHN0cmluZywgdmFsdWU6IHN0cmluZykge1xuICB0cnkge1xuICAgIGlmICh2YWx1ZSkgbG9jYWxTdG9yYWdlLnNldEl0ZW0obGFzdFNhdmVwYXRoS2V5KGRvd25sb2FkZXJJZCksIHZhbHVlKVxuICB9IGNhdGNoIHt9XG59XG5cbmZ1bmN0aW9uIGVzY2FwZUh0bWwodmFsdWU6IGFueSkge1xuICByZXR1cm4gU3RyaW5nKHZhbHVlID8/ICcnKS5yZXBsYWNlKC9bJjw+J1wiXS9nLCBjID0+ICh7ICcmJzogJyZhbXA7JywgJzwnOiAnJmx0OycsICc+JzogJyZndDsnLCBcIidcIjogJyYjMzk7JywgJ1wiJzogJyZxdW90OycgfVtjXSEpKVxufVxuXG5mdW5jdGlvbiByZW5kZXJSZXNvdXJjZVByZXZpZXcocmVzb3VyY2VTdGF0ZTogYW55KSB7XG4gIGNvbnN0IGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKVxuICBkLmNsYXNzTmFtZSA9ICdub29yLWRvd25sb2FkZXItcHJldmlldydcbiAgaWYgKCFyZXNvdXJjZVN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX3Jlc291cmNlX3ByZXZpZXcpIHJldHVybiBkXG4gIGlmIChyZXNvdXJjZVN0YXRlLmxvYWRpbmcpIHtcbiAgICBkLmlubmVySFRNTCA9ICc8ZGl2IGNsYXNzPVwibm9vci1kb3dubG9hZGVyLXByZXZpZXdfX2hlYWRcIj48c3Bhbj7otYTmupDpooTop4g8L3NwYW4+PGVtPuivu+WPluS4rS4uLjwvZW0+PC9kaXY+J1xuICAgIHJldHVybiBkXG4gIH1cbiAgaWYgKHJlc291cmNlU3RhdGUuZXJyb3IpIHtcbiAgICBkLmlubmVySFRNTCA9IGA8ZGl2IGNsYXNzPVwibm9vci1kb3dubG9hZGVyLXByZXZpZXdfX2hlYWRcIj48c3Bhbj7otYTmupDpooTop4g8L3NwYW4+PGVtIGNsYXNzPVwiaXMtZXJyb3JcIj4ke2VzY2FwZUh0bWwocmVzb3VyY2VTdGF0ZS5lcnJvcil9PC9lbT48L2Rpdj5gXG4gICAgcmV0dXJuIGRcbiAgfVxuICBjb25zdCBmaWxlcyA9IEFycmF5LmlzQXJyYXkocmVzb3VyY2VTdGF0ZS5kYXRhPy5maWxlcykgPyByZXNvdXJjZVN0YXRlLmRhdGEuZmlsZXMgOiBbXVxuICBpZiAoIWZpbGVzLmxlbmd0aCkge1xuICAgIGQuaW5uZXJIVE1MID0gJzxkaXYgY2xhc3M9XCJub29yLWRvd25sb2FkZXItcHJldmlld19faGVhZFwiPjxzcGFuPui1hOa6kOmihOiniDwvc3Bhbj48ZW0+5pqC5peg5paH5Lu25L+h5oGvPC9lbT48L2Rpdj4nXG4gICAgcmV0dXJuIGRcbiAgfVxuICBjb25zdCB2aXNpYmxlID0gZmlsZXMuc2xpY2UoMCwgNilcbiAgZC5pbm5lckhUTUwgPSBgPGRpdiBjbGFzcz1cIm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19oZWFkXCI+PHNwYW4+6LWE5rqQ6aKE6KeIPC9zcGFuPjxlbT4ke2VzY2FwZUh0bWwocmVzb3VyY2VTdGF0ZS5kYXRhPy50b3RhbF9zaXplX2Zvcm1hdHRlZCB8fCAnJyl9IMK3ICR7ZmlsZXMubGVuZ3RofSDkuKrmlofku7Y8L2VtPjwvZGl2PlxuICA8ZGl2IGNsYXNzPVwibm9vci1kb3dubG9hZGVyLXByZXZpZXdfX2ZpbGVzXCI+JHt2aXNpYmxlLm1hcCgoZmlsZTogYW55KSA9PiBgPGRpdiBjbGFzcz1cIm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19maWxlXCI+PHNwYW4+JHtlc2NhcGVIdG1sKGZpbGUubmFtZSB8fCBmaWxlLmZ1bGxfcGF0aCB8fCAnJyl9PC9zcGFuPjxlbT4ke2VzY2FwZUh0bWwoZmlsZS5zaXplX2Zvcm1hdHRlZCB8fCAnJyl9PC9lbT48L2Rpdj5gKS5qb2luKCcnKX0ke2ZpbGVzLmxlbmd0aCA+IHZpc2libGUubGVuZ3RoID8gYDxkaXYgY2xhc3M9XCJub29yLWRvd25sb2FkZXItcHJldmlld19fbW9yZVwiPui/mOaciSAke2ZpbGVzLmxlbmd0aCAtIHZpc2libGUubGVuZ3RofSDkuKrmlofku7Y8L2Rpdj5gIDogJyd9PC9kaXY+YFxuICByZXR1cm4gZFxufVxuXG5mdW5jdGlvbiBjcmVhdGVEb3dubG9hZGVyRGlhbG9nQ29udGV4dChzb3VyY2VQbHVnaW5JZDogc3RyaW5nKSB7XG4gIGxldCBwcm9ncmVzc1RpbWVyOiBudW1iZXIgfCBudWxsID0gbnVsbFxuXG4gIGFzeW5jIGZ1bmN0aW9uIHBvc3RKc29uKHVybDogc3RyaW5nLCBwYXlsb2FkOiBhbnkpIHtcbiAgICBjb25zdCByZXMgPSBhd2FpdCBmZXRjaCh1cmwsIHtcbiAgICAgIG1ldGhvZDogJ1BPU1QnLFxuICAgICAgaGVhZGVyczogeyAnQ29udGVudC1UeXBlJzogJ2FwcGxpY2F0aW9uL2pzb24nIH0sXG4gICAgICBib2R5OiBKU09OLnN0cmluZ2lmeSh7IHBheWxvYWQgfSksXG4gICAgfSlcbiAgICBjb25zdCBkYXRhID0gYXdhaXQgcmVzLmpzb24oKS5jYXRjaCgoKSA9PiAoe30pKVxuICAgIGlmICghcmVzLm9rIHx8IGRhdGE/Lm9rID09PSBmYWxzZSkgdGhyb3cgbmV3IEVycm9yKGRhdGE/LmRldGFpbCB8fCBkYXRhPy5tZXNzYWdlIHx8ICfor7fmsYLlpLHotKUnKVxuICAgIHJldHVybiBkYXRhXG4gIH1cblxuICBhc3luYyBmdW5jdGlvbiBvcGVuKG9wdGlvbnM6IGFueSA9IHt9KSB7XG4gICAgY29uc3QgYWxsb3dCYXRjaFVybHMgPSAhIW9wdGlvbnMuYWxsb3dCYXRjaFVybHNcbiAgICBjb25zdCBzaG93RG93bmxvYWRlckZpZWxkID0gb3B0aW9ucy5zaG93RG93bmxvYWRlckZpZWxkICE9PSBmYWxzZVxuICAgIGNvbnN0IHByZXZpZXdFbmFibGVkID0gb3B0aW9ucy5wcmV2aWV3ICE9PSBmYWxzZVxuICAgIGNvbnN0IG1heFVybHMgPSBOdW1iZXIob3B0aW9ucy5tYXhVcmxzIHx8IDApXG4gICAgY29uc3Qgc3VibWl0SWRsZUxhYmVsID0gU3RyaW5nKG9wdGlvbnMuc3VibWl0SWRsZUxhYmVsIHx8IChhbGxvd0JhdGNoVXJscyA/ICfliJvlu7rku7vliqEnIDogJ+aOqOmAgeS4i+i9vScpKVxuICAgIGNvbnN0IHN1Ym1pdFN1Y2Nlc3NMYWJlbCA9IFN0cmluZyhvcHRpb25zLnN1Ym1pdFN1Y2Nlc3NMYWJlbCB8fCAoYWxsb3dCYXRjaFVybHMgPyAn5Yib5bu65oiQ5YqfJyA6ICfmjqjpgIHmiJDlip8nKSlcbiAgICBjb25zdCBzdWJtaXRFcnJvckxhYmVsID0gU3RyaW5nKG9wdGlvbnMuc3VibWl0RXJyb3JMYWJlbCB8fCAoYWxsb3dCYXRjaFVybHMgPyAn5Yib5bu65aSx6LSlJyA6ICfmjqjpgIHlpLHotKUnKSlcbiAgICBjb25zdCBzdWJtaXRQYXJ0aWFsTGFiZWwgPSBTdHJpbmcob3B0aW9ucy5zdWJtaXRQYXJ0aWFsTGFiZWwgfHwgJ+mDqOWIhuWksei0pScpXG4gICAgY29uc3Qgc3RhdGU6IGFueSA9IHtcbiAgICAgIGRvd25sb2FkZXJJZDogU3RyaW5nKG9wdGlvbnMuZG93bmxvYWRlcklkIHx8ICcnKS50cmltKCksXG4gICAgICB0aXRsZTogU3RyaW5nKG9wdGlvbnMudGl0bGUgfHwgJycpLFxuICAgICAgbmFtZTogU3RyaW5nKG9wdGlvbnMubmFtZSB8fCBvcHRpb25zLnJlbmFtZSB8fCBvcHRpb25zLnRpdGxlIHx8ICcnKSxcbiAgICAgIHJlbmFtZTogU3RyaW5nKG9wdGlvbnMucmVuYW1lIHx8IG9wdGlvbnMubmFtZSB8fCBvcHRpb25zLnRpdGxlIHx8ICcnKSxcbiAgICAgIHRpdGxlT3B0aW9uczogQXJyYXkuaXNBcnJheShvcHRpb25zLnRpdGxlT3B0aW9ucykgPyBvcHRpb25zLnRpdGxlT3B0aW9ucy5maWx0ZXIoQm9vbGVhbikgOiBbXSxcbiAgICAgIHRpdGxlTW9kZTogU3RyaW5nKG9wdGlvbnMudGl0bGVNb2RlIHx8ICcnKSxcbiAgICAgIHVybDogU3RyaW5nKG9wdGlvbnMudXJsIHx8IG9wdGlvbnMubWFnbmV0IHx8IG9wdGlvbnMudXJscyB8fCAnJyksXG4gICAgICB1cmxzVGV4dDogU3RyaW5nKG9wdGlvbnMudXJsc1RleHQgfHwgb3B0aW9ucy51cmxzIHx8IG9wdGlvbnMudXJsIHx8IG9wdGlvbnMubWFnbmV0IHx8ICcnKSxcbiAgICAgIGl0ZW1UaXRsZTogU3RyaW5nKG9wdGlvbnMuaXRlbVRpdGxlIHx8IG9wdGlvbnMudGl0bGUgfHwgJycpLFxuICAgICAgZmlsZUluZGljZXM6ICdhdXRvJyxcbiAgICAgIHNhdmVwYXRoOiAnJyxcbiAgICAgIHNlbGVjdGVkUGF0aDogJycsXG4gICAgICBjYXRlZ29yeTogJycsXG4gICAgICBtaW5GaWxlU2l6ZU1iOiAnJyxcbiAgICAgIG9wdGlvbnM6IG51bGwsXG4gICAgICBlcnJvcjogJycsXG4gICAgICBsb2FkaW5nOiB0cnVlLFxuICAgICAgcHJldmlld0xvYWRpbmc6IGZhbHNlLFxuICAgICAgcHJldmlld0Vycm9yOiAnJyxcbiAgICAgIHByZXZpZXdEYXRhOiBudWxsLFxuICAgICAgc3VibWl0U3RhdHVzOiAnaWRsZScsXG4gICAgICBzdWJtaXRQcm9ncmVzczogMCxcbiAgICAgIHN1Ym1pdHRpbmc6IGZhbHNlLFxuICAgICAgc3VibWl0QnV0dG9uOiBudWxsIGFzIGFueSxcbiAgICB9XG5cbiAgICBpZiAoIXN0YXRlLmRvd25sb2FkZXJJZCkgdGhyb3cgbmV3IEVycm9yKCfmnKrnu5HlrprkuIvovb3lmagnKVxuICAgIGlmICghYWxsb3dCYXRjaFVybHMgJiYgIXN0YXRlLnVybCkgdGhyb3cgbmV3IEVycm9yKCfnvLrlsJHkuIvovb3pk77mjqUnKVxuICAgIGlmICghc3RhdGUudGl0bGVNb2RlICYmIHN0YXRlLnRpdGxlT3B0aW9ucy5sZW5ndGgpIHN0YXRlLnRpdGxlTW9kZSA9IFN0cmluZyhzdGF0ZS50aXRsZU9wdGlvbnNbMF0/LmtleSB8fCAnJylcblxuICAgIGNvbnN0IG1vZGFsID0gbWFrZU1vZGFsKHtcbiAgICAgIHRpdGxlOiBTdHJpbmcob3B0aW9ucy5tb2RhbFRpdGxlIHx8IChhbGxvd0JhdGNoVXJscyA/ICfmlrDlu7rkuIvovb3ku7vliqEnIDogJ+aOqOmAgeS4i+i9vScpKSxcbiAgICAgIHdpZHRoOiAnbWQnLFxuICAgICAgY2xvc2VPbk1hc2s6IGZhbHNlLFxuICAgICAgb25DbG9zZTogKCkgPT4ge1xuICAgICAgICBpZiAoc3RhdGUuc3VibWl0dGluZykgcmV0dXJuXG4gICAgICAgIGlmIChwcm9ncmVzc1RpbWVyKSB3aW5kb3cuY2xlYXJJbnRlcnZhbChwcm9ncmVzc1RpbWVyKVxuICAgICAgfSxcbiAgICB9KVxuXG4gICAgYXN5bmMgZnVuY3Rpb24gbG9hZE9wdGlvbnMoKSB7XG4gICAgICBzdGF0ZS5sb2FkaW5nID0gdHJ1ZVxuICAgICAgc3RhdGUuZXJyb3IgPSAnJ1xuICAgICAgcmVuZGVyKClcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IGluZm9SZXMgPSBhd2FpdCBhcGkuZ2V0KGAvcGx1Z2lucy8ke3N0YXRlLmRvd25sb2FkZXJJZH0vY29uZmlnYCkudGhlbihyID0+IHIuZGF0YSkuY2F0Y2goKCkgPT4gbnVsbClcbiAgICAgICAgY29uc3QgZGxPcHRpb25zID0gYXdhaXQgcG9zdEpzb24oYC9hcGkvcGx1Z2lucy8ke3N0YXRlLmRvd25sb2FkZXJJZH0vYWN0aW9ucy9kb3dubG9hZF9vcHRpb25zYCwge30pXG4gICAgICAgIHN0YXRlLm9wdGlvbnMgPSBkbE9wdGlvbnNcbiAgICAgICAgc3RhdGUuZG93bmxvYWRlck5hbWUgPSBpbmZvUmVzPy5wbHVnaW4/Lm5hbWUgfHwgZGxPcHRpb25zLmRvd25sb2FkZXIgfHwgc3RhdGUuZG93bmxvYWRlcklkXG4gICAgICAgIHN0YXRlLmZpbGVJbmRpY2VzID0gU3RyaW5nKGRsT3B0aW9ucy5maWxlX2luZGljZXMgfHwgc3RhdGUuZmlsZUluZGljZXMgfHwgJ2F1dG8nKVxuICAgICAgICBzdGF0ZS5jYXRlZ29yeSA9IFN0cmluZyhkbE9wdGlvbnMuZGVmYXVsdF9jYXRlZ29yeSB8fCAnJylcbiAgICAgICAgc3RhdGUuc2F2ZXBhdGggPSByZWFkTGFzdFNhdmVwYXRoKHN0YXRlLmRvd25sb2FkZXJJZCkgfHwgU3RyaW5nKGRsT3B0aW9ucy5kZWZhdWx0X3NhdmVwYXRoIHx8ICcnKVxuICAgICAgICBzdGF0ZS5zZWxlY3RlZFBhdGggPSBzdGF0ZS5zYXZlcGF0aFxuICAgICAgICBpZiAoZGxPcHRpb25zLnNtYWxsX2ZpbGVfZmlsdGVyICYmIHR5cGVvZiBkbE9wdGlvbnMuc21hbGxfZmlsZV9maWx0ZXIgPT09ICdvYmplY3QnKSB7XG4gICAgICAgICAgY29uc3QgcmF3ID0gZGxPcHRpb25zLnNtYWxsX2ZpbGVfZmlsdGVyLmRlZmF1bHRfbWJcbiAgICAgICAgICBzdGF0ZS5taW5GaWxlU2l6ZU1iID0gcmF3ID09PSB1bmRlZmluZWQgfHwgcmF3ID09PSBudWxsIHx8IHJhdyA9PT0gJycgPyAnJyA6IFN0cmluZyhyYXcpXG4gICAgICAgIH1cbiAgICAgICAgY29uc3QgZm91bmQgPSAoZGxPcHRpb25zLmNhdGVnb3JpZXMgfHwgW10pLmZpbmQoKGl0ZW06IGFueSkgPT4gaXRlbS5uYW1lID09PSBzdGF0ZS5jYXRlZ29yeSlcbiAgICAgICAgaWYgKGZvdW5kPy5zYXZlX3BhdGggJiYgIXN0YXRlLnNhdmVwYXRoKSBzdGF0ZS5zYXZlcGF0aCA9IFN0cmluZyhmb3VuZC5zYXZlX3BhdGgpXG4gICAgICAgIGlmICghc3RhdGUuc2F2ZXBhdGgpIHtcbiAgICAgICAgICBjb25zdCBmaXJzdFBhdGggPSBBcnJheS5pc0FycmF5KGRsT3B0aW9ucy5wYXRocykgPyBkbE9wdGlvbnMucGF0aHMuZmluZCgoaXRlbTogYW55KSA9PiBpdGVtPy5wYXRoKT8ucGF0aCA6ICcnXG4gICAgICAgICAgaWYgKGZpcnN0UGF0aCkge1xuICAgICAgICAgICAgc3RhdGUuc2F2ZXBhdGggPSBTdHJpbmcoZmlyc3RQYXRoKVxuICAgICAgICAgICAgc3RhdGUuc2VsZWN0ZWRQYXRoID0gc3RhdGUuc2F2ZXBhdGhcbiAgICAgICAgICB9XG4gICAgICAgIH1cbiAgICAgICAgaWYgKHByZXZpZXdFbmFibGVkICYmIGRsT3B0aW9ucy5zdXBwb3J0c19yZXNvdXJjZV9wcmV2aWV3ICYmICFhbGxvd0JhdGNoVXJscyAmJiBzdGF0ZS51cmwpIGF3YWl0IGxvYWRQcmV2aWV3KClcbiAgICAgIH0gY2F0Y2ggKGU6IGFueSkge1xuICAgICAgICBzdGF0ZS5lcnJvciA9IGU/Lm1lc3NhZ2UgfHwgJ+S4i+i9veWZqOmFjee9ruivu+WPluWksei0pSdcbiAgICAgICAgc3RhdGUub3B0aW9ucyA9IHsgY2F0ZWdvcmllczogW10gfVxuICAgICAgfSBmaW5hbGx5IHtcbiAgICAgICAgc3RhdGUubG9hZGluZyA9IGZhbHNlXG4gICAgICAgIHJlbmRlcigpXG4gICAgICB9XG4gICAgfVxuXG4gICAgYXN5bmMgZnVuY3Rpb24gbG9hZFByZXZpZXcoKSB7XG4gICAgICBpZiAoIXN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX3Jlc291cmNlX3ByZXZpZXcpIHJldHVyblxuICAgICAgc3RhdGUucHJldmlld0xvYWRpbmcgPSB0cnVlXG4gICAgICBzdGF0ZS5wcmV2aWV3RXJyb3IgPSAnJ1xuICAgICAgc3RhdGUucHJldmlld0RhdGEgPSBudWxsXG4gICAgICByZW5kZXIoKVxuICAgICAgdHJ5IHtcbiAgICAgICAgY29uc3QgcHJldmlld1VybCA9IFN0cmluZyhzdGF0ZS51cmwgfHwgc3RhdGUudXJsc1RleHQgfHwgJycpLnNwbGl0KC9cXHI/XFxuLykubWFwKChpdGVtOiBzdHJpbmcpID0+IGl0ZW0udHJpbSgpKS5maWx0ZXIoQm9vbGVhbilbMF0gfHwgJydcbiAgICAgICAgaWYgKCFwcmV2aWV3VXJsKSByZXR1cm5cbiAgICAgICAgc3RhdGUucHJldmlld0RhdGEgPSBhd2FpdCBwb3N0SnNvbihgL2FwaS9wbHVnaW5zLyR7c3RhdGUuZG93bmxvYWRlcklkfS9hY3Rpb25zL3Jlc291cmNlX2luZm9gLCB7IHVybDogcHJldmlld1VybCwgbWFnbmV0OiBwcmV2aWV3VXJsIH0pXG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgc3RhdGUucHJldmlld0Vycm9yID0gZT8ubWVzc2FnZSB8fCAn6LWE5rqQ6aKE6KeI5aSx6LSlJ1xuICAgICAgfSBmaW5hbGx5IHtcbiAgICAgICAgc3RhdGUucHJldmlld0xvYWRpbmcgPSBmYWxzZVxuICAgICAgICByZW5kZXIoKVxuICAgICAgfVxuICAgIH1cblxuICAgIGFzeW5jIGZ1bmN0aW9uIHN1Ym1pdCgpIHtcbiAgICAgIGlmIChzdGF0ZS5zdWJtaXR0aW5nKSByZXR1cm5cbiAgICAgIHN0YXRlLnN1Ym1pdHRpbmcgPSB0cnVlXG4gICAgICBzdGF0ZS5zdWJtaXRTdGF0dXMgPSAncnVubmluZydcbiAgICAgIHN0YXRlLnN1Ym1pdFByb2dyZXNzID0gOFxuICAgICAgc3RhdGUuZXJyb3IgPSAnJ1xuICAgICAgc3RhdGUuc3VibWl0QnV0dG9uPy5fX3NldFN0YXRlPy4oJ3J1bm5pbmcnLCA4LCAnOCUnKVxuICAgICAgcmVuZGVyKClcbiAgICAgIHByb2dyZXNzVGltZXIgPSB3aW5kb3cuc2V0SW50ZXJ2YWwoKCkgPT4ge1xuICAgICAgICBpZiAoIXN0YXRlLnN1Ym1pdHRpbmcgfHwgc3RhdGUuc3VibWl0U3RhdHVzICE9PSAncnVubmluZycpIHJldHVyblxuICAgICAgICBzdGF0ZS5zdWJtaXRQcm9ncmVzcyA9IE1hdGgubWluKDkyLCBOdW1iZXIoc3RhdGUuc3VibWl0UHJvZ3Jlc3MgfHwgMCkgKyA4KVxuICAgICAgICBzdGF0ZS5zdWJtaXRCdXR0b24/Ll9fc2V0U3RhdGU/LigncnVubmluZycsIHN0YXRlLnN1Ym1pdFByb2dyZXNzLCBgJHtNYXRoLnJvdW5kKHN0YXRlLnN1Ym1pdFByb2dyZXNzKX0lYClcbiAgICAgIH0sIDE4MClcbiAgICAgIHRyeSB7XG4gICAgICAgIGNvbnN0IHVybExpc3QgPSBTdHJpbmcoYWxsb3dCYXRjaFVybHMgPyBzdGF0ZS51cmxzVGV4dCA6IChzdGF0ZS51cmwgfHwgc3RhdGUudXJsc1RleHQgfHwgJycpKVxuICAgICAgICAgIC5zcGxpdCgvXFxyP1xcbi8pXG4gICAgICAgICAgLm1hcCgoaXRlbTogc3RyaW5nKSA9PiBpdGVtLnRyaW0oKSlcbiAgICAgICAgICAuZmlsdGVyKEJvb2xlYW4pXG4gICAgICAgIGlmICghdXJsTGlzdC5sZW5ndGgpIHRocm93IG5ldyBFcnJvcign6K+35aGr5YaZ5LiL6L296ZO+5o6lJylcbiAgICAgICAgaWYgKG1heFVybHMgPiAwICYmIHVybExpc3QubGVuZ3RoID4gbWF4VXJscykgdGhyb3cgbmV3IEVycm9yKGDljZXmrKHmnIDlpJrmt7vliqAgJHttYXhVcmxzfSDmnaHpk77mjqVgKVxuICAgICAgICBjb25zdCBmaXJzdFVybCA9IHVybExpc3RbMF0gfHwgJydcbiAgICAgICAgY29uc3QgcGF5bG9hZCA9IHtcbiAgICAgICAgICB1cmw6IGZpcnN0VXJsLFxuICAgICAgICAgIHVybHM6IGFsbG93QmF0Y2hVcmxzID8gdXJsTGlzdC5qb2luKCdcXG4nKSA6IGZpcnN0VXJsLFxuICAgICAgICAgIG1hZ25ldDogZmlyc3RVcmwsXG4gICAgICAgICAgdGl0bGU6IHN0YXRlLnRpdGxlLFxuICAgICAgICAgIG5hbWU6IHN0YXRlLm5hbWUsXG4gICAgICAgICAgcmVuYW1lOiBzdGF0ZS5vcHRpb25zPy5zdXBwb3J0c19yZW5hbWUgPyBzdGF0ZS5yZW5hbWUgOiAnJyxcbiAgICAgICAgICBzYXZlcGF0aDogc3RhdGUub3B0aW9ucz8uc3VwcG9ydHNfc2F2ZXBhdGggPyBzdGF0ZS5zYXZlcGF0aCA6ICcnLFxuICAgICAgICAgIGNhdGVnb3J5OiBzdGF0ZS5vcHRpb25zPy5zdXBwb3J0c19jYXRlZ29yaWVzID8gc3RhdGUuY2F0ZWdvcnkgOiAnJyxcbiAgICAgICAgICBmaWxlX2luZGljZXM6IHN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX2ZpbGVfaW5kaWNlcyA/IHN0YXRlLmZpbGVJbmRpY2VzIDogdW5kZWZpbmVkLFxuICAgICAgICAgIG1pbl9maWxlX3NpemVfbWI6IHN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX3NtYWxsX2ZpbGVfZmlsdGVyID8gc3RhdGUubWluRmlsZVNpemVNYiA6IHVuZGVmaW5lZCxcbiAgICAgICAgICBzb3VyY2VfcGx1Z2luOiBzb3VyY2VQbHVnaW5JZCxcbiAgICAgICAgfVxuICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBwb3N0SnNvbihgL2FwaS9wbHVnaW5zLyR7c3RhdGUuZG93bmxvYWRlcklkfS9kb3dubG9hZHNgLCBwYXlsb2FkKVxuICAgICAgICB3cml0ZUxhc3RTYXZlcGF0aChzdGF0ZS5kb3dubG9hZGVySWQsIHN0YXRlLnNhdmVwYXRoIHx8ICcnKVxuICAgICAgICBjb25zdCBwYXJ0aWFsRmFpbHVyZSA9IE51bWJlcihyZXN1bHQ/LmZhaWx1cmVfY291bnQgfHwgMCkgPiAwXG4gICAgICAgIHN0YXRlLnN1Ym1pdFN0YXR1cyA9IHBhcnRpYWxGYWlsdXJlID8gJ2Vycm9yJyA6ICdzdWNjZXNzJ1xuICAgICAgICBzdGF0ZS5zdWJtaXRQcm9ncmVzcyA9IDEwMFxuICAgICAgICBpZiAocGFydGlhbEZhaWx1cmUpIHtcbiAgICAgICAgICBzdGF0ZS5lcnJvciA9IFN0cmluZyhyZXN1bHQ/Lm1lc3NhZ2UgfHwgYCR7cmVzdWx0Py5mYWlsdXJlX2NvdW50IHx8IDB9IOadoeS7u+WKoeWksei0pWApXG4gICAgICAgICAgc3RhdGUuc3VibWl0QnV0dG9uPy5fX3NldFN0YXRlPy4oJ2Vycm9yJywgMTAwLCBzdWJtaXRQYXJ0aWFsTGFiZWwpXG4gICAgICAgIH0gZWxzZSB7XG4gICAgICAgICAgc3RhdGUuc3VibWl0QnV0dG9uPy5fX3NldFN0YXRlPy4oJ3N1Y2Nlc3MnLCAxMDAsIHN1Ym1pdFN1Y2Nlc3NMYWJlbClcbiAgICAgICAgfVxuICAgICAgICByZW5kZXIoKVxuICAgICAgICByZXR1cm4gcmVzdWx0XG4gICAgICB9IGNhdGNoIChlOiBhbnkpIHtcbiAgICAgICAgc3RhdGUuZXJyb3IgPSBlPy5tZXNzYWdlIHx8ICfmjqjpgIHlpLHotKUnXG4gICAgICAgIHN0YXRlLnN1Ym1pdFN0YXR1cyA9ICdlcnJvcidcbiAgICAgICAgc3RhdGUuc3VibWl0UHJvZ3Jlc3MgPSAxMDBcbiAgICAgICAgc3RhdGUuc3VibWl0QnV0dG9uPy5fX3NldFN0YXRlPy4oJ2Vycm9yJywgMTAwLCAn5o6o6YCB5aSx6LSlJylcbiAgICAgICAgcmVuZGVyKClcbiAgICAgICAgdGhyb3cgZVxuICAgICAgfSBmaW5hbGx5IHtcbiAgICAgICAgc3RhdGUuc3VibWl0dGluZyA9IGZhbHNlXG4gICAgICAgIGlmIChwcm9ncmVzc1RpbWVyKSB7XG4gICAgICAgICAgd2luZG93LmNsZWFySW50ZXJ2YWwocHJvZ3Jlc3NUaW1lcilcbiAgICAgICAgICBwcm9ncmVzc1RpbWVyID0gbnVsbFxuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgZnVuY3Rpb24gcmVuZGVyKCkge1xuICAgICAgY29uc3QgYm9keSA9IG1vZGFsLmJvZHlcbiAgICAgIGJvZHkuaW5uZXJIVE1MID0gJydcbiAgICAgIGlmIChzdGF0ZS5lcnJvcikgYm9keS5hcHBlbmRDaGlsZChPYmplY3QuYXNzaWduKGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpLCB7IGNsYXNzTmFtZTogJ25vb3ItcGx1Z2luLW5vdGljZSBub29yLXBsdWdpbi1ub3RpY2UtLWVycm9yJywgdGV4dENvbnRlbnQ6IHN0YXRlLmVycm9yIH0pKVxuICAgICAgY29uc3QgZm9ybSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgICBmb3JtLmNsYXNzTmFtZSA9ICdub29yLWRvd25sb2FkZXItZm9ybSdcblxuICAgICAgaWYgKHNob3dEb3dubG9hZGVyRmllbGQpIHtcbiAgICAgICAgY29uc3QgZG93bmxvYWRlcklucHV0ID0gbWFrZUlucHV0KHsgdmFsdWU6IHN0YXRlLmRvd25sb2FkZXJOYW1lIHx8IHN0YXRlLmRvd25sb2FkZXJJZCwgcmVhZG9ubHk6IHRydWUgfSlcbiAgICAgICAgZm9ybS5hcHBlbmRDaGlsZChtYWtlRmllbGQoeyBsYWJlbDogJ+S4i+i9veWZqCcsIGNvbnRyb2w6IGRvd25sb2FkZXJJbnB1dCB9KSlcbiAgICAgIH1cblxuICAgICAgaWYgKGFsbG93QmF0Y2hVcmxzKSB7XG4gICAgICAgIGNvbnN0IHVybHNJbnB1dCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ3RleHRhcmVhJylcbiAgICAgICAgdXJsc0lucHV0LmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1pbnB1dCBub29yLWRvd25sb2FkZXItdGV4dGFyZWEnXG4gICAgICAgIHVybHNJbnB1dC5yb3dzID0gTnVtYmVyKG9wdGlvbnMudXJsUm93cyB8fCA2KVxuICAgICAgICB1cmxzSW5wdXQucGxhY2Vob2xkZXIgPSBTdHJpbmcob3B0aW9ucy51cmxQbGFjZWhvbGRlciB8fCAn5q+P6KGM5LiA5LiqIG1hZ25ldCAvIEJUIFVSTCAvIOaZrumAmiBVUkwnKVxuICAgICAgICB1cmxzSW5wdXQudmFsdWUgPSBzdGF0ZS51cmxzVGV4dFxuICAgICAgICB1cmxzSW5wdXQub25pbnB1dCA9ICgpID0+IHsgc3RhdGUudXJsc1RleHQgPSB1cmxzSW5wdXQudmFsdWUgfVxuICAgICAgICBmb3JtLmFwcGVuZENoaWxkKG1ha2VGaWVsZCh7XG4gICAgICAgICAgbGFiZWw6IG9wdGlvbnMudXJsTGFiZWwgfHwgJ+S4i+i9vemTvuaOpScsXG4gICAgICAgICAgaGludDogbWF4VXJscyA+IDAgPyBg5pSv5oyB5om56YeP5re75Yqg77ya5q+P6KGM5LiA5p2h77yM5pyA5aSaICR7bWF4VXJsc30g5p2h44CCYCA6ICfmlK/mjIHmibnph4/mt7vliqDvvJrmr4/ooYzkuIDmnaHjgIInLFxuICAgICAgICAgIGNvbnRyb2w6IHVybHNJbnB1dCxcbiAgICAgICAgfSkpXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGNhdGVnb3JpZXMgPSBBcnJheS5pc0FycmF5KHN0YXRlLm9wdGlvbnM/LmNhdGVnb3JpZXMpID8gc3RhdGUub3B0aW9ucy5jYXRlZ29yaWVzIDogW11cbiAgICAgIGlmIChzdGF0ZS5vcHRpb25zPy5zdXBwb3J0c19jYXRlZ29yaWVzKSB7XG4gICAgICAgIGNvbnN0IGNhdGVnb3J5U2VsZWN0ID0gbWFrZVNlbGVjdCh7XG4gICAgICAgICAgdmFsdWU6IHN0YXRlLmNhdGVnb3J5LFxuICAgICAgICAgIG9wdGlvbnM6IFt7IHZhbHVlOiAnJywgbGFiZWw6ICfkuI3kvb/nlKjliIbnsbvot6/lvoQnIH1dLmNvbmNhdChjYXRlZ29yaWVzLm1hcCgoaXRlbTogYW55KSA9PiAoeyB2YWx1ZTogaXRlbS5uYW1lLCBsYWJlbDogYCR7aXRlbS5uYW1lfSR7aXRlbS5zYXZlX3BhdGggPyBgIMK3ICR7aXRlbS5zYXZlX3BhdGh9YCA6ICcnfWAgfSkpKSxcbiAgICAgICAgICBvbkNoYW5nZTogKHZhbHVlOiBzdHJpbmcpID0+IHtcbiAgICAgICAgICAgIHN0YXRlLmNhdGVnb3J5ID0gdmFsdWVcbiAgICAgICAgICAgIGNvbnN0IGZvdW5kID0gY2F0ZWdvcmllcy5maW5kKChpdGVtOiBhbnkpID0+IGl0ZW0ubmFtZSA9PT0gdmFsdWUpXG4gICAgICAgICAgICBpZiAoZm91bmQ/LnNhdmVfcGF0aCkgc3RhdGUuc2F2ZXBhdGggPSBTdHJpbmcoZm91bmQuc2F2ZV9wYXRoKVxuICAgICAgICAgICAgcmVuZGVyKClcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICBmb3JtLmFwcGVuZENoaWxkKG1ha2VGaWVsZCh7IGxhYmVsOiAn5YiG57G7IC8g6Lev5b6E5bu66K6uJywgY29udHJvbDogY2F0ZWdvcnlTZWxlY3QgfSkpXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IHBhdGhzID0gQXJyYXkuaXNBcnJheShzdGF0ZS5vcHRpb25zPy5wYXRocykgPyBzdGF0ZS5vcHRpb25zLnBhdGhzLmZpbHRlcigoaXRlbTogYW55KSA9PiBpdGVtPy5wYXRoKSA6IFtdXG4gICAgICBpZiAoc3RhdGUub3B0aW9ucz8uc3VwcG9ydHNfc2F2ZXBhdGggJiYgcGF0aHMubGVuZ3RoKSB7XG4gICAgICAgIGNvbnN0IHBhdGhTZWxlY3QgPSBtYWtlU2VsZWN0KHtcbiAgICAgICAgICB2YWx1ZTogc3RhdGUuc2VsZWN0ZWRQYXRoIHx8IHN0YXRlLnNhdmVwYXRoLFxuICAgICAgICAgIG9wdGlvbnM6IFt7IHZhbHVlOiAnJywgbGFiZWw6ICfpgInmi6nljoblj7Lot6/lvoQnIH1dLmNvbmNhdChwYXRocy5tYXAoKGl0ZW06IGFueSkgPT4gKHtcbiAgICAgICAgICAgIHZhbHVlOiBTdHJpbmcoaXRlbS5wYXRoIHx8ICcnKSxcbiAgICAgICAgICAgIGxhYmVsOiBTdHJpbmcoaXRlbS5uYW1lIHx8IGl0ZW0ucGF0aCB8fCAnJyksXG4gICAgICAgICAgfSkpKSxcbiAgICAgICAgICBvbkNoYW5nZTogKHZhbHVlOiBzdHJpbmcpID0+IHtcbiAgICAgICAgICAgIHN0YXRlLnNlbGVjdGVkUGF0aCA9IHZhbHVlXG4gICAgICAgICAgICBpZiAodmFsdWUpIHN0YXRlLnNhdmVwYXRoID0gdmFsdWVcbiAgICAgICAgICAgIHJlbmRlcigpXG4gICAgICAgICAgfSxcbiAgICAgICAgfSlcbiAgICAgICAgZm9ybS5hcHBlbmRDaGlsZChtYWtlRmllbGQoeyBsYWJlbDogJ+WOhuWPsui3r+W+hCcsIGNvbnRyb2w6IHBhdGhTZWxlY3QsIGhpbnQ6ICfpgInmi6nlkI7ku43lj6/nu6fnu63nvJbovpHkuLrmm7Tmt7HlsYLnmoTlrZDnm67lvZXjgIInIH0pKVxuICAgICAgfVxuXG4gICAgICBpZiAoc3RhdGUub3B0aW9ucz8uc3VwcG9ydHNfcmVuYW1lKSB7XG4gICAgICAgIGNvbnN0IHJlbmFtZUlucHV0ID0gbWFrZUlucHV0KHtcbiAgICAgICAgICB2YWx1ZTogc3RhdGUucmVuYW1lLFxuICAgICAgICAgIHBsYWNlaG9sZGVyOiBzdGF0ZS5pdGVtVGl0bGUgfHwgJ+S4i+i9veS7u+WKoeWQjeensCcsXG4gICAgICAgICAgb25JbnB1dDogKHZhbHVlOiBzdHJpbmcpID0+IHtcbiAgICAgICAgICAgIHN0YXRlLnJlbmFtZSA9IHZhbHVlXG4gICAgICAgICAgICBzdGF0ZS5uYW1lID0gdmFsdWVcbiAgICAgICAgICB9LFxuICAgICAgICB9KVxuICAgICAgICBpZiAoc3RhdGUudGl0bGVPcHRpb25zLmxlbmd0aCA+IDEpIHtcbiAgICAgICAgICBjb25zdCB0aXRsZU1vZGVTZWxlY3QgPSBtYWtlU2VsZWN0KHtcbiAgICAgICAgICAgIHZhbHVlOiBzdGF0ZS50aXRsZU1vZGUgfHwgU3RyaW5nKHN0YXRlLnRpdGxlT3B0aW9uc1swXT8ua2V5IHx8ICcnKSxcbiAgICAgICAgICAgIG9wdGlvbnM6IHN0YXRlLnRpdGxlT3B0aW9ucy5tYXAoKGl0ZW06IGFueSkgPT4gKHsgdmFsdWU6IFN0cmluZyhpdGVtLmtleSB8fCBpdGVtLmxhYmVsIHx8IGl0ZW0udmFsdWUgfHwgJycpLCBsYWJlbDogU3RyaW5nKGl0ZW0ubGFiZWwgfHwgaXRlbS5rZXkgfHwgJycpIH0pKSxcbiAgICAgICAgICAgIG9uQ2hhbmdlOiAodmFsdWU6IHN0cmluZykgPT4ge1xuICAgICAgICAgICAgICBzdGF0ZS50aXRsZU1vZGUgPSB2YWx1ZVxuICAgICAgICAgICAgICBjb25zdCBmb3VuZCA9IHN0YXRlLnRpdGxlT3B0aW9ucy5maW5kKChpdGVtOiBhbnkpID0+IFN0cmluZyhpdGVtLmtleSB8fCAnJykgPT09IHZhbHVlKVxuICAgICAgICAgICAgICBpZiAoZm91bmQ/LnZhbHVlKSB7XG4gICAgICAgICAgICAgICAgc3RhdGUucmVuYW1lID0gU3RyaW5nKGZvdW5kLnZhbHVlKVxuICAgICAgICAgICAgICAgIHN0YXRlLm5hbWUgPSBTdHJpbmcoZm91bmQudmFsdWUpXG4gICAgICAgICAgICAgIH1cbiAgICAgICAgICAgICAgcmVuZGVyKClcbiAgICAgICAgICAgIH0sXG4gICAgICAgICAgfSlcbiAgICAgICAgICBjb25zdCBjb21ibyA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgICAgICAgY29tYm8uY2xhc3NOYW1lID0gJ25vb3ItZG93bmxvYWRlci10aXRsZS1jb21ibydcbiAgICAgICAgICBjb21iby5hcHBlbmQocmVuYW1lSW5wdXQsIHRpdGxlTW9kZVNlbGVjdClcbiAgICAgICAgICBjb25zdCBhY3RpdmVIaW50ID0gc3RhdGUudGl0bGVPcHRpb25zLmZpbmQoKGl0ZW06IGFueSkgPT4gU3RyaW5nKGl0ZW0ua2V5IHx8ICcnKSA9PT0gc3RhdGUudGl0bGVNb2RlKT8uaGludCB8fCAn5LyY5YWI5L2/55So5pm66IO95ZG95ZCNJ1xuICAgICAgICAgIGZvcm0uYXBwZW5kQ2hpbGQobWFrZUZpZWxkKHsgbGFiZWw6ICfkuIvovb3ku7vliqHlkI3np7AnLCBjb250cm9sOiBjb21ibywgaGludDogYWN0aXZlSGludCB9KSlcbiAgICAgICAgfSBlbHNlIHtcbiAgICAgICAgICBmb3JtLmFwcGVuZENoaWxkKG1ha2VGaWVsZCh7IGxhYmVsOiAn5LiL6L295Lu75Yqh5ZCN56ewJywgY29udHJvbDogcmVuYW1lSW5wdXQgfSkpXG4gICAgICAgIH1cbiAgICAgIH1cblxuICAgICAgaWYgKHN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX3NhdmVwYXRoKSB7XG4gICAgICAgIGNvbnN0IHNhdmVwYXRoSW5wdXQgPSBtYWtlSW5wdXQoe1xuICAgICAgICAgIHZhbHVlOiBzdGF0ZS5zYXZlcGF0aCxcbiAgICAgICAgICBwbGFjZWhvbGRlcjogJy9kb3dubG9hZHMvYXYnLFxuICAgICAgICAgIG9uSW5wdXQ6ICh2YWx1ZTogc3RyaW5nKSA9PiB7XG4gICAgICAgICAgICBzdGF0ZS5zYXZlcGF0aCA9IHZhbHVlXG4gICAgICAgICAgICBzdGF0ZS5zZWxlY3RlZFBhdGggPSB2YWx1ZVxuICAgICAgICAgIH0sXG4gICAgICAgIH0pXG4gICAgICAgIGZvcm0uYXBwZW5kQ2hpbGQobWFrZUZpZWxkKHsgbGFiZWw6ICfkuIvovb3ot6/lvoQnLCBjb250cm9sOiBzYXZlcGF0aElucHV0LCBoaW50OiAn5LyY5YWI5L2/55So5LiL6L295Zmo5o+S5Lu26L+U5Zue55qE5Y6G5Y+y6Lev5b6E5oiW6buY6K6k6Lev5b6E44CCJyB9KSlcbiAgICAgIH1cblxuICAgICAgaWYgKHN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX2ZpbGVfaW5kaWNlcykge1xuICAgICAgICBjb25zdCBmaWxlT3B0aW9ucyA9IEFycmF5LmlzQXJyYXkoc3RhdGUub3B0aW9ucz8uZmlsZV9pbmRpY2VzX29wdGlvbnMpID8gc3RhdGUub3B0aW9ucy5maWxlX2luZGljZXNfb3B0aW9ucy5maWx0ZXIoQm9vbGVhbikgOiBbXVxuICAgICAgICBjb25zdCBmaWxlQ29udHJvbCA9IGZpbGVPcHRpb25zLmxlbmd0aFxuICAgICAgICAgID8gbWFrZVNlbGVjdCh7XG4gICAgICAgICAgICAgIHZhbHVlOiBzdGF0ZS5maWxlSW5kaWNlcyxcbiAgICAgICAgICAgICAgb3B0aW9uczogZmlsZU9wdGlvbnMubWFwKChpdGVtOiBhbnkpID0+ICh7IHZhbHVlOiBTdHJpbmcoaXRlbS52YWx1ZSA/PyAnJyksIGxhYmVsOiBTdHJpbmcoaXRlbS5sYWJlbCA/PyBpdGVtLnZhbHVlID8/ICcnKSB9KSksXG4gICAgICAgICAgICAgIG9uQ2hhbmdlOiAodmFsdWU6IHN0cmluZykgPT4geyBzdGF0ZS5maWxlSW5kaWNlcyA9IHZhbHVlIH0sXG4gICAgICAgICAgICB9KVxuICAgICAgICAgIDogbWFrZUlucHV0KHtcbiAgICAgICAgICAgICAgdmFsdWU6IHN0YXRlLmZpbGVJbmRpY2VzLFxuICAgICAgICAgICAgICBwbGFjZWhvbGRlcjogJ2F1dG8gLyAtLTEgLyAwIC8gMSwzJyxcbiAgICAgICAgICAgICAgb25JbnB1dDogKHZhbHVlOiBzdHJpbmcpID0+IHsgc3RhdGUuZmlsZUluZGljZXMgPSB2YWx1ZSB9LFxuICAgICAgICAgICAgfSlcbiAgICAgICAgY29uc3QgZmlsZUhpbnQgPSBmaWxlT3B0aW9ucy5maW5kKChpdGVtOiBhbnkpID0+IFN0cmluZyhpdGVtLnZhbHVlID8/ICcnKSA9PT0gU3RyaW5nKHN0YXRlLmZpbGVJbmRpY2VzKSk/LmhpbnQgfHwgJydcbiAgICAgICAgZm9ybS5hcHBlbmRDaGlsZChtYWtlRmllbGQoeyBsYWJlbDogJ+aWh+S7tumAieaLqScsIGNvbnRyb2w6IGZpbGVDb250cm9sLCBoaW50OiBmaWxlSGludCB8fCB1bmRlZmluZWQgfSkpXG4gICAgICB9XG5cbiAgICAgIGlmIChzdGF0ZS5vcHRpb25zPy5zdXBwb3J0c19zbWFsbF9maWxlX2ZpbHRlcikge1xuICAgICAgICBjb25zdCBmaWx0ZXJJbnB1dCA9IG1ha2VJbnB1dCh7XG4gICAgICAgICAgdmFsdWU6IHN0YXRlLm1pbkZpbGVTaXplTWIsXG4gICAgICAgICAgcGxhY2Vob2xkZXI6IFN0cmluZyhzdGF0ZS5vcHRpb25zPy5zbWFsbF9maWxlX2ZpbHRlcj8uZGVmYXVsdF9tYiA/PyAnMCcpLFxuICAgICAgICAgIG9uSW5wdXQ6ICh2YWx1ZTogc3RyaW5nKSA9PiB7IHN0YXRlLm1pbkZpbGVTaXplTWIgPSB2YWx1ZSB9LFxuICAgICAgICB9KVxuICAgICAgICBjb25zdCBmaWx0ZXJIaW50ID0gc3RhdGUub3B0aW9ucz8uc21hbGxfZmlsZV9maWx0ZXI/LmtlZXBfc3VidGl0bGVzXG4gICAgICAgICAgPyAn6Ieq5Yqo6L+H5ruk5bCP5LqO6K+l6ZiI5YC855qE6Z2e5a2X5bmV5paH5Lu277yM5a2X5bmV5aeL57uI5L+d55WZ44CC5aGrIDAg6KGo56S65YWz6Zet44CCJ1xuICAgICAgICAgIDogJ+iHquWKqOi/h+a7pOWwj+S6juivpemYiOWAvOeahOaWh+S7tuOAguWhqyAwIOihqOekuuWFs+mXreOAgidcbiAgICAgICAgZm9ybS5hcHBlbmRDaGlsZChtYWtlRmllbGQoeyBsYWJlbDogJ+iHquWKqOi/h+a7pOWwj+aWh+S7tu+8iE1C77yJJywgY29udHJvbDogZmlsdGVySW5wdXQsIGhpbnQ6IGZpbHRlckhpbnQgfSkpXG4gICAgICB9XG5cbiAgICAgIGJvZHkuYXBwZW5kQ2hpbGQoZm9ybSlcbiAgICAgIGlmIChzdGF0ZS5sb2FkaW5nKSBib2R5LmFwcGVuZENoaWxkKG1ha2VMb2FkaW5nU3RhdGUoeyB0ZXh0OiAn6K+75Y+W5LiL6L295Zmo6YWN572u5Lit4oCmJyB9KSlcbiAgICAgIGVsc2UgaWYgKHN0YXRlLm9wdGlvbnM/LnN1cHBvcnRzX3Jlc291cmNlX3ByZXZpZXcpIHtcbiAgICAgICAgYm9keS5hcHBlbmRDaGlsZChyZW5kZXJSZXNvdXJjZVByZXZpZXcoe1xuICAgICAgICAgIG9wdGlvbnM6IHN0YXRlLm9wdGlvbnMsXG4gICAgICAgICAgbG9hZGluZzogc3RhdGUucHJldmlld0xvYWRpbmcsXG4gICAgICAgICAgZXJyb3I6IHN0YXRlLnByZXZpZXdFcnJvcixcbiAgICAgICAgICBkYXRhOiBzdGF0ZS5wcmV2aWV3RGF0YSxcbiAgICAgICAgfSkpXG4gICAgICB9XG5cbiAgICAgIGNvbnN0IGZvb3RlciA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpXG4gICAgICBmb290ZXIuY2xhc3NOYW1lID0gJ25vb3ItcGx1Z2luLW1vZGFsX19hY3Rpb25zJ1xuICAgICAgY29uc3QgY2FuY2VsID0gbWFrZUJ1dHRvbih7IGxhYmVsOiAn5YWz6ZetJywgb25DbGljazogKCkgPT4gIXN0YXRlLnN1Ym1pdHRpbmcgJiYgbW9kYWwuY2xvc2UoKSB9KVxuICAgICAgY29uc3Qgc3VibWl0QnRuID0gbWFrZVN1Ym1pdEJ1dHRvbih7XG4gICAgICAgIGlkbGVMYWJlbDogc3VibWl0SWRsZUxhYmVsLFxuICAgICAgICBzdWJtaXR0aW5nTGFiZWw6ICfmjqjpgIHkuK0nLFxuICAgICAgICBzdWNjZXNzTGFiZWw6IHN1Ym1pdFN1Y2Nlc3NMYWJlbCxcbiAgICAgICAgZXJyb3JMYWJlbDogc3VibWl0RXJyb3JMYWJlbCxcbiAgICAgICAgc3RhdHVzOiBzdGF0ZS5zdWJtaXRTdGF0dXMsXG4gICAgICAgIHByb2dyZXNzOiBzdGF0ZS5zdWJtaXRQcm9ncmVzcyxcbiAgICAgICAgY2xhc3NOYW1lOiAnbm9vci1kb3dubG9hZGVyLXN1Ym1pdCcsXG4gICAgICAgIGRpc2FibGVkOiBzdGF0ZS5sb2FkaW5nIHx8ICEoYWxsb3dCYXRjaFVybHMgPyBTdHJpbmcoc3RhdGUudXJsc1RleHQgfHwgJycpLnRyaW0oKSA6IFN0cmluZyhzdGF0ZS51cmwgfHwgJycpLnRyaW0oKSkgfHwgIXN0YXRlLmRvd25sb2FkZXJJZCB8fCBzdGF0ZS5zdWJtaXRTdGF0dXMgPT09ICdzdWNjZXNzJyxcbiAgICAgICAgb25DbGljazogYXN5bmMgKCkgPT4ge1xuICAgICAgICAgIHRyeSB7XG4gICAgICAgICAgICBjb25zdCByZXN1bHQgPSBhd2FpdCBzdWJtaXQoKVxuICAgICAgICAgICAgb3B0aW9ucy5vblN1Y2Nlc3M/LihyZXN1bHQpXG4gICAgICAgICAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgICAgICAgICBvcHRpb25zLm9uRXJyb3I/LihlKVxuICAgICAgICAgIH1cbiAgICAgICAgfSxcbiAgICAgIH0pXG4gICAgICBzdGF0ZS5zdWJtaXRCdXR0b24gPSBzdWJtaXRCdG5cbiAgICAgIGZvb3Rlci5hcHBlbmQoY2FuY2VsLCBzdWJtaXRCdG4pXG4gICAgICBjb25zdCBleGlzdGluZ0Zvb3RlciA9IG1vZGFsLmVsLnF1ZXJ5U2VsZWN0b3IoJy5ub29yLXBsdWdpbi1tb2RhbF9fYWN0aW9ucycpXG4gICAgICBpZiAoZXhpc3RpbmdGb290ZXIpIGV4aXN0aW5nRm9vdGVyLnJlbW92ZSgpXG4gICAgICBtb2RhbC5lbC5xdWVyeVNlbGVjdG9yKCcubm9vci1wbHVnaW4tbW9kYWwnKT8uYXBwZW5kQ2hpbGQoZm9vdGVyKVxuICAgIH1cblxuICAgIGF3YWl0IGxvYWRPcHRpb25zKClcbiAgICBpZiAoYWxsb3dCYXRjaFVybHMpIHtcbiAgICAgIHdpbmRvdy5zZXRUaW1lb3V0KCgpID0+IHtcbiAgICAgICAgY29uc3QgaW5wdXQgPSBtb2RhbC5ib2R5LnF1ZXJ5U2VsZWN0b3IoJy5ub29yLWRvd25sb2FkZXItdGV4dGFyZWEnKSBhcyBIVE1MVGV4dEFyZWFFbGVtZW50IHwgbnVsbFxuICAgICAgICBpbnB1dD8uZm9jdXMoKVxuICAgICAgfSwgMClcbiAgICB9XG4gICAgcmVuZGVyKClcbiAgICByZXR1cm4gbW9kYWxcbiAgfVxuXG4gIHJldHVybiB7IG9wZW4sIG9wZW5UYXNrOiBvcGVuIH1cbn1cblxuZnVuY3Rpb24gc2RrRm9yKGlkOiBzdHJpbmcpIHtcbiAgY29uc3QgcGx1Z2luRmV0Y2ggPSAocGF0aDogc3RyaW5nLCBpbml0PzogUmVxdWVzdEluaXQpID0+IGZldGNoKGAvYXBpL3BsdWdpbnMvJHtpZH0ke3BhdGh9YCwgaW5pdClcbiAgY29uc3QgZG93bmxvYWRzID0gY3JlYXRlRG93bmxvYWRlckRpYWxvZ0NvbnRleHQoaWQpXG4gIHJldHVybiB7XG4gICAgcGx1Z2luSWQ6IGlkLFxuICAgIGFwaToge1xuICAgICAgcGx1Z2luOiBwbHVnaW5GZXRjaCxcbiAgICAgIHdzVXJsOiAocGF0aDogc3RyaW5nKSA9PiBgJHtsb2NhdGlvbi5wcm90b2NvbCA9PT0gJ2h0dHBzOicgPyAnd3NzJyA6ICd3cyd9Oi8vJHtsb2NhdGlvbi5ob3N0fS9hcGkvcGx1Z2lucy8ke2lkfSR7cGF0aH1gLFxuICAgICAgZ2V0OiAocGF0aDogc3RyaW5nLCBjb25maWc/OiBhbnkpID0+IGFwaS5nZXQocGF0aCwgY29uZmlnKSxcbiAgICAgIHBvc3Q6IChwYXRoOiBzdHJpbmcsIGRhdGE/OiBhbnksIGNvbmZpZz86IGFueSkgPT4gYXBpLnBvc3QocGF0aCwgZGF0YSwgY29uZmlnKSxcbiAgICB9LFxuICAgIHRvYXN0OiB7XG4gICAgICBzdWNjZXNzOiAobXNnOiBzdHJpbmcpID0+IHRvYXN0LnN1Y2Nlc3MobXNnKSxcbiAgICAgIGVycm9yOiAobXNnOiBzdHJpbmcpID0+IHRvYXN0LmVycm9yKG1zZyksXG4gICAgICBpbmZvOiAobXNnOiBzdHJpbmcpID0+IHRvYXN0LmluZm8obXNnKSxcbiAgICAgIHdhcm5pbmc6IChtc2c6IHN0cmluZykgPT4gdG9hc3Qud2FybmluZyhtc2cpLFxuICAgIH0sXG4gICAgZG93bmxvYWRzLFxuICAgIHVpOiB7XG4gICAgICBidXR0b246IG1ha2VCdXR0b24sXG4gICAgICBpbnB1dDogbWFrZUlucHV0LFxuICAgICAgc2VsZWN0OiBtYWtlU2VsZWN0LFxuICAgICAgZmllbGQ6IG1ha2VGaWVsZCxcbiAgICAgIG1vZGFsOiBtYWtlTW9kYWwsXG4gICAgICBwYW5lbDogbWFrZVBhbmVsLFxuICAgICAgdGFiczogbWFrZVRhYnMsXG4gICAgICBwYWdpbmF0aW9uOiBtYWtlUGFnaW5hdGlvbixcbiAgICAgIHN1Ym1pdEJ1dHRvbjogbWFrZVN1Ym1pdEJ1dHRvbixcbiAgICAgIHRvcEJhcjogbWFrZVRvcEJhcixcbiAgICAgIGFjdGlvblJvdzogbWFrZUFjdGlvblJvdyxcbiAgICAgIHN0YXRDYXJkOiBtYWtlU3RhdENhcmQsXG4gICAgICBzdGF0R3JpZDogbWFrZVN0YXRHcmlkLFxuICAgICAgbWVkaWFDYXJkOiBtYWtlTWVkaWFDYXJkLFxuICAgICAgbG9hZGluZ1N0YXRlOiBtYWtlTG9hZGluZ1N0YXRlLFxuICAgICAgYmFkZ2U6IChvOiBhbnkpID0+IHsgY29uc3QgYiA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoby5vbkNsaWNrID8gJ2J1dHRvbicgOiAnc3BhbicpOyBiLmNsYXNzTmFtZSA9IFsnbm9vci1wbHVnaW4tYmFkZ2UnLCBvLnRvbmUgPyBgbm9vci1wbHVnaW4tYmFkZ2UtLSR7by50b25lfWAgOiAnJywgby5jbGFzc05hbWUgfHwgJyddLmZpbHRlcihCb29sZWFuKS5qb2luKCcgJyk7IGIudGV4dENvbnRlbnQgPSBvLmxhYmVsIHx8ICcnOyBpZiAoby5vbkNsaWNrKSAoYiBhcyBIVE1MQnV0dG9uRWxlbWVudCkub25jbGljayA9IG8ub25DbGljazsgcmV0dXJuIGIgfSxcbiAgICAgIGNoaXA6IChvOiBhbnkpID0+IHsgY29uc3QgYiA9IG1ha2VCdXR0b24oeyBsYWJlbDogby5sYWJlbCwgY2xhc3NOYW1lOiBbJ25vb3ItcGx1Z2luLWNoaXAnLCBvLmFjdGl2ZSA/ICdpcy1hY3RpdmUnIDogJycsIG8uY2xhc3NOYW1lIHx8ICcnXS5maWx0ZXIoQm9vbGVhbikuam9pbignICcpIH0pOyBiLm9uY2xpY2sgPSBvLm9uQ2xpY2s7IHJldHVybiBiIH0sXG4gICAgICBub3RpY2U6IChvOiBhbnkpID0+IHsgY29uc3QgZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOyBkLmNsYXNzTmFtZSA9IGBub29yLXBsdWdpbi1ub3RpY2Ugbm9vci1wbHVnaW4tbm90aWNlLS0ke28udG9uZSB8fCAnaW5mbyd9YDsgZC50ZXh0Q29udGVudCA9IG8udGV4dCB8fCAnJzsgcmV0dXJuIGQgfSxcbiAgICAgIGVtcHR5U3RhdGU6IChvOiBhbnkpID0+IHsgY29uc3QgZCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2RpdicpOyBkLmNsYXNzTmFtZSA9ICdub29yLXBsdWdpbi1zdGF0ZSc7IGQudGV4dENvbnRlbnQgPSBvLnRleHQgfHwgJ+aaguaXoOWGheWuuSc7IHJldHVybiBkIH0sXG4gICAgICBlcnJvclN0YXRlOiAobzogYW55KSA9PiB7IGNvbnN0IGQgPSBkb2N1bWVudC5jcmVhdGVFbGVtZW50KCdkaXYnKTsgZC5jbGFzc05hbWUgPSAnbm9vci1wbHVnaW4tc3RhdGUgbm9vci1wbHVnaW4tc3RhdGUtLWVycm9yJzsgZC50ZXh0Q29udGVudCA9IG8udGV4dCB8fCAn5Yqg6L295aSx6LSlJzsgcmV0dXJuIGQgfSxcbiAgICAgIHNrZWxldG9uQ2FyZDogKG86IGFueSkgPT4geyBjb25zdCBkID0gZG9jdW1lbnQuY3JlYXRlRWxlbWVudCgnZGl2Jyk7IGQuY2xhc3NOYW1lID0gYG5vb3ItcGx1Z2luLXNrZWxldG9uICR7by5jbGFzc05hbWUgfHwgJyd9YDsgcmV0dXJuIGQgfSxcbiAgICAgIGNhcmQ6IChvOiBhbnkpID0+IHsgY29uc3QgYSA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoby5ocmVmID8gJ2EnIDogJ2RpdicpOyBhLmNsYXNzTmFtZSA9IGBub29yLXBsdWdpbi1jYXJkICR7by5jbGFzc05hbWUgfHwgJyd9YDsgaWYgKG8uaHJlZikgeyAoYSBhcyBIVE1MQW5jaG9yRWxlbWVudCkuaHJlZiA9IG8uaHJlZjsgKGEgYXMgSFRNTEFuY2hvckVsZW1lbnQpLnRhcmdldCA9IG8udGFyZ2V0IHx8ICdfc2VsZicgfTsgcmV0dXJuIGEgfSxcbiAgICAgIGNvbmZpcm06IChvOiBhbnkpID0+IGNvbmZpcm0uY29uZmlybSh7IHRpdGxlOiBvLnRpdGxlIHx8ICfnoa7orqTmk43kvZwnLCBtZXNzYWdlOiBvLm1lc3NhZ2UgfHwgJycsIGNvbmZpcm1UZXh0OiBvLmNvbmZpcm1UZXh0IHx8ICfnoa7orqQnLCBkYW5nZXI6ICEhby5kYW5nZXIgfSksXG4gICAgfSxcbiAgfVxufVxuXG5hc3luYyBmdW5jdGlvbiBtb3VudFBsdWdpbigpIHtcbiAgY2xlYXJNb3VudGVkKClcbiAgaWYgKCFwbHVnaW5JZC52YWx1ZSB8fCAhaG9zdC52YWx1ZSkgcmV0dXJuXG4gIGxvYWRpbmcudmFsdWUgPSB0cnVlXG4gIGVycm9yLnZhbHVlID0gJydcbiAgdHJ5IHtcbiAgICBjb25zdCBpbmZvID0gYXdhaXQgYXBpLmdldChgL3BsdWdpbnMvJHtwbHVnaW5JZC52YWx1ZX0vY29uZmlnYCkudGhlbihyID0+IHIuZGF0YSlcbiAgICBjb25zdCBzdHlsZSA9IGluZm8/LnBsdWdpbj8uZnJvbnRlbmQ/LnN0eWxlXG4gICAgaWYgKHN0eWxlKSB7XG4gICAgICBjb25zdCBidXN0ID0gRGF0ZS5ub3coKVxuICAgICAgc3R5bGVFbCA9IGRvY3VtZW50LmNyZWF0ZUVsZW1lbnQoJ2xpbmsnKVxuICAgICAgc3R5bGVFbC5yZWwgPSAnc3R5bGVzaGVldCdcbiAgICAgIHN0eWxlRWwuaHJlZiA9IGAvYXBpL3BsdWdpbnMvJHtwbHVnaW5JZC52YWx1ZX0vYXNzZXRzLyR7c3R5bGUucmVwbGFjZSgvXmZyb250ZW5kXFwvLywgJycpfT90PSR7YnVzdH1gXG4gICAgICBkb2N1bWVudC5oZWFkLmFwcGVuZENoaWxkKHN0eWxlRWwpXG4gICAgfVxuICAgIGNvbnN0IGVudHJ5ID0gaW5mbz8ucGx1Z2luPy5mcm9udGVuZD8uZW50cnkgfHwgJ2Zyb250ZW5kL3BhZ2UuanMnXG4gICAgY29uc3QgbW9kID0gYXdhaXQgaW1wb3J0KC8qIEB2aXRlLWlnbm9yZSAqLyBgL2FwaS9wbHVnaW5zLyR7cGx1Z2luSWQudmFsdWV9L2Fzc2V0cy8ke2VudHJ5LnJlcGxhY2UoL15mcm9udGVuZFxcLy8sICcnKX0/dD0ke0RhdGUubm93KCl9YClcbiAgICBhd2FpdCBuZXh0VGljaygpXG4gICAgY29uc3QgcmV0ID0gYXdhaXQgbW9kLm1vdW50KGhvc3QudmFsdWUsIHNka0ZvcihwbHVnaW5JZC52YWx1ZSkpXG4gICAgaWYgKHR5cGVvZiByZXQgPT09ICdmdW5jdGlvbicpIGRpc3Bvc2UgPSByZXRcbiAgfSBjYXRjaCAoZTogYW55KSB7XG4gICAgZXJyb3IudmFsdWUgPSBlPy5yZXNwb25zZT8uZGF0YT8uZGV0YWlsIHx8IGU/Lm1lc3NhZ2UgfHwgJ+aPkuS7tuWKoOi9veWksei0pSdcbiAgfSBmaW5hbGx5IHtcbiAgICBsb2FkaW5nLnZhbHVlID0gZmFsc2VcbiAgfVxufVxuXG5vbk1vdW50ZWQobW91bnRQbHVnaW4pXG53YXRjaChwbHVnaW5JZCwgbW91bnRQbHVnaW4pXG5vbkJlZm9yZVVubW91bnQoY2xlYXJNb3VudGVkKVxuPC9zY3JpcHQ+XG5cbjx0ZW1wbGF0ZT5cbiAgPGRpdiBjbGFzcz1cInBsdWdpbi1ob3N0LXBhZ2VcIj5cbiAgICA8ZGl2IHYtaWY9XCJsb2FkaW5nXCIgY2xhc3M9XCJwbHVnaW4taG9zdC1zdGF0ZVwiPuaPkuS7tuWKoOi9veS4rTwvZGl2PlxuICAgIDxkaXYgdi1pZj1cImVycm9yXCIgY2xhc3M9XCJwbHVnaW4taG9zdC1zdGF0ZSBwbHVnaW4taG9zdC1zdGF0ZS0tZXJyb3JcIj57eyBlcnJvciB9fTwvZGl2PlxuICAgIDxkaXYgcmVmPVwiaG9zdFwiIGNsYXNzPVwicGx1Z2luLWhvc3QtbW91bnRcIiA6Y2xhc3M9XCJ7ICdpcy1sb2FkaW5nJzogbG9hZGluZyB9XCIgLz5cbiAgPC9kaXY+XG48L3RlbXBsYXRlPlxuXG48c3R5bGU+XG4ucGx1Z2luLWhvc3QtcGFnZSB7IG1pbi1oZWlnaHQ6IDQwdmg7IH1cbi5wbHVnaW4taG9zdC1zdGF0ZSB7IHBhZGRpbmc6IDFyZW07IG1hcmdpbi1ib3R0b206IDFyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1sZyk7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsLjA0KTsgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDgpOyBjb2xvcjogcmdiYSgyNTUsMjU1LDI1NSwuNyk7IH1cbi5wbHVnaW4taG9zdC1zdGF0ZS0tZXJyb3IgeyBjb2xvcjogdmFyKC0tY29sb3ItZXJyb3IpOyBib3JkZXItY29sb3I6IHJnYmEoMjI3LDI2LDI2LC4yNSk7IGJhY2tncm91bmQ6IHJnYmEoMjI3LDI2LDI2LC4xKTsgfVxuLnBsdWdpbi1ob3N0LW1vdW50LmlzLWxvYWRpbmcgeyBvcGFjaXR5OiAuNjsgfVxuLm5vb3ItcGx1Z2luLXRvcGJhciB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogc3BhY2UtYmV0d2VlbjsgZ2FwOiAuNzVyZW07IG1hcmdpbi1ib3R0b206IDFyZW07IGZsZXgtd3JhcDogd3JhcDsgfVxuLm5vb3ItcGx1Z2luLXRvcGJhcl9fdGFicywgLm5vb3ItcGx1Z2luLXRvcGJhcl9fYWN0aW9ucyB7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGdhcDogLjVyZW07IGZsZXgtd3JhcDogd3JhcDsgfVxuLm5vb3ItcGx1Z2luLWJ0biB7IG1pbi1oZWlnaHQ6IDMwcHg7IHBhZGRpbmc6IC4zNXJlbSAuNzVyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7IGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA4KTsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwuMDQpOyBjb2xvcjogcmdiYSgyNTUsMjU1LDI1NSwuNzgpOyBmb250LXNpemU6IC43NXJlbTsgZm9udC13ZWlnaHQ6IDYwMDsgdHJhbnNpdGlvbjogYWxsIHZhcigtLXRyYW5zaXRpb24tZmFzdCk7IH1cbi5ub29yLXBsdWdpbi1idG46aG92ZXI6bm90KDpkaXNhYmxlZCkgeyBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LC4wOCk7IGNvbG9yOiAjZmZmOyB9XG4ubm9vci1wbHVnaW4tYnRuOmRpc2FibGVkIHsgb3BhY2l0eTogLjQ1OyBjdXJzb3I6IG5vdC1hbGxvd2VkOyB9XG4ubm9vci1wbHVnaW4tYnRuLS1wcmltYXJ5IHsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYnJhbmQpOyBjb2xvcjogd2hpdGU7IGJvcmRlci1jb2xvcjogdHJhbnNwYXJlbnQ7IH1cbi5ub29yLXBsdWdpbi1idG4tLWRhbmdlciB7IGJhY2tncm91bmQ6IHJnYmEoMjI3LDI2LDI2LC4xOCk7IGNvbG9yOiAjZmY4YTgwOyBib3JkZXItY29sb3I6IHJnYmEoMjI3LDI2LDI2LC4yOCk7IH1cbi5ub29yLXBsdWdpbi1pbnB1dCB7IHdpZHRoOiAxMDAlOyBtaW4taGVpZ2h0OiAzNnB4OyBwYWRkaW5nOiAuNXJlbSAuNzVyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1tZCk7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsLjA1KTsgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDgpOyBjb2xvcjogd2hpdGU7IG91dGxpbmU6IG5vbmU7IH1cbi5ub29yLXBsdWdpbi1pbnB1dDpmb2N1cyB7IGJvcmRlci1jb2xvcjogdmFyKC0tY29sb3ItYnJhbmQpOyBib3gtc2hhZG93OiAwIDAgMCAzcHggcmdiYSgwLDExNywyNTUsLjEyKTsgfVxuLm5vb3ItcGx1Z2luLXNlbGVjdCBvcHRpb24geyBiYWNrZ3JvdW5kOiAjMTExOTM2OyBjb2xvcjogd2hpdGU7IH1cbi5ub29yLXBsdWdpbi1maWVsZCB7IGRpc3BsYXk6IGZsZXg7IGZsZXgtZGlyZWN0aW9uOiBjb2x1bW47IGdhcDogLjM1cmVtOyB9XG4ubm9vci1wbHVnaW4tZmllbGRfX2xhYmVsIHsgZm9udC1zaXplOiAuNzVyZW07IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC41Mik7IGZvbnQtd2VpZ2h0OiA2MDA7IH1cbi5ub29yLXBsdWdpbi1maWVsZF9faGludCB7IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC4zNSk7IH1cbi5ub29yLXBsdWdpbi1tb2RhbC1tYXNrIHsgcG9zaXRpb246IGZpeGVkOyBpbnNldDogMDsgei1pbmRleDogdmFyKC0tei1tb2RhbCk7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBwYWRkaW5nOiAxcmVtOyBiYWNrZ3JvdW5kOiByZ2JhKDAsMCwwLC42Mik7IGJhY2tkcm9wLWZpbHRlcjogYmx1cigxMHB4KTsgfVxuLm5vb3ItcGx1Z2luLW1vZGFsIHsgd2lkdGg6IG1pbig1NjBweCwgMTAwJSk7IG1heC1oZWlnaHQ6IG1pbig3NjBweCwgOTJ2aCk7IG92ZXJmbG93OiBhdXRvOyBib3JkZXItcmFkaXVzOiB2YXIoLS1yYWRpdXMteGwpOyBiYWNrZ3JvdW5kOiByZ2IoMjYsMzEsNTUpOyBib3JkZXI6IDFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wOCk7IGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdy14bCk7IH1cbi5ub29yLXBsdWdpbi1tb2RhbC0tbGcgeyB3aWR0aDogbWluKDkyMHB4LCAxMDAlKTsgfVxuLm5vb3ItcGx1Z2luLW1vZGFsX19oZWFkLCAubm9vci1wbHVnaW4tbW9kYWxfX2FjdGlvbnMgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47IGdhcDogLjc1cmVtOyBwYWRkaW5nOiAxcmVtOyBib3JkZXItYm90dG9tOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpOyB9XG4ubm9vci1wbHVnaW4tbW9kYWxfX2FjdGlvbnMgeyBqdXN0aWZ5LWNvbnRlbnQ6IGZsZXgtZW5kOyBib3JkZXItdG9wOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpOyBib3JkZXItYm90dG9tOiAwOyB9XG4ubm9vci1wbHVnaW4tbW9kYWxfX3RpdGxlIHsgY29sb3I6IHdoaXRlOyBmb250LXdlaWdodDogNzAwOyB9XG4ubm9vci1wbHVnaW4tbW9kYWxfX2JvZHkgeyBwYWRkaW5nOiAxcmVtOyBkaXNwbGF5OiBncmlkOyBnYXA6IC44NXJlbTsgfVxuLm5vb3ItcGx1Z2luLXRhYnMgeyBwb3NpdGlvbjogcmVsYXRpdmU7IGRpc3BsYXk6IGlubGluZS1mbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IC4yNXJlbTsgcGFkZGluZzogLjM3NXJlbTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLXhsKTsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwuMDQpOyBib3JkZXI6IDFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wNik7IG1heC13aWR0aDogMTAwJTsgb3ZlcmZsb3cteDogYXV0bzsgc2Nyb2xsYmFyLXdpZHRoOiBub25lOyB9XG4ubm9vci1wbHVnaW4tdGFiczo6LXdlYmtpdC1zY3JvbGxiYXIgeyBkaXNwbGF5OiBub25lOyB9XG4ubm9vci1wbHVnaW4tdGFic19fbWFya2VyIHsgcG9zaXRpb246IGFic29sdXRlOyB0b3A6IC4zNzVyZW07IGJvdHRvbTogLjM3NXJlbTsgbGVmdDogMDsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWxnKTsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYnJhbmQpOyBib3gtc2hhZG93OiAwIDRweCAxMnB4IHJnYmEoMCwxMTcsMjU1LC4zKTsgdHJhbnNpdGlvbjogbm9uZTsgei1pbmRleDogMDsgcG9pbnRlci1ldmVudHM6IG5vbmU7IH1cbi5ub29yLXBsdWdpbi10YWJzLS1yZWFkeSAubm9vci1wbHVnaW4tdGFic19fbWFya2VyIHsgdHJhbnNpdGlvbjogdHJhbnNmb3JtIC4yNXMgY3ViaWMtYmV6aWVyKC40LDAsLjIsMSksIHdpZHRoIC4yNXMgY3ViaWMtYmV6aWVyKC40LDAsLjIsMSk7IH1cbi5ub29yLXBsdWdpbi10YWJzX19pdGVtIHsgcG9zaXRpb246IHJlbGF0aXZlOyB6LWluZGV4OiAxOyBtaW4taGVpZ2h0OiAzNHB4OyBwYWRkaW5nOiAuNXJlbSAxLjVyZW07IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1sZyk7IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC40KTsgZm9udC1zaXplOiAuODc1cmVtOyBmb250LXdlaWdodDogNjAwOyB3aGl0ZS1zcGFjZTogbm93cmFwOyB0cmFuc2l0aW9uOiBjb2xvciAuMnMgZWFzZTsgfVxuLm5vb3ItcGx1Z2luLXRhYnNfX2l0ZW06aG92ZXIgeyBjb2xvcjogcmdiYSgyNTUsMjU1LDI1NSwuNyk7IH1cbi5ub29yLXBsdWdpbi10YWJzX19pdGVtLmlzLWFjdGl2ZSB7IGNvbG9yOiAjZmZmOyB9XG4ubm9vci1wbHVnaW4tcGFnaW5hdGlvbiwgLm5vb3ItcGFnaW5hdGlvbiB7IGRpc3BsYXk6IGZsZXg7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBhbGlnbi1pdGVtczogY2VudGVyOyBnYXA6IC40cmVtOyBtYXJnaW4tdG9wOiAxcmVtOyBmbGV4LXdyYXA6IHdyYXA7IH1cbi5ub29yLXBhZ2luYXRpb25fX2J0biB7IG1pbi1oZWlnaHQ6IDMwcHg7IG1pbi13aWR0aDogMzBweDsgcGFkZGluZzogLjM1cmVtIC43NXJlbTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLW1kKTsgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDgpOyBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LC4wNCk7IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC43OCk7IGZvbnQtc2l6ZTogLjc1cmVtOyBmb250LXdlaWdodDogNzAwOyB0cmFuc2l0aW9uOiBhbGwgdmFyKC0tdHJhbnNpdGlvbi1mYXN0KTsgfVxuLm5vb3ItcGFnaW5hdGlvbl9fYnRuOmhvdmVyOm5vdCg6ZGlzYWJsZWQpIHsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwuMDgpOyBjb2xvcjogI2ZmZjsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC0xcHgpOyB9XG4ubm9vci1wYWdpbmF0aW9uX19idG46ZGlzYWJsZWQgeyBvcGFjaXR5OiAuMzg7IGN1cnNvcjogbm90LWFsbG93ZWQ7IH1cbi5ub29yLXBhZ2luYXRpb25fX3BhZ2UuaXMtYWN0aXZlLCAubm9vci1wYWdpbmF0aW9uX19idG4uaXMtYWN0aXZlIHsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYnJhbmQpOyBjb2xvcjogd2hpdGU7IGJvcmRlci1jb2xvcjogdHJhbnNwYXJlbnQ7IGJveC1zaGFkb3c6IDAgNHB4IDEycHggcmdiYSgwLDExNywyNTUsLjI1KTsgfVxuLm5vb3ItcGx1Z2luLWJhZGdlIHsgbWluLWhlaWdodDogMjhweDsgZGlzcGxheTogaW5saW5lLWZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IHBhZGRpbmc6IC4yNXJlbSAuNnJlbTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLXBpbGwpOyBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwyNTUsMjU1LC4wNik7IGJvcmRlcjogMXB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjA4KTsgY29sb3I6IHJnYmEoMjU1LDI1NSwyNTUsLjY4KTsgZm9udC1zaXplOiAuNzVyZW07IH1cbi5ub29yLXBsdWdpbi1jaGlwIHsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLXBpbGwpOyB9XG4ubm9vci1wbHVnaW4tY2hpcC5pcy1hY3RpdmUgeyBiYWNrZ3JvdW5kOiB2YXIoLS1jb2xvci1icmFuZCk7IGNvbG9yOiB3aGl0ZTsgfVxuLm5vb3ItcGx1Z2luLW5vdGljZSwgLm5vb3ItcGx1Z2luLXN0YXRlIHsgcGFkZGluZzogMXJlbTsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWxnKTsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwuMDQpOyBib3JkZXI6IDFweCBzb2xpZCByZ2JhKDI1NSwyNTUsMjU1LC4wOCk7IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC43KTsgfVxuLm5vb3ItcGx1Z2luLW5vdGljZS0tZXJyb3IsIC5ub29yLXBsdWdpbi1zdGF0ZS0tZXJyb3IgeyBjb2xvcjogI2ZmOGE4MDsgYmFja2dyb3VuZDogcmdiYSgyMjcsMjYsMjYsLjEpOyBib3JkZXItY29sb3I6IHJnYmEoMjI3LDI2LDI2LC4yNSk7IH1cbi5ub29yLXBsdWdpbi1jYXJkIHsgYmFja2dyb3VuZDogcmdiKDI2LDMxLDU1KTsgYm9yZGVyOiAxcHggc29saWQgcmdiYSgyNTUsMjU1LDI1NSwuMDYpOyBjb2xvcjogaW5oZXJpdDsgdGV4dC1kZWNvcmF0aW9uOiBub25lOyB9XG4ubm9vci1wbHVnaW4tc2tlbGV0b24geyBtaW4taGVpZ2h0OiAxODBweDsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWxnKTsgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDkwZGVnLCByZ2JhKDI1NSwyNTUsMjU1LC4wNCksIHJnYmEoMjU1LDI1NSwyNTUsLjA4KSwgcmdiYSgyNTUsMjU1LDI1NSwuMDQpKTsgYmFja2dyb3VuZC1zaXplOiAyMDAlIDEwMCU7IGFuaW1hdGlvbjogbm9vci1za2VsZXRvbiAxLjJzIGxpbmVhciBpbmZpbml0ZTsgfVxuQGtleWZyYW1lcyBub29yLXNrZWxldG9uIHsgdG8geyBiYWNrZ3JvdW5kLXBvc2l0aW9uOiAtMjAwJSAwOyB9IH1cbkBtZWRpYSAobWF4LXdpZHRoOiA2NDBweCkgeyAubm9vci1wbHVnaW4tdG9wYmFyIHsgZmxleC1kaXJlY3Rpb246IGNvbHVtbi1yZXZlcnNlOyBhbGlnbi1pdGVtczogc3RyZXRjaDsgfSAubm9vci1wbHVnaW4tdG9wYmFyX19hY3Rpb25zIHsgb3JkZXI6IC0xOyB9IH1cbi8qIFNESyB2aXN1YWwgY29udHJhY3Q6IHBsdWdpbnMgbXVzdCBzaGFyZSBtYWluIE5PT1IgY29tcG9uZW50IG1ldHJpY3MuICovXG4ucGx1Z2luLWhvc3QtbW91bnQsIC5wbHVnaW4taG9zdC1tb3VudCAqIHsgYm94LXNpemluZzogYm9yZGVyLWJveDsgfVxuLm5vb3ItcGx1Z2luLWJ0biB7IGhlaWdodDogMzBweDsgbWluLWhlaWdodDogMzBweDsgZGlzcGxheTogaW5saW5lLWZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBsaW5lLWhlaWdodDogMTsgZm9udC1mYW1pbHk6IHZhcigtLWZvbnQtZGlzcGxheSk7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1idXR0b24pOyB9XG4ubm9vci1wbHVnaW4tYnRuLS1wcmltYXJ5OmhvdmVyOm5vdCg6ZGlzYWJsZWQpIHsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYnJhbmQtaG92ZXIpOyBib3JkZXItY29sb3I6IHRyYW5zcGFyZW50OyB9XG4ubm9vci1wbHVnaW4tbW9kYWxfX2Nsb3NlIHsgd2lkdGg6IDMwcHg7IG1pbi13aWR0aDogMzBweDsgcGFkZGluZzogMDsgYm9yZGVyLXJhZGl1czogNTAlOyBmb250LXNpemU6IDE4cHg7IGxpbmUtaGVpZ2h0OiAxOyB9XG4ubm9vci1wbHVnaW4tbW9kYWxfX2Nsb3NlOmhvdmVyOm5vdCg6ZGlzYWJsZWQpIHsgY29sb3I6ICNmZmY7IGJvcmRlci1jb2xvcjogcmdiYSgyMjcsMjYsMjYsLjM1KTsgYmFja2dyb3VuZDogcmdiYSgyMjcsMjYsMjYsLjE2KTsgfVxuLmRldGFpbC1wYW5lbC10b3BiYXIgeyBkaXNwbGF5OiBmbGV4OyBhbGlnbi1pdGVtczogY2VudGVyOyBqdXN0aWZ5LWNvbnRlbnQ6IHNwYWNlLWJldHdlZW47IGdhcDogLjc1cmVtOyB9XG4uZGV0YWlsLXBhbmVsLXRvcGJhcl9fbWV0YSB7IG1pbi13aWR0aDogMDsgfVxuLmRldGFpbC1wYW5lbC10b3BiYXJfX2V5ZWJyb3cgeyBkaXNwbGF5OiBpbmxpbmUtZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgbWluLWhlaWdodDogMS41cmVtOyBmb250LXNpemU6IC43MnJlbTsgbGV0dGVyLXNwYWNpbmc6IC4wOGVtOyB0ZXh0LXRyYW5zZm9ybTogdXBwZXJjYXNlOyBjb2xvcjogdmFyKC0tY29sb3ItdGV4dC1tdXRlZCk7IH1cbi5kZXRhaWwtcGFuZWwtdG9wYmFyX19jbG9zZSB7IHdpZHRoOiAyLjFyZW07IGhlaWdodDogMi4xcmVtOyBmbGV4OiBub25lOyBib3JkZXItcmFkaXVzOiAuN3JlbTsgZGlzcGxheTogaW5saW5lLWZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBjb2xvcjogdmFyKC0tY29sb3ItdGV4dC1zZWNvbmRhcnkpOyBiYWNrZ3JvdW5kOiB2YXIoLS1jb2xvci1iZy1lbGV2YXRlZCk7IGJvcmRlcjogMXB4IHNvbGlkIHZhcigtLWNvbG9yLWJvcmRlci1kZWZhdWx0KTsgdHJhbnNpdGlvbjogY29sb3IgLjE2cyBlYXNlLCBiYWNrZ3JvdW5kIC4xNnMgZWFzZSwgYm9yZGVyLWNvbG9yIC4xNnMgZWFzZSwgdHJhbnNmb3JtIC4xNnMgZWFzZTsgfVxuLmRldGFpbC1wYW5lbC10b3BiYXJfX2Nsb3NlOmhvdmVyIHsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtcHJpbWFyeSk7IGJhY2tncm91bmQ6IHZhcigtLWNvbG9yLWJnLWhvdmVyKTsgYm9yZGVyLWNvbG9yOiB2YXIoLS1jb2xvci1ib3JkZXItc3Ryb25nKTsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC0xcHgpOyB9XG4ubm9vci1wbHVnaW4tcGFuZWwtbWFzayB7IHBvc2l0aW9uOiBmaXhlZDsgaW5zZXQ6IDA7IHotaW5kZXg6IHZhcigtLXotbW9kYWwpOyBkaXNwbGF5OiBmbGV4OyBqdXN0aWZ5LWNvbnRlbnQ6IGZsZXgtZW5kOyBiYWNrZ3JvdW5kOiByZ2JhKDAsMCwwLC44KTsgYmFja2Ryb3AtZmlsdGVyOiBibHVyKDhweCk7IH1cbi5ub29yLXBsdWdpbi1wYW5lbCB7IHBvc2l0aW9uOiByZWxhdGl2ZTsgd2lkdGg6IDEwMHZ3OyBoZWlnaHQ6IDEwMHZoOyBiYWNrZ3JvdW5kOiB2YXIoLS1jb2xvci1iZy1zdXJmYWNlKTsgYm9yZGVyLWxlZnQ6IDFweCBzb2xpZCB2YXIoLS1jb2xvci1ib3JkZXItZGVmYXVsdCk7IGJveC1zaGFkb3c6IHZhcigtLXNoYWRvdy14bCk7IG92ZXJmbG93OiBoaWRkZW47IH1cbi5ub29yLXBsdWdpbi1wYW5lbF9fc2Nyb2xsIHsgaGVpZ2h0OiAxMDAlOyBvdmVyZmxvdy15OiBhdXRvOyBwYWRkaW5nOiAxcmVtOyBkaXNwbGF5OiBncmlkOyBnYXA6IDFyZW07IH1cbi5ub29yLXBsdWdpbi1wYW5lbF9faGVhZCB7IHBhZGRpbmc6IDA7IH1cbi5ub29yLXBsdWdpbi1wYW5lbF9fbWV0YSB7IG1pbi13aWR0aDogMDsgZGlzcGxheTogZ3JpZDsgZ2FwOiAuMnJlbTsgfVxuLm5vb3ItcGx1Z2luLXBhbmVsX19leWVicm93IHsgZm9udC1zaXplOiAuNzJyZW07IGxldHRlci1zcGFjaW5nOiAuMDhlbTsgdGV4dC10cmFuc2Zvcm06IHVwcGVyY2FzZTsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtbXV0ZWQpOyB9XG4ubm9vci1wbHVnaW4tcGFuZWxfX3RpdGxlIHsgY29sb3I6ICNmZmY7IGZvbnQtd2VpZ2h0OiA3MDA7IGZvbnQtc2l6ZTogMXJlbTsgbGluZS1oZWlnaHQ6IDEuMzU7IH1cbi5ub29yLXBsdWdpbi1wYW5lbF9fYm9keSB7IGRpc3BsYXk6IGdyaWQ7IGdhcDogMXJlbTsgfVxuLm5vb3ItcGx1Z2luLXBhbmVsX19jbG9zZSB7IHBhZGRpbmc6IDA7IH1cbi5ub29yLXBsdWdpbi1pbnB1dCB7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWRpc3BsYXkpOyB9XG4ubm9vci1wbHVnaW4tdGFicyB7IGZvbnQtZmFtaWx5OiB2YXIoLS1mb250LWRpc3BsYXkpOyB9XG4ubm9vci1wbHVnaW4tdGFic19faXRlbSB7IG1pbi1oZWlnaHQ6IDM0cHg7IGJhY2tncm91bmQ6IHRyYW5zcGFyZW50OyBib3JkZXI6IDA7IGN1cnNvcjogcG9pbnRlcjsgfVxuLm5vb3ItcGx1Z2luLWJhZGdlLS1zdWNjZXNzLCAubm9vci1wbHVnaW4tYmFkZ2UtLWdvb2QgeyBib3JkZXItY29sb3I6IHJnYmEoMSwxODEsMTE2LC4yOCk7IGJhY2tncm91bmQ6IHJnYmEoMSwxODEsMTE2LC4xMCk7IGNvbG9yOiAjZmZmOyB9XG4ubm9vci1wbHVnaW4tYmFkZ2UtLWluZm8geyBib3JkZXItY29sb3I6IHJnYmEoMCwxMTcsMjU1LC4zNik7IGJhY2tncm91bmQ6IHJnYmEoMCwxMTcsMjU1LC4xNCk7IGNvbG9yOiAjZmZmOyB9XG4ubm9vci1wbHVnaW4tYmFkZ2UtLXdhcm5pbmcsIC5ub29yLXBsdWdpbi1iYWRnZS0td2FybiB7IGJvcmRlci1jb2xvcjogcmdiYSgyNTUsMTgxLDcxLC4yOCk7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDE4MSw3MSwuMTApOyBjb2xvcjogI2ZmZjsgfVxuLm5vb3ItcGx1Z2luLWJhZGdlLS1lcnJvciwgLm5vb3ItcGx1Z2luLWJhZGdlLS1kYW5nZXIgeyBib3JkZXItY29sb3I6IHJnYmEoMjI3LDI2LDI2LC4yOCk7IGJhY2tncm91bmQ6IHJnYmEoMjI3LDI2LDI2LC4xMCk7IGNvbG9yOiAjZmZmOyB9XG4ubm9vci1wbHVnaW4tY2FyZCB7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1sZyk7IGJhY2tncm91bmQ6IHZhcigtLWNvbG9yLWJnLXN1cmZhY2UpOyBib3JkZXI6IDFweCBzb2xpZCB2YXIoLS1jb2xvci1nbGFzcy1ib3JkZXIpOyBib3gtc2hhZG93OiAwIDFweCAwIHJnYmEoMjU1LDI1NSwyNTUsLjAyKSBpbnNldCwgMCA4cHggMThweCByZ2JhKDAsMCwwLC4xNik7IG92ZXJmbG93OiBoaWRkZW47IH1cblxuXG4ubm9vci1zdWJtaXQtYnRuIHsgcG9zaXRpb246IHJlbGF0aXZlOyBvdmVyZmxvdzogaGlkZGVuOyBtaW4td2lkdGg6IDEwOHB4OyBpc29sYXRpb246IGlzb2xhdGU7IH1cbi5ub29yLXN1Ym1pdC1idG5fX2JhciB7IHBvc2l0aW9uOiBhYnNvbHV0ZTsgaW5zZXQ6IDAgYXV0byAwIDA7IHdpZHRoOiB2YXIoLS1zdWJtaXQtcHJvZ3Jlc3MsIDAlKTsgYmFja2dyb3VuZDogbGluZWFyLWdyYWRpZW50KDkwZGVnLCByZ2JhKDAsMTE3LDI1NSwuNDgpLCByZ2JhKDMzLDIxMiwyNTMsLjM0KSk7IHRyYW5zaXRpb246IHdpZHRoIC4xOHMgZWFzZS1vdXQsIGJhY2tncm91bmQgdmFyKC0tdHJhbnNpdGlvbi1mYXN0KTsgei1pbmRleDogLTE7IH1cbi5ub29yLXN1Ym1pdC1idG5fX3RleHQgeyBwb3NpdGlvbjogcmVsYXRpdmU7IHotaW5kZXg6IDE7IHdoaXRlLXNwYWNlOiBub3dyYXA7IH1cbi5ub29yLXN1Ym1pdC1idG4uaXMtcnVubmluZyB7IGJvcmRlci1jb2xvcjogcmdiYSgzMywyMTIsMjUzLC40NSk7IGJhY2tncm91bmQ6IHJnYmEoMzMsMjEyLDI1MywuMSk7IH1cbi5ub29yLXN1Ym1pdC1idG4uaXMtc3VjY2VzcyB7IGJvcmRlci1jb2xvcjogcmdiYSgxLDE4MSwxMTYsLjQ2KTsgYmFja2dyb3VuZDogcmdiYSgxLDE4MSwxMTYsLjIyKTsgY29sb3I6ICNmZmY7IH1cbi5ub29yLXN1Ym1pdC1idG4uaXMtc3VjY2VzcyAubm9vci1zdWJtaXQtYnRuX19iYXIgeyBiYWNrZ3JvdW5kOiByZ2JhKDEsMTgxLDExNiwuMzYpOyB9XG4ubm9vci1zdWJtaXQtYnRuLmlzLWVycm9yIHsgYm9yZGVyLWNvbG9yOiByZ2JhKDIyNywyNiwyNiwuMzgpOyBiYWNrZ3JvdW5kOiByZ2JhKDIyNywyNiwyNiwuMTQpOyBjb2xvcjogI2ZmZjsgfVxuLm5vb3Itc3VibWl0LWJ0bi5pcy1lcnJvciAubm9vci1zdWJtaXQtYnRuX19iYXIgeyBiYWNrZ3JvdW5kOiByZ2JhKDIyNywyNiwyNiwuMjIpOyB9XG5cbi8qIFByb21vdGVkIHBsdWdpbiBwYXR0ZXJuczogcmV1c2FibGUgTk9PUiBTREsgY29tcG9uZW50cy4gKi9cbi5ub29yLXBsdWdpbi1hY3Rpb24tcm93IHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsgZ2FwOiA4cHg7IGZsZXgtd3JhcDogd3JhcDsgfVxuLm5vb3ItcGx1Z2luLXN0YXQtZ3JpZCB7IGRpc3BsYXk6IGdyaWQ7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogcmVwZWF0KGF1dG8tZml0LCBtaW5tYXgoMTUwcHgsIDFmcikpOyBnYXA6IDEwcHg7IH1cbi5ub29yLXBsdWdpbi1zdGF0LWNhcmQgeyBtaW4taGVpZ2h0OiA1OHB4OyBkaXNwbGF5OiBncmlkOyBhbGlnbi1jb250ZW50OiBjZW50ZXI7IGdhcDogM3B4OyBwYWRkaW5nOiA5cHggMTJweDsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWxnKTsgYm9yZGVyOiAxcHggc29saWQgdmFyKC0tY29sb3ItZ2xhc3MtYm9yZGVyKTsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYmctc3VyZmFjZSk7IGNvbG9yOiBpbmhlcml0OyB0ZXh0LWFsaWduOiBsZWZ0OyBib3gtc2hhZG93OiAwIDFweCAwIHJnYmEoMjU1LDI1NSwyNTUsLjAyKSBpbnNldCwgMCA4cHggMThweCByZ2JhKDAsMCwwLC4xNik7IH1cbmJ1dHRvbi5ub29yLXBsdWdpbi1zdGF0LWNhcmQgeyBjdXJzb3I6IHBvaW50ZXI7IHRyYW5zaXRpb246IGFsbCB2YXIoLS10cmFuc2l0aW9uLWZhc3QpOyB9XG5idXR0b24ubm9vci1wbHVnaW4tc3RhdC1jYXJkOmhvdmVyIHsgdHJhbnNmb3JtOiB0cmFuc2xhdGVZKC0xcHgpOyBib3JkZXItY29sb3I6IHJnYmEoMCwxMTcsMjU1LC4zKTsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYmctZWxldmF0ZWQpOyB9XG4ubm9vci1wbHVnaW4tc3RhdC1jYXJkX19sYWJlbCB7IGZvbnQtc2l6ZTogMTJweDsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtbXV0ZWQpOyB9XG4ubm9vci1wbHVnaW4tc3RhdC1jYXJkX192YWx1ZSB7IGZvbnQtc2l6ZTogMThweDsgY29sb3I6ICNmZmY7IGZvbnQtd2VpZ2h0OiA3NTA7IGxpbmUtaGVpZ2h0OiAxLjE1OyB9XG4ubm9vci1wbHVnaW4tc3RhdC1jYXJkX19oaW50IHsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtbXV0ZWQpOyBmb250LXNpemU6IDExcHg7IGxpbmUtaGVpZ2h0OiAxLjI1OyB9XG4ubm9vci1wbHVnaW4tc3RhdC1jYXJkLS1zdWNjZXNzIHsgYm9yZGVyLWNvbG9yOiByZ2JhKDEsMTgxLDExNiwuMik7IGJhY2tncm91bmQ6IHJnYmEoMSwxODEsMTE2LC4wOCk7IH1cbi5ub29yLXBsdWdpbi1zdGF0LWNhcmQtLWluZm8geyBib3JkZXItY29sb3I6IHJnYmEoMCwxMTcsMjU1LC4yMik7IGJhY2tncm91bmQ6IHJnYmEoMCwxMTcsMjU1LC4wOSk7IH1cbi5ub29yLXBsdWdpbi1zdGF0LWNhcmQtLXdhcm5pbmcgeyBib3JkZXItY29sb3I6IHJnYmEoMjU1LDE4MSw3MSwuMjIpOyBiYWNrZ3JvdW5kOiByZ2JhKDI1NSwxODEsNzEsLjA4KTsgfVxuLm5vb3ItcGx1Z2luLXN0YXQtY2FyZC0tZXJyb3IgeyBib3JkZXItY29sb3I6IHJnYmEoMjI3LDI2LDI2LC4yMik7IGJhY2tncm91bmQ6IHJnYmEoMjI3LDI2LDI2LC4wOCk7IH1cbi5ub29yLXBsdWdpbi1tZWRpYS1jYXJkIHsgd2lkdGg6IDEwMCU7IG1pbi13aWR0aDogMDsgZGlzcGxheTogZmxleDsgZmxleC1kaXJlY3Rpb246IGNvbHVtbjsgb3ZlcmZsb3c6IGhpZGRlbjsgYm9yZGVyLXJhZGl1czogdmFyKC0tcmFkaXVzLWxnKTsgYm9yZGVyOiAxcHggc29saWQgdmFyKC0tY29sb3ItZ2xhc3MtYm9yZGVyKTsgYmFja2dyb3VuZDogdmFyKC0tY29sb3ItYmctc3VyZmFjZSk7IGNvbG9yOiBpbmhlcml0OyB0ZXh0LWRlY29yYXRpb246IG5vbmU7IGJveC1zaGFkb3c6IDAgMXB4IDAgcmdiYSgyNTUsMjU1LDI1NSwuMDIpIGluc2V0LCAwIDhweCAxOHB4IHJnYmEoMCwwLDAsLjE2KTsgdHJhbnNpdGlvbjogYWxsIHZhcigtLXRyYW5zaXRpb24tZmFzdCk7IHRleHQtYWxpZ246IGxlZnQ7IH1cbi5ub29yLXBsdWdpbi1tZWRpYS1jYXJkLS1zaGFycCB7IGJvcmRlci1yYWRpdXM6IDA7IH1cbmJ1dHRvbi5ub29yLXBsdWdpbi1tZWRpYS1jYXJkIHsgY3Vyc29yOiBwb2ludGVyOyB9XG4ubm9vci1wbHVnaW4tbWVkaWEtY2FyZDpob3ZlciB7IHRyYW5zZm9ybTogdHJhbnNsYXRlWSgtMXB4KTsgYm9yZGVyLWNvbG9yOiByZ2JhKDAsMTE3LDI1NSwuMyk7IGJhY2tncm91bmQ6IHZhcigtLWNvbG9yLWJnLWVsZXZhdGVkKTsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX2NvdmVyIHsgYXNwZWN0LXJhdGlvOiAyMTg0IC8gMTQ2ODsgYmFja2dyb3VuZDogcmdiYSgyNTUsMjU1LDI1NSwuMDQpOyBvdmVyZmxvdzogaGlkZGVuOyB9XG4ubm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fY292ZXIuaXMtY2xpY2thYmxlLCAubm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fdGl0bGUuaXMtY2xpY2thYmxlIHsgY3Vyc29yOiBwb2ludGVyOyB9XG4ubm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fY292ZXIgaW1nIHsgd2lkdGg6IDEwMCU7IGhlaWdodDogMTAwJTsgb2JqZWN0LWZpdDogY292ZXI7IGRpc3BsYXk6IGJsb2NrOyB9XG4ubm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fcGxhY2Vob2xkZXIgeyBoZWlnaHQ6IDEwMCU7IGRpc3BsYXk6IGZsZXg7IGFsaWduLWl0ZW1zOiBjZW50ZXI7IGp1c3RpZnktY29udGVudDogY2VudGVyOyBjb2xvcjogdmFyKC0tY29sb3ItdGV4dC1tdXRlZCk7IGZvbnQtc2l6ZTogMTJweDsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX2JvZHkgeyBkaXNwbGF5OiBncmlkOyBnYXA6IDdweDsgcGFkZGluZzogMTBweDsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX3RpdGxlIHsgaGVpZ2h0OiAzOHB4OyBkaXNwbGF5OiAtd2Via2l0LWJveDsgLXdlYmtpdC1saW5lLWNsYW1wOiAyOyAtd2Via2l0LWJveC1vcmllbnQ6IHZlcnRpY2FsOyBvdmVyZmxvdzogaGlkZGVuOyBjb2xvcjogI2ZmZjsgZm9udC1zaXplOiAxM3B4OyBmb250LXdlaWdodDogNzUwOyBsaW5lLWhlaWdodDogMS40MjsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX3RpdGxlLmlzLWNsaWNrYWJsZTpob3ZlciB7IGNvbG9yOiByZ2JhKDI1NSwyNTUsMjU1LC44Mik7IH1cbi5ub29yLXBsdWdpbi1tZWRpYS1jYXJkX19tZXRhIHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBnYXA6IDhweDsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtbXV0ZWQpOyBmb250LXNpemU6IDExcHg7IG1pbi13aWR0aDogMDsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX21ldGEgc3BhbiB7IG92ZXJmbG93OiBoaWRkZW47IHRleHQtb3ZlcmZsb3c6IGVsbGlwc2lzOyB3aGl0ZS1zcGFjZTogbm93cmFwOyB9XG4ubm9vci1wbHVnaW4tbWVkaWEtY2FyZF9fYmFkZ2VzIHsgbWluLWhlaWdodDogMjJweDsgZGlzcGxheTogZmxleDsgZmxleC13cmFwOiB3cmFwOyBnYXA6IDVweDsgfVxuLm5vb3ItcGx1Z2luLW1lZGlhLWNhcmRfX2FjdGlvbnMgeyBkaXNwbGF5OiBmbGV4OyBqdXN0aWZ5LWNvbnRlbnQ6IGZsZXgtZW5kOyBnYXA6IDhweDsgfVxuLm5vb3ItcGx1Z2luLXN0YXRlLS1sb2FkaW5nIHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBjZW50ZXI7IGdhcDogMTBweDsgfVxuLm5vb3ItcGx1Z2luLXNwaW5uZXIgeyB3aWR0aDogMTRweDsgaGVpZ2h0OiAxNHB4OyBib3JkZXItcmFkaXVzOiA1MCU7IGJvcmRlcjogMnB4IHNvbGlkIHJnYmEoMjU1LDI1NSwyNTUsLjE2KTsgYm9yZGVyLXRvcC1jb2xvcjogdmFyKC0tY29sb3ItYnJhbmQpOyBhbmltYXRpb246IG5vb3ItcGx1Z2luLXNwaW4gLjhzIGxpbmVhciBpbmZpbml0ZTsgfVxuQGtleWZyYW1lcyBub29yLXBsdWdpbi1zcGluIHsgdG8geyB0cmFuc2Zvcm06IHJvdGF0ZSgzNjBkZWcpOyB9IH1cbi5ub29yLWRvd25sb2FkZXItZm9ybSB7IGRpc3BsYXk6IGdyaWQ7IGdhcDogMTJweDsgfVxuLm5vb3ItZG93bmxvYWRlci1zdWJtaXQgeyBtaW4td2lkdGg6IDEzMnB4OyB9XG4ubm9vci1kb3dubG9hZGVyLXRleHRhcmVhIHsgbWluLWhlaWdodDogMTIwcHg7IGhlaWdodDogYXV0bzsgcmVzaXplOiB2ZXJ0aWNhbDsgbGluZS1oZWlnaHQ6IDEuNDU7IHBhZGRpbmctdG9wOiAxMHB4OyBwYWRkaW5nLWJvdHRvbTogMTBweDsgfVxuLm5vb3ItZG93bmxvYWRlci10aXRsZS1jb21ibyB7IGRpc3BsYXk6IGdyaWQ7IGdyaWQtdGVtcGxhdGUtY29sdW1uczogbWlubWF4KDAsMWZyKSAxNDRweDsgZ2FwOiA4cHg7IGFsaWduLWl0ZW1zOiBzdHJldGNoOyB9XG4ubm9vci1kb3dubG9hZGVyLXByZXZpZXcgeyBkaXNwbGF5OiBncmlkOyBnYXA6IDEwcHg7IHBhZGRpbmc6IDEycHg7IGJvcmRlci1yYWRpdXM6IHZhcigtLXJhZGl1cy1sZyk7IGJvcmRlcjogMXB4IHNvbGlkIHZhcigtLWNvbG9yLWdsYXNzLWJvcmRlcik7IGJhY2tncm91bmQ6IHJnYmEoMjU1LDI1NSwyNTUsLjAzKTsgfVxuLm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19oZWFkIHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBnYXA6IDEycHg7IGNvbG9yOiB2YXIoLS1jb2xvci10ZXh0LXNlY29uZGFyeSk7IGZvbnQtc2l6ZTogMTJweDsgfVxuLm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19oZWFkIHNwYW4geyBjb2xvcjogI2ZmZjsgZm9udC13ZWlnaHQ6IDcwMDsgfVxuLm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19oZWFkIC5pcy1lcnJvciB7IGNvbG9yOiAjZmY4YTgwOyB9XG4ubm9vci1kb3dubG9hZGVyLXByZXZpZXdfX2ZpbGVzIHsgZGlzcGxheTogZ3JpZDsgZ2FwOiA2cHg7IH1cbi5ub29yLWRvd25sb2FkZXItcHJldmlld19fZmlsZSwgLm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19tb3JlIHsgZGlzcGxheTogZmxleDsgYWxpZ24taXRlbXM6IGNlbnRlcjsganVzdGlmeS1jb250ZW50OiBzcGFjZS1iZXR3ZWVuOyBnYXA6IDEycHg7IGZvbnQtc2l6ZTogMTJweDsgY29sb3I6IHZhcigtLWNvbG9yLXRleHQtc2Vjb25kYXJ5KTsgfVxuLm5vb3ItZG93bmxvYWRlci1wcmV2aWV3X19maWxlIHNwYW4sIC5ub29yLWRvd25sb2FkZXItcHJldmlld19fZmlsZSBlbSB7IG92ZXJmbG93OiBoaWRkZW47IHdoaXRlLXNwYWNlOiBub3dyYXA7IHRleHQtb3ZlcmZsb3c6IGVsbGlwc2lzOyBmb250LXN0eWxlOiBub3JtYWw7IH1cbkBtZWRpYSAobWF4LXdpZHRoOiA2NDBweCkgeyAubm9vci1kb3dubG9hZGVyLXRpdGxlLWNvbWJvIHsgZ3JpZC10ZW1wbGF0ZS1jb2x1bW5zOiAxZnI7IH0gfVxuPC9zdHlsZT5cbiJdLCJmaWxlIjoiL2hvbWUva2luYXgvbm9vci1yZXN0b3JlZC9mcm9udGVuZC9zcmMvdmlld3MvUGx1Z2luSG9zdC52dWUifQ==