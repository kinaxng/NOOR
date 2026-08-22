function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'\"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function encodeRoutePart(value) {
  return encodeURIComponent(String(value || "").trim());
}
function decodeRoutePart(value) {
  try {
    return decodeURIComponent(String(value || "").trim());
  } catch {
    return String(value || "").trim();
  }
}
function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}
function fmtMin(v) {
  const n = Number(v || 0);
  return n ? `${n} \u5206\u949F` : "";
}
function titleOf(item) {
  const code = String(item?.number || item?.code || "").trim();
  const title = String(item?.title || item?.origin_title || "").trim();
  return code ? `[${code}] ${title}` : title;
}
function titleCandidates(item) {
  const code = String(item?.number || item?.code || "").trim();
  const main = String(item?.title || "").trim();
  const smart = String(item?.display_title || item?.smart_title || (code ? `[${code}] ${main}` : main)).trim();
  return [
    { key: "smart", label: "\u667A\u80FD\u4F18\u9009", value: smart, hint: "\u4F18\u5148\u4F7F\u7528\u756A\u53F7+\u6807\u9898\u3002" },
    { key: "main", label: "\u4E3B\u6807\u9898", value: main, hint: "\u4F5C\u54C1\u539F\u59CB\u4E3B\u6807\u9898\u3002" },
    { key: "code", label: "\u7F16\u53F7", value: code, hint: "\u4EC5\u4F7F\u7528\u756A\u53F7\u3002" }
  ].filter((opt) => opt.value);
}
function classifyCategory(item) {
  const code = String(item?.number || item?.code || "").toUpperCase();
  const title = String(item?.title || "").toUpperCase();
  const uncensoredPrefixes = ["HEYZO", "CARIB", "CARIBBEAN", "1PONDO", "10MUSUME", "PACOPACOMAMA", "FC2-PPV", "FC2PPV"];
  if (code.startsWith("FC2") || title.includes("FC2")) return "FC2";
  if (uncensoredPrefixes.some((prefix) => code.startsWith(prefix) || title.includes(prefix))) return "\u65E0\u7801";
  if (code.includes("TUSHY") || code.includes("BRAZZERS") || code.includes("VIXEN") || code.includes("BLACKED") || code.includes("NUBILE") || code.includes("MOFOS")) return "\u6B27\u7F8E";
  return "\u6709\u7801";
}
function magnetLabel(item) {
  const count = Number(item?.magnets_count || 0);
  return count > 0 ? `${count} \u78C1\u94FE` : "";
}
function textHasKeywords(value, keywords) {
  if (value == null) return false;
  if (typeof value === "string") {
    const text = value.toLowerCase();
    return keywords.some((keyword) => text.includes(keyword));
  }
  if (Array.isArray(value)) return value.some((entry) => textHasKeywords(entry, keywords));
  if (typeof value === "object") return Object.values(value).some((entry) => textHasKeywords(entry, keywords));
  return textHasKeywords(String(value), keywords);
}
function detectCnsub(detail) {
  const keywords = ["\u4E2D\u5B57", "\u5B57\u5E55", "\u4E2D\u6587", "\u4E2D\u6587\u5B57\u5E55", "chs", "cht"];
  return textHasKeywords(detail?.categories, keywords) || textHasKeywords(detail?.magnets, keywords) || textHasKeywords(detail?.title, keywords);
}
function detectCracked(detail) {
  const keywords = ["\u7834\u89E3", "\u7834\u89E3\u7248", "\u65E0\u7801\u7834\u89E3", "uncensored leak"];
  return textHasKeywords(detail?.categories, keywords) || textHasKeywords(detail?.magnets, keywords) || textHasKeywords(detail?.title, keywords);
}
function formatReleaseDate(value) {
  if (!value) return "";
  const text = String(value);
  return text.includes("T") ? text.slice(0, 10) : text;
}
function numericScore(value) {
  const n = Number(value || 0);
  return Number.isFinite(n) && n > 0 ? n : 0;
}
function detailCode(video) {
  return String(video?.code || video?.number || "").trim();
}
function detailTitle(video) {
  const code = detailCode(video);
  const title = String(video?.title || video?.origin_title || "").trim();
  return code && title ? `${code} ${title}` : code || title || "\u672A\u77E5\u4F5C\u54C1";
}
function normalizeCode(value) {
  return String(value || "").toUpperCase().replace(/[^A-Z0-9]/g, "");
}
function magnetTone(tag) {
  const text = String(tag || "");
  if (/中字|字幕|中文/i.test(text)) return "success";
  if (/破解|流出/i.test(text)) return "danger";
  if (/高清|HD|4K/i.test(text)) return "info";
  return "neutral";
}
function resourceProviderOrder(resource) {
  const provider = String(resource?.provider || "").trim();
  if (provider === "avdb") return 0;
  if (provider === "mteam-plugin") return 1;
  if (provider === "javdb") return 2;
  return 9;
}
function compactResourceSubtitle(resource) {
  const raw = String(resource?.subtitle || "").trim();
  if (!raw) return "";
  const parts = raw.split("\xB7").map((part) => part.trim()).filter(Boolean);
  if (!parts.length) return raw;
  const compact = [];
  for (const part of parts) {
    if (compact.some((existing) => existing === part)) continue;
    if (String(resource?.provider || "") === "avdb" && compact.some((existing) => existing.includes(part))) continue;
    compact.push(part);
  }
  return compact.join(" \xB7 ");
}
function resourceBadgeModels(resource) {
  const badges = [];
  if (resource?.features?.has_subtitle) badges.push({ label: "\u4E2D\u5B57", tone: "success" });
  if (resource?.features?.is_cracked) badges.push({ label: "\u7834\u89E3", tone: "danger" });
  if (resource?.features?.is_private_tracker) badges.push({ label: "PT", tone: "warning" });
  return badges;
}
function resourceIdentity(resource) {
  const provider = String(resource?.provider || resource?.provider_label || "other").trim().toLowerCase();
  const url = String(resource?.url || resource?.magnet || resource?.download_url || "").trim().toLowerCase();
  if (url) return `${provider}:url:${url}`;
  const id = String(resource?.id || "").trim().toLowerCase();
  if (id) return `${provider}:id:${id}`;
  return `${provider}:title:${String(resource?.title || "").trim().toLowerCase()}:${String(resource?.subtitle || "").trim().toLowerCase()}`;
}
function mergeResources(primary, fallback) {
  const out = [];
  const seen = /* @__PURE__ */ new Set();
  [...Array.isArray(primary) ? primary : [], ...Array.isArray(fallback) ? fallback : []].forEach((resource) => {
    const key = resourceIdentity(resource);
    if (seen.has(key)) return;
    seen.add(key);
    out.push(resource);
  });
  return out;
}
function isPluginUnmountError(error) {
  const name = String(error?.name || "");
  const code = String(error?.code || "");
  const message = String(error?.response?.data?.detail || error?.message || error || "");
  return name === "AbortError" || name === "CanceledError" || code === "ERR_CANCELED" || /unmounted|aborted|canceled|cancelled/i.test(message);
}
async function mount(root, sdk) {
  const state = {
    tab: "latest",
    latestSelectedFilters: ["magnets"],
    latestType: "all",
    latestSort: "update",
    videosFilter: "",
    videosActorId: "",
    videosCategoryIds: [],
    videosMinScore: "",
    videosSort: "created",
    videosOrder: "desc",
    actorSearch: "",
    videoCategories: [],
    videoActors: [],
    videoActorsLoaded: false,
    videoActorsLoading: false,
    videoCategoriesLoaded: false,
    videoCategoriesLoading: false,
    rankingMode: "top250",
    rankingType: 0,
    rankingPeriod: "daily",
    rankingSelectedFilters: [],
    top250Year: "",
    relation: null,
    relationActorMeta: null,
    relationActorSelectedFilters: [],
    relationActorSingleFilter: false,
    relationActorYear: "",
    relationActorSort: "release_desc",
    page: 1,
    limit: 48,
    total: 0,
    items: [],
    loading: false,
    hasLoadedOnce: false,
    loadError: "",
    activePanel: null,
    subscriptionMap: /* @__PURE__ */ new Map()
  };
  const chooserState = {
    modal: null,
    search: ""
  };
  let tabControl = null;
  let resizeTimer = null;
  let loadSeq = 0;
  const initialCode = new URLSearchParams(window.location.search).get("code")?.trim() || "";
  let initialCodeOpened = false;
  let syncingRoute = false;
  let relationActorGenreFilters = [];
  root.innerHTML = "";
  const page = el("div", "javdb-page");
  const header = el("div", "javdb-header-wrap");
  const tabsWrap = el("div", "javdb-tabs-wrap");
  const panelWrap = el("div", "javdb-panel-wrap");
  const loadingStatus = el("div", "javdb-loading-status");
  const filtersWrap = el("div", "javdb-filters-wrap");
  const grid = el("div", "javdb-grid");
  const pager = el("div", "javdb-pager");
  header.append(tabsWrap, loadingStatus, panelWrap, filtersWrap);
  page.append(header, grid, pager);
  root.appendChild(page);
  const tabDefs = [
    { value: "latest", label: "\u6700\u8FD1\u66F4\u65B0", path: "latest" },
    { value: "rankings", label: "\u699C\u5355", path: "rankings" },
    { value: "actors", label: "\u6F14\u5458", path: "actors" },
    { value: "videos", label: "\u67E5\u770B\u8BB0\u5F55", path: "videos" }
  ];
  function currentRouteTab() {
    const subPath = String(sdk.route?.subPath || "").replace(/^\/+|\/+$/g, "");
    const first = subPath.split("/").filter(Boolean)[0];
    return tabDefs.some((tab) => tab.value === first || tab.path === first) ? first : "";
  }
  function currentRouteRelation() {
    const parts = String(sdk.route?.subPath || "").replace(/^\/+|\/+$/g, "").split("/").filter(Boolean);
    const relType = parts[0] || "";
    if (!["actor", "series", "director", "maker", "publisher", "category", "list"].includes(relType)) return null;
    const relId = decodeRoutePart(parts[1] || "");
    if (!relId) return null;
    const label = decodeRoutePart(parts.slice(2).join("/") || relId);
    return { relType, relId, label };
  }
  function relationPath(relType, relId, label) {
    return [relType, encodeRoutePart(relId), encodeRoutePart(label || relId)].filter(Boolean).join("/");
  }
  const initialTab = currentRouteTab();
  if (initialTab) state.tab = initialTab;
  const initialRelation = currentRouteRelation();
  if (initialRelation) {
    state.tab = initialTab || (initialRelation.relType === "actor" ? "actors" : "rankings");
    state.relation = initialRelation;
  }
  const latestFilters = [
    ["magnets", "\u6709\u78C1\u94FE"],
    ["cnsub", "\u4E2D\u5B57"],
    ["cracked", "\u7834\u89E3"]
  ];
  const latestTypes = [
    ["all", "\u5168\u90E8"],
    ["0", "\u6709\u7801"],
    ["1", "\u65E0\u7801"],
    ["2", "\u6B27\u7F8E"],
    ["3", "FC2"],
    ["4", "\u52A8\u6F2B"]
  ];
  const latestSorts = [
    ["update", "\u66F4\u65B0\u65F6\u95F4"],
    ["release", "\u4E0A\u6620\u65E5\u671F"]
  ];
  const rankingModes = [
    ["top250", "TOP250"],
    ["daily", "\u65E5\u699C"],
    ["weekly", "\u5468\u699C"],
    ["monthly", "\u6708\u699C"],
    ["actors", "\u6F14\u5458\u699C"]
  ];
  const rankingTypes = [
    [0, "\u6709\u7801"],
    [1, "\u65E0\u7801"],
    [2, "\u6B27\u7F8E"],
    [3, "FC2"]
  ];
  const rankingPeriods = [
    ["daily", "\u65E5\u699C"],
    ["weekly", "\u5468\u699C"],
    ["monthly", "\u6708\u699C"]
  ];
  const rankingFilters = [
    ["cnsub", "\u4E2D\u5B57"],
    ["cracked", "\u7834\u89E3"]
  ];
  const relationActorBadgeFilters = [
    ["magnets", "\u6709\u78C1\u94FE"],
    ["cnsub", "\u5B57\u5E55"],
    ["cracked", "\u7834\u89E3"]
  ];
  const relationActorSortOptions = [
    { label: "\u6700\u65B0\u4F18\u5148", value: "release_desc" },
    { label: "\u6700\u65E9\u4F18\u5148", value: "release_asc" },
    { label: "\u78C1\u94FE\u6570", value: "magnets_desc" },
    { label: "\u6807\u9898", value: "title_asc" }
  ];
  const videosMinScoreOptions = [
    { label: "\u5168\u90E8\u8BC4\u5206", value: "" },
    { label: "4 \u5206\u53CA\u4EE5\u4E0A", value: "4" },
    { label: "5 \u5206\u53CA\u4EE5\u4E0A", value: "5" },
    { label: "6 \u5206\u53CA\u4EE5\u4E0A", value: "6" },
    { label: "7 \u5206\u53CA\u4EE5\u4E0A", value: "7" },
    { label: "8 \u5206\u53CA\u4EE5\u4E0A", value: "8" },
    { label: "9 \u5206\u53CA\u4EE5\u4E0A", value: "9" }
  ];
  const videosSortOptions = [
    { label: "\u5165\u5E93\u65F6\u95F4", value: "created" },
    { label: "\u4E0A\u6620\u65F6\u95F4", value: "date" },
    { label: "\u66F4\u65B0\u65F6\u95F4", value: "updated" }
  ];
  const videosFilterOptions = [
    ["all", "\u5168\u90E8"],
    ["m", "\u53EF\u4E0B\u8F7D"],
    ["c", "\u5B57\u5E55"],
    ["n", "\u65E0\u8D44\u6E90"]
  ];
  function isActorRankingFrame() {
    return state.tab === "rankings" && state.rankingMode === "actors" && !state.relation;
  }
  function isActorDirectoryFrame() {
    return state.tab === "actors" && !state.relation;
  }
  function rerenderCurrentList() {
    renderFilters();
    renderGrid();
    renderPager();
  }
  function usesRemotePaging() {
    if (state.relation) return true;
    if (state.tab === "latest") return true;
    if (state.tab === "videos") return true;
    if (state.tab === "rankings") return state.rankingMode === "top250";
    return false;
  }
  function latestRemoteFilter() {
    if (state.latestSelectedFilters.includes("cracked")) return "cracked";
    if (state.latestSelectedFilters.includes("cnsub")) return "cnsub";
    if (state.latestSelectedFilters.includes("magnets")) return "magnets";
    return "all";
  }
  function isLatestRemoteBuffered() {
    return state.tab === "latest" && state.latestSelectedFilters.length > 0;
  }
  function estimatePageSize() {
    if (isActorRankingFrame() || isActorDirectoryFrame()) {
      const width = grid.clientWidth || root.clientWidth || window.innerWidth;
      const cardWidth = 236;
      const cols = Math.max(1, Math.floor((width + 16) / cardWidth));
      const rows = window.innerWidth <= 760 ? 5 : 3;
      state.limit = Math.max(cols, cols * rows);
      return;
    }
    if (state.tab === "rankings" && ["daily", "weekly", "monthly"].includes(state.rankingMode)) {
      state.limit = 60;
      return;
    }
    state.limit = 48;
  }
  function setTab(next) {
    if (state.tab === next) return;
    state.tab = next;
    state.page = 1;
    state.latestSelectedFilters = next === "latest" ? ["magnets"] : [];
    state.latestType = "all";
    state.latestSort = "update";
    state.videosFilter = "";
    state.videosActorId = "";
    state.videosCategoryIds = [];
    state.videosMinScore = "";
    state.videosSort = "created";
    state.videosOrder = "desc";
    state.actorSearch = "";
    state.rankingMode = "top250";
    state.rankingType = 0;
    state.rankingPeriod = "daily";
    state.rankingSelectedFilters = [];
    state.top250Year = "";
    state.relation = null;
    if (next === "actors") void ensureVideoActors();
    if (next === "videos") void ensureVideoCategories();
    if (next === "videos") void ensureVideoActors();
    loadData();
  }
  function setRelation(relType, relId, label, options = {}) {
    state.relation = { relType, relId, label };
    state.relationActorMeta = options.meta || null;
    state.relationActorSelectedFilters = [];
    state.relationActorSingleFilter = false;
    state.relationActorYear = "";
    state.relationActorSort = "release_desc";
    relationActorGenreFilters = [];
    state.page = 1;
    if (options.syncRoute !== false && sdk.route?.push) {
      syncingRoute = true;
      sdk.route.push(relationPath(relType, relId, label));
      queueMicrotask(() => {
        syncingRoute = false;
      });
    }
    loadData();
  }
  function syncFromRoute() {
    if (syncingRoute) return;
    const relation = currentRouteRelation();
    if (relation) {
      const current = state.relation || {};
      if (current.relType === relation.relType && current.relId === relation.relId && current.label === relation.label) return;
      setRelation(relation.relType, relation.relId, relation.label, { syncRoute: false });
      renderTabs();
      return;
    }
    const tab = currentRouteTab();
    if (tab && tab !== state.tab) {
      setTab(tab);
      return;
    }
    if (tab && state.relation) {
      state.relation = null;
      state.relationActorMeta = null;
      state.page = 1;
      loadData();
      renderTabs();
    }
  }
  sdk.route?.onChange?.(syncFromRoute);
  function actorRelationYears() {
    const years = /* @__PURE__ */ new Set();
    for (const item of state.items) {
      const year = String(item?.release_date || "").slice(0, 4);
      if (year) years.add(year);
    }
    return [...years].sort((a, b) => Number(b) - Number(a));
  }
  function actorRelationGenres() {
    const counts = /* @__PURE__ */ new Map();
    for (const item of state.items) {
      const values = [
        ...Array.isArray(item?.categories) ? item.categories : [],
        ...Array.isArray(item?.tags) ? item.tags : []
      ];
      for (const entry of values) {
        const name = String(entry?.name || entry?.label || entry || "").trim();
        if (name) counts.set(name, Number(counts.get(name) || 0) + 1);
      }
    }
    return [...counts.entries()].map(([name, count]) => ({ name, count })).sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, "zh-CN"));
  }
  function currentActorMeta() {
    const relId = String(state.relation?.relId || "");
    const relLabel = String(state.relation?.label || "");
    return state.relationActorMeta || state.videoActors.find((item) => String(item?.value || item?.id || item?.external_id || "") === relId) || state.videoActors.find((item) => [item?.label, item?.name, item?.name_zht, item?.other_name].some((value) => String(value || "") === relLabel)) || { label: relLabel, name: relLabel, value: relId };
  }
  function normalizeCategoryOptions(items) {
    return (Array.isArray(items) ? items : []).map((item) => {
      const value = String(item?.id ?? item?.value ?? item?.category_id ?? item?.external_id ?? "").trim();
      const label = String(item?.name ?? item?.label ?? item?.title ?? item?.value ?? "").trim();
      return value && label ? { value, label } : null;
    }).filter(Boolean);
  }
  async function loadSubscriptionStates() {
    try {
      const res = await sdk.api.post("/plugins/subscription-core/actions/overview", { payload: {} });
      const map = /* @__PURE__ */ new Map();
      for (const item of res.data?.items || []) {
        if (!item || item.status === "deleted") continue;
        const key = normalizeCode(item.code);
        if (key) map.set(key, item);
      }
      state.subscriptionMap = map;
    } catch {
      state.subscriptionMap = /* @__PURE__ */ new Map();
    }
  }
  function subscriptionStateFor(videoData) {
    const code = detailCode(videoData);
    if (!code) return null;
    return state.subscriptionMap.get(normalizeCode(code)) || null;
  }
  function subscriptionActionModel(videoData) {
    const sub = subscriptionStateFor(videoData);
    const isInLibrary = !!videoData?.library?.in_library;
    if (sub) {
      const running = ["matched", "submitted", "waiting_quota", "submit_failed"].includes(String(sub.status || ""));
      if (sub.type === "upgrade") return { label: running ? "\u6D17\u7248\u4E2D" : "\u6D17\u7248\u4E2D", state: "upgrade-active", disabled: true };
      return { label: running ? "\u5DF2\u8BA2\u9605" : "\u5DF2\u8BA2\u9605", state: "subscribed", disabled: true };
    }
    return isInLibrary ? { label: "\u6D17\u7248", state: "upgrade", disabled: false } : { label: "\u8BA2\u9605", state: "subscribe", disabled: false };
  }
  async function ensureVideoCategories() {
    if (state.videoCategoriesLoaded || state.videoCategoriesLoading) return;
    state.videoCategoriesLoading = true;
    try {
      const res = await sdk.api.post("/plugins/javdb/actions/categories", { payload: {} });
      state.videoCategories = normalizeCategoryOptions(res.data?.items || []);
      state.videoCategoriesLoaded = true;
      renderFilters();
    } catch {
      state.videoCategories = [];
      state.videoCategoriesLoaded = false;
    } finally {
      state.videoCategoriesLoading = false;
    }
  }
  async function ensureVideoActors() {
    if (state.videoActorsLoaded || state.videoActorsLoading) return;
    state.videoActorsLoading = true;
    try {
      const res = await sdk.api.post("/plugins/javdb/actions/actor_options", { payload: {} });
      state.videoActors = (Array.isArray(res.data?.items) ? res.data.items : []).map((item) => {
        const value = String(item?.external_id ?? item?.id ?? "").trim();
        const label = String(item?.name ?? "").trim();
        return value && label ? { ...item, value, label } : null;
      }).filter(Boolean);
      state.videoActorsLoaded = true;
      renderFilters();
    } catch {
      state.videoActors = [];
      state.videoActorsLoaded = false;
    } finally {
      state.videoActorsLoading = false;
    }
  }
  function filteredItems() {
    if (isActorDirectoryFrame()) {
      const keyword = String(state.actorSearch || "").trim().toLowerCase();
      if (!keyword) return state.items;
      return state.items.filter((item) => [item.name, item.name_zht, item.other_name, item.id, item.external_id].filter(Boolean).join(" ").toLowerCase().includes(keyword));
    }
    if (state.relation?.relType === "actor") {
      const list = state.items.filter((item) => {
        if (state.relationActorSelectedFilters.includes("magnets") && Number(item?.magnets_count || 0) <= 0) return false;
        if (state.relationActorSelectedFilters.includes("cnsub") && !(item?.has_cnsub || item?.play_subtitle)) return false;
        if (state.relationActorSelectedFilters.includes("cracked") && !item?.is_cracked) return false;
        if (state.relationActorSingleFilter && Number(item?.actor_count || 0) > 1) return false;
        if (state.relationActorYear && String(item?.release_date || "").slice(0, 4) !== state.relationActorYear) return false;
        if (relationActorGenreFilters.length) {
          const names = [
            ...Array.isArray(item?.categories) ? item.categories : [],
            ...Array.isArray(item?.tags) ? item.tags : []
          ].map((entry) => String(entry?.name || entry?.label || entry || "").trim());
          if (!relationActorGenreFilters.every((name) => names.includes(name))) return false;
        }
        return true;
      });
      const sorted = [...list];
      if (state.relationActorSort === "release_desc") sorted.sort((a, b) => String(b.release_date || "").localeCompare(String(a.release_date || "")));
      else if (state.relationActorSort === "release_asc") sorted.sort((a, b) => String(a.release_date || "").localeCompare(String(b.release_date || "")));
      else if (state.relationActorSort === "magnets_desc") sorted.sort((a, b) => Number(b.magnets_count || 0) - Number(a.magnets_count || 0));
      else if (state.relationActorSort === "title_asc") sorted.sort((a, b) => titleOf(a).localeCompare(titleOf(b), "zh-CN"));
      return sorted;
    }
    if (state.tab === "latest") {
      return state.items.filter((item) => {
        if (state.latestSelectedFilters.includes("magnets") && Number(item?.magnets_count || 0) <= 0) return false;
        if (state.latestSelectedFilters.includes("cnsub") && !(item?.has_cnsub || item?.play_subtitle)) return false;
        if (state.latestSelectedFilters.includes("cracked") && !item?.is_cracked) return false;
        return true;
      });
    }
    return state.items;
  }
  async function enrichWorkItems(items) {
    const targets = (items || []).filter((item) => item && item.code && !item.__detailEnriched);
    if (!targets.length) return;
    const queue = targets.slice(0, state.relation?.relType === "actor" ? 120 : 80);
    const concurrency = 8;
    let index = 0;
    async function worker() {
      while (index < queue.length) {
        const current = queue[index++];
        try {
          const res = await sdk.api.post("/plugins/javdb/actions/video", { payload: { code: current.code } });
          const detail = res.data?.data || {};
          current.actor_count = Array.isArray(detail.actors) ? detail.actors.length : Number(current.actor_count || 0);
          current.has_cnsub = !!(current.has_cnsub || current.play_subtitle || detectCnsub(detail));
          current.is_cracked = !!(current.is_cracked || detectCracked(detail));
          if (detail.library && typeof detail.library === "object") current.library = detail.library;
          current.__detailEnriched = true;
        } catch {
          current.__detailEnriched = true;
          if (current.actor_count == null) current.actor_count = 0;
        }
      }
    }
    await Promise.all(Array.from({ length: concurrency }, () => worker()));
  }
  function renderTabs() {
    if (!tabControl) {
      tabControl = sdk.ui.tabs({
        tabs: tabDefs,
        value: state.tab,
        route: {
          mode: "path",
          defaultReplace: false,
          subPath: () => sdk.route?.subPath || "",
          push: (path) => sdk.route?.push?.(path),
          replace: (path) => sdk.route?.replace?.(path)
        },
        onChange: setTab
      });
      tabsWrap.appendChild(tabControl);
    }
    tabControl.__noorSetValue?.(state.tab);
  }
  function buildPanelGroup(label, children) {
    if (sdk.ui?.filterPanelGroup) return sdk.ui.filterPanelGroup({ label, items: children });
    if (sdk.ui?.controlPanelGroup) return sdk.ui.controlPanelGroup({ label, items: children });
    const group = el("div", "noor-control-panel__group");
    if (label) group.appendChild(el("span", "noor-control-panel__group-label", label));
    const items = el("div", "noor-control-panel__group-items");
    (Array.isArray(children) ? children : [children]).filter(Boolean).forEach((child) => items.appendChild(child));
    group.appendChild(items);
    return group;
  }
  function buildPanelSection(label, children) {
    if (sdk.ui?.filterPanelSection) return sdk.ui.filterPanelSection({ label, items: children });
    if (sdk.ui?.controlPanelSection) return sdk.ui.controlPanelSection({ label, items: children });
    return buildPanelGroup(label, children);
  }
  function uniqueValues(values) {
    const seen = /* @__PURE__ */ new Set();
    return (Array.isArray(values) ? values : []).map((value) => String(value || "").trim()).filter((value) => value && !seen.has(value) && seen.add(value));
  }
  function pickerMultiLabel(list, values, emptyLabel, unitLabel = "\u9879") {
    const selected = uniqueValues(values);
    if (!selected.length) return emptyLabel;
    const labels = selected.map((value) => (Array.isArray(list) ? list : []).find((item) => String(item.value) === value)?.label).filter(Boolean);
    if (labels.length <= 2) return labels.join(" \xB7 ");
    return `\u5DF2\u9009 ${labels.length} ${unitLabel}`;
  }
  function pickerSingleLabel(list, value, emptyLabel) {
    const current = String(value || "").trim();
    if (!current) return emptyLabel;
    return (Array.isArray(list) ? list : []).find((item) => String(item.value) === current)?.label || emptyLabel;
  }
  function openMultiPickerModal(title, items, currentValues, onApply, emptyLabel = "\u5168\u90E8", titleMeta = "") {
    if (!sdk.ui?.modal) return;
    chooserState.search = "";
    const body = el("div", "noor-control-panel__picker-list");
    const searchWrap = el("div", "noor-control-panel__picker-search");
    const searchInput = sdk.ui.input ? sdk.ui.input({
      value: "",
      placeholder: `\u641C\u7D22${title}`,
      className: "noor-control-panel__search-input",
      onInput: (value) => {
        chooserState.search = String(value || "").trim().toLowerCase();
        renderOptions();
      }
    }) : null;
    if (searchInput) searchWrap.appendChild(searchInput);
    const optionsWrap = el("div", "noor-control-panel__picker-options");
    body.append(searchWrap, optionsWrap);
    let draft = uniqueValues(currentValues);
    const modal = sdk.ui.modal({
      title,
      titleMeta,
      width: "lg",
      content: body,
      footer: [
        sdk.ui.button({
          label: emptyLabel,
          onClick: () => {
            draft = [];
            renderOptions();
          }
        }),
        sdk.ui.button({
          label: "\u5E94\u7528",
          tone: "primary",
          onClick: () => {
            onApply([...draft]);
            modal.close();
          }
        }),
        sdk.ui.button({ label: "\u5173\u95ED", onClick: () => modal.close() })
      ],
      onClose: () => {
        chooserState.modal = null;
      }
    });
    chooserState.modal = modal;
    function renderOptions() {
      optionsWrap.innerHTML = "";
      const keyword = chooserState.search;
      const fullList = [{ label: emptyLabel, value: "" }, ...Array.isArray(items) ? items : []];
      fullList.filter((item) => !keyword || String(item.label || "").toLowerCase().includes(keyword)).forEach((item) => {
        optionsWrap.appendChild(sdk.ui.chip({
          label: item.label,
          active: draft.includes(String(item.value || "")),
          className: "noor-plugin-chip--soft",
          onClick: () => {
            const value = String(item.value || "");
            draft = draft.includes(value) ? draft.filter((entry) => entry !== value) : [...draft, value];
            renderOptions();
          }
        }));
      });
    }
    renderOptions();
  }
  function openSinglePickerModal(title, items, currentValue, onApply, emptyLabel = "\u5168\u90E8") {
    if (!sdk.ui?.modal) return;
    chooserState.search = "";
    const body = el("div", "noor-control-panel__picker-list");
    const searchWrap = el("div", "noor-control-panel__picker-search");
    const searchInput = sdk.ui.input ? sdk.ui.input({
      value: "",
      placeholder: `\u641C\u7D22${title}`,
      className: "noor-control-panel__search-input",
      onInput: (value) => {
        chooserState.search = String(value || "").trim().toLowerCase();
        renderOptions();
      }
    }) : null;
    if (searchInput) searchWrap.appendChild(searchInput);
    const optionsWrap = el("div", "noor-control-panel__picker-options");
    body.append(searchWrap, optionsWrap);
    let draft = String(currentValue || "").trim();
    const modal = sdk.ui.modal({
      title,
      width: "lg",
      content: body,
      footer: [
        sdk.ui.button({
          label: emptyLabel,
          onClick: () => {
            draft = "";
            renderOptions();
          }
        }),
        sdk.ui.button({
          label: "\u5E94\u7528",
          tone: "primary",
          onClick: () => {
            onApply(draft);
            modal.close();
          }
        }),
        sdk.ui.button({ label: "\u5173\u95ED", onClick: () => modal.close() })
      ],
      onClose: () => {
        chooserState.modal = null;
      }
    });
    chooserState.modal = modal;
    function renderOptions() {
      optionsWrap.innerHTML = "";
      const keyword = chooserState.search;
      const fullList = [{ label: emptyLabel, value: "" }, ...Array.isArray(items) ? items : []];
      fullList.filter((item) => !keyword || String(item.label || "").toLowerCase().includes(keyword)).forEach((item) => {
        const value = String(item.value || "");
        optionsWrap.appendChild(sdk.ui.chip({
          label: item.label,
          active: draft === value,
          className: "noor-plugin-chip--soft",
          onClick: () => {
            draft = draft === value ? "" : value;
            renderOptions();
          }
        }));
      });
    }
    renderOptions();
  }
  function buildPickerButton(title, values, options, onApply, emptyLabel, unitLabel, titleMeta = "") {
    const btn = sdk.ui.button({
      label: pickerMultiLabel(options, values, emptyLabel, unitLabel),
      className: `noor-control-panel__picker-btn ${uniqueValues(values).length ? "" : "is-empty"}`.trim(),
      onClick: () => openMultiPickerModal(title, options, values, onApply, emptyLabel, titleMeta)
    });
    return btn;
  }
  function buildSinglePickerButton(title, value, options, onApply, emptyLabel) {
    const current = String(value || "").trim();
    const btn = sdk.ui.button({
      label: pickerSingleLabel(options, current, emptyLabel),
      className: `noor-control-panel__picker-btn ${current ? "" : "is-empty"}`.trim(),
      onClick: () => openSinglePickerModal(title, options, current, onApply, emptyLabel)
    });
    return btn;
  }
  function sortChipLabel(option) {
    if (state.videosSort !== option.value) return option.label;
    return `${option.label} ${state.videosOrder === "asc" ? "\u2191" : "\u2193"}`;
  }
  function renderFilterPanel() {
    panelWrap.innerHTML = "";
    const panelFactory = sdk.ui?.filterPanel || sdk.ui?.controlPanel;
    if (!panelFactory || !sdk.ui?.chip) return;
    const rows = [];
    const chip = (label, active, onClick) => sdk.ui.chip({ label, active, className: "noor-plugin-chip--soft", onClick });
    const select = (value, options, onChange) => sdk.ui?.select ? sdk.ui.select({ value, options, className: "javdb-year-select", onChange }) : null;
    const pushRow = (sections) => {
      const valid = sections.filter(Boolean);
      if (valid.length) rows.push({ sections: valid });
    };
    if (state.relation) {
      if (state.relation.relType === "actor") {
        void ensureVideoActors();
        const actor = currentActorMeta();
        const profile = el("div", "javdb-actor-profile");
        const avatar = el("div", "javdb-actor-profile__avatar");
        const avatarUrl = actor?.avatar_url || "";
        if (avatarUrl) {
          const img = el("img");
          img.src = avatarUrl;
          img.alt = actor?.name_zht || actor?.label || actor?.name || state.relation.label;
          avatar.appendChild(img);
        } else {
          avatar.textContent = String(actor?.name_zht || actor?.label || actor?.name || state.relation.label || "?").slice(0, 1).toUpperCase();
        }
        const info = el("div", "javdb-actor-profile__info");
        info.appendChild(el("strong", "", actor?.name_zht || actor?.label || actor?.name || state.relation.label));
        const aliases = [...new Set([actor?.name, actor?.other_name].filter(Boolean).map((value) => String(value).trim()))];
        if (aliases.length) info.appendChild(el("span", "", aliases.join(" \xB7 ")));
        profile.append(avatar, info);
        pushRow([buildPanelSection("\u6F14\u5458", [profile])]);
        pushRow([
          buildPanelSection("\u7B5B\u9009", [
            chip("\u5168\u90E8", state.relationActorSelectedFilters.length === 0, () => {
              state.relationActorSelectedFilters = [];
              state.page = 1;
              rerenderCurrentList();
            }),
            ...relationActorBadgeFilters.map(([value, label]) => chip(label, state.relationActorSelectedFilters.includes(value), () => {
              state.relationActorSelectedFilters = state.relationActorSelectedFilters.includes(value) ? state.relationActorSelectedFilters.filter((x) => x !== value) : [...state.relationActorSelectedFilters, value];
              state.page = 1;
              rerenderCurrentList();
            })),
            chip("\u5355\u4EBA", state.relationActorSingleFilter, () => {
              state.relationActorSingleFilter = !state.relationActorSingleFilter;
              state.page = 1;
              rerenderCurrentList();
            })
          ])
        ]);
        const yearOptions = [{ label: "\u5168\u90E8\u5E74\u4EFD", value: "" }, ...actorRelationYears().map((year) => ({ label: year, value: year }))];
        const relationYearSelect = select(state.relationActorYear, yearOptions, (value) => {
          state.relationActorYear = String(value || "");
          state.page = 1;
          rerenderCurrentList();
        });
        const relationSortSelect = select(state.relationActorSort, relationActorSortOptions, (value) => {
          state.relationActorSort = String(value || "release_desc");
          state.page = 1;
          rerenderCurrentList();
        });
        pushRow([
          relationYearSelect ? buildPanelSection("\u5E74\u4EFD", [relationYearSelect]) : null,
          relationSortSelect ? buildPanelSection("\u6392\u5E8F", [relationSortSelect]) : null
        ]);
        const genreFilters = actorRelationGenres();
        if (genreFilters.length) {
          pushRow([
            buildPanelSection("\u7C7B\u578B/\u6807\u7B7E", [
              chip("\u5168\u90E8", relationActorGenreFilters.length === 0, () => {
                relationActorGenreFilters = [];
                state.page = 1;
                rerenderCurrentList();
              }),
              ...genreFilters.map((item) => chip(`${item.name} ${item.count}`, relationActorGenreFilters.includes(item.name), () => {
                relationActorGenreFilters = relationActorGenreFilters.includes(item.name) ? relationActorGenreFilters.filter((name) => name !== item.name) : [...relationActorGenreFilters, item.name];
                state.page = 1;
                rerenderCurrentList();
              }))
            ])
          ]);
        }
      } else {
        pushRow([
          buildPanelSection("\u5F53\u524D", [chip(state.relation.label, true, () => {
          })])
        ]);
      }
    } else if (state.tab === "latest") {
      pushRow([
        buildPanelSection("\u7C7B\u578B", latestTypes.map(([value, label]) => chip(label, state.latestType === value, () => {
          state.latestType = value;
          state.page = 1;
          loadData();
        })))
      ]);
      pushRow([
        buildPanelSection("\u6392\u5E8F", latestSorts.map(([value, label]) => chip(label, state.latestSort === value, () => {
          state.latestSort = value;
          state.page = 1;
          loadData();
        })))
      ]);
      pushRow([
        buildPanelSection("\u7B5B\u9009", [
          chip("\u5168\u90E8", state.latestSelectedFilters.length === 0, () => {
            state.latestSelectedFilters = [];
            state.page = 1;
            loadData();
          }),
          ...latestFilters.map(([value, label]) => chip(label, state.latestSelectedFilters.includes(value), () => {
            state.latestSelectedFilters = state.latestSelectedFilters.includes(value) ? state.latestSelectedFilters.filter((x) => x !== value) : [...state.latestSelectedFilters, value];
            state.page = 1;
            loadData();
          }))
        ])
      ]);
    } else if (state.tab === "rankings") {
      pushRow([
        buildPanelSection("\u699C\u5355", rankingModes.map(([value, label]) => chip(label, state.rankingMode === value, () => {
          state.rankingMode = value;
          state.page = 1;
          loadData();
        })))
      ]);
      if (state.rankingMode !== "actors") {
        pushRow([
          buildPanelSection("\u7C7B\u578B", rankingTypes.map(([value, label]) => chip(label, state.rankingType === value, () => {
            state.rankingType = value;
            state.page = 1;
            loadData();
          })))
        ]);
      }
      if (state.rankingMode === "top250") {
        const years = [];
        const currentYear = (/* @__PURE__ */ new Date()).getFullYear();
        for (let y = currentYear; y >= 2e3; y--) years.push({ label: String(y), value: String(y) });
        pushRow([
          buildPanelSection("\u5E74\u4EFD", [
            buildSinglePickerButton("\u5E74\u4EFD", state.top250Year, years, (value) => {
              state.top250Year = String(value || "");
              state.page = 1;
              loadData();
            }, "\u5168\u90E8\u5E74\u4EFD")
          ])
        ]);
      }
      if (state.rankingMode !== "actors") {
        pushRow([
          buildPanelSection("\u7B5B\u9009", [
            chip("\u5168\u90E8", state.rankingSelectedFilters.length === 0, () => {
              state.rankingSelectedFilters = [];
              state.page = 1;
              loadData();
            }),
            ...rankingFilters.map(([value, label]) => chip(label, state.rankingSelectedFilters.includes(value), () => {
              state.rankingSelectedFilters = state.rankingSelectedFilters.includes(value) ? state.rankingSelectedFilters.filter((x) => x !== value) : [...state.rankingSelectedFilters, value];
              state.page = 1;
              loadData();
            }))
          ])
        ]);
      }
    } else if (state.tab === "actors") {
      const input = sdk.ui?.input ? sdk.ui.input({
        value: state.actorSearch,
        placeholder: "\u641C\u7D22\u6F14\u5458\u6216\u522B\u540D",
        className: "javdb-actor-search",
        onInput: (value) => {
          state.actorSearch = String(value || "");
          state.page = 1;
          rerenderCurrentList();
        }
      }) : null;
      pushRow([
        buildPanelSection("\u641C\u7D22", input ? [input] : [])
      ]);
    } else if (state.tab === "videos") {
      pushRow([
        buildPanelSection("\u7B5B\u9009\u65B9\u5F0F", videosFilterOptions.map(([value, label]) => sdk.ui.chip({
          label,
          active: (state.videosFilter || "all") === value,
          className: "noor-plugin-chip--soft",
          onClick: () => {
            state.videosFilter = value === "all" ? "" : value;
            state.page = 1;
            loadData();
          }
        })))
      ]);
      pushRow([
        buildPanelSection("\u6F14\u5458", [
          buildSinglePickerButton("\u6F14\u5458", state.videosActorId, state.videoActors, (value) => {
            state.videosActorId = String(value || "");
            state.page = 1;
            loadData();
          }, "\u5168\u90E8\u6F14\u5458")
        ]),
        buildPanelSection("\u7C7B\u578B", [
          buildPickerButton("\u7C7B\u578B", state.videosCategoryIds, state.videoCategories, (values) => {
            state.videosCategoryIds = uniqueValues(values);
            state.page = 1;
            loadData();
          }, "\u5168\u90E8\u7C7B\u578B", "\u9879", "\u53EF\u591A\u9009")
        ]),
        buildPanelSection("\u6700\u4F4E\u8BC4\u5206", videosMinScoreOptions.map((option) => sdk.ui.chip({
          label: option.label,
          active: String(state.videosMinScore || "") === String(option.value || ""),
          className: "noor-plugin-chip--soft",
          onClick: () => {
            state.videosMinScore = String(option.value || "");
            state.page = 1;
            loadData();
          }
        })))
      ]);
      pushRow([
        buildPanelSection("\u6392\u5E8F\u5B57\u6BB5", videosSortOptions.map((option) => sdk.ui.chip({
          label: sortChipLabel(option),
          active: String(state.videosSort || "") === String(option.value || ""),
          className: "noor-plugin-chip--soft",
          onClick: () => {
            if (state.videosSort === String(option.value || "created")) {
              state.videosOrder = state.videosOrder === "desc" ? "asc" : "desc";
            } else {
              state.videosSort = String(option.value || "created");
              state.videosOrder = "desc";
            }
            state.page = 1;
            loadData();
          }
        })))
      ]);
    }
    if (!rows.length) return;
    panelWrap.appendChild(panelFactory({
      rows,
      collapsible: true,
      collapseKey: state.relation ? `javdb-relation-${state.relation.relType}-filter-panel` : `javdb-${state.tab}-filter-panel`,
      defaultCollapsed: true
    }));
  }
  function renderFilters() {
    filtersWrap.innerHTML = "";
    renderFilterPanel();
    if (state.tab === "videos") {
      void ensureVideoCategories();
      void ensureVideoActors();
    }
  }
  function renderLoadingStatus() {
    loadingStatus.innerHTML = "";
    loadingStatus.style.display = "none";
    if (state.loading) {
      loadingStatus.classList.remove("is-error");
      loadingStatus.style.display = "flex";
      const message = state.hasLoadedOnce && state.items.length ? "\u6B63\u5728\u5237\u65B0\u5F53\u524D\u5217\u8868\u2026" : "\u6B63\u5728\u52A0\u8F7D JAVDB \u6570\u636E\u2026";
      loadingStatus.appendChild(el("span", "javdb-loading-status__bar"));
      loadingStatus.appendChild(el("span", "javdb-loading-status__spinner"));
      loadingStatus.appendChild(el("span", "javdb-loading-status__text", message));
      return;
    }
    if (state.loadError && state.items.length) {
      loadingStatus.style.display = "flex";
      loadingStatus.classList.add("is-error");
      loadingStatus.appendChild(el("span", "javdb-loading-status__text", state.loadError));
      return;
    }
    loadingStatus.classList.remove("is-error");
  }
  function renderSkeletonGrid() {
    const count = Math.max(1, Number(state.limit || 48));
    for (let i = 0; i < count; i++) {
      if (isActorRankingFrame()) {
        const card2 = el("div", "javdb-actor-card javdb-skeleton javdb-skeleton--actor");
        card2.appendChild(el("div", "javdb-skeleton-avatar"));
        card2.appendChild(el("div", "javdb-skeleton-line javdb-skeleton-line--name"));
        card2.appendChild(el("div", "javdb-skeleton-line"));
        grid.appendChild(card2);
        continue;
      }
      const card = el("div", "noor-plugin-media-card noor-plugin-media-card--sharp javdb-card javdb-skeleton");
      card.appendChild(el("div", "noor-plugin-media-card__cover javdb-skeleton-cover"));
      const body = el("div", "noor-plugin-media-card__body");
      body.appendChild(el("div", "noor-plugin-media-card__title javdb-skeleton-title"));
      card.appendChild(body);
      grid.appendChild(card);
    }
  }
  async function loadData() {
    const seq = ++loadSeq;
    estimatePageSize();
    const hadContent = state.hasLoadedOnce && state.items.length > 0;
    state.loading = true;
    state.loadError = "";
    renderLoadingStatus();
    renderFilters();
    renderGrid();
    try {
      const remoteLatestFilter = latestRemoteFilter();
      const action = state.relation ? "related_movies" : state.tab === "rankings" ? state.rankingMode === "actors" ? "actors" : state.rankingMode === "top250" ? "top250" : "rankings" : state.tab === "actors" ? "actor_options" : state.tab;
      const payload = {
        page: state.page,
        limit: state.limit,
        ...state.relation ? { rel_type: state.relation.relType, rel_id: state.relation.relId } : {},
        ...state.tab === "latest" ? { type: state.latestType, filter_by: remoteLatestFilter, filters: [...state.latestSelectedFilters], sort_by: state.latestSort || "update" } : {},
        ...state.tab === "videos" ? {
          ...state.videosFilter ? { filter: state.videosFilter } : {},
          sort: state.videosSort,
          order: state.videosOrder,
          ...state.videosActorId ? { actor_id: state.videosActorId } : {},
          ...state.videosMinScore ? { min_score: state.videosMinScore } : {},
          ...state.videosCategoryIds.length ? { category_ids: [...state.videosCategoryIds] } : {}
        } : {},
        ...state.tab === "rankings" && ["daily", "weekly", "monthly"].includes(state.rankingMode) ? { type: state.rankingType, period: state.rankingMode, filters: [...state.rankingSelectedFilters] } : {},
        ...state.tab === "rankings" && state.rankingMode === "top250" ? { type_value: state.top250Year || String(state.rankingType), filters: [...state.rankingSelectedFilters] } : {},
        ...isActorRankingFrame() ? { type: state.rankingType } : {}
      };
      if (state.relation?.relType === "actor") {
        payload.sort_by = "release";
        payload.order_by = "desc";
      }
      const res = await sdk.api.post(`/plugins/javdb/actions/${action}`, { payload });
      if (seq !== loadSeq) return;
      state.items = res.data.items || [];
      state.total = Number(res.data.total || state.items.length);
      state.hasLoadedOnce = true;
      if (state.items.length && (state.relation?.relType === "actor" || state.tab === "latest" && remoteLatestFilter !== "all")) {
        await enrichWorkItems(state.items);
        if (seq !== loadSeq) return;
      }
      await loadSubscriptionStates();
      if (seq !== loadSeq) return;
    } catch (e) {
      if (isPluginUnmountError(e)) return;
      if (seq !== loadSeq) return;
      const message = e.message || "\u6570\u636E\u52A0\u8F7D\u5931\u8D25";
      sdk.toast.error(message);
      state.loadError = message;
      if (!hadContent) {
        state.items = [];
        state.total = 0;
      }
    }
    if (seq !== loadSeq) return;
    state.loading = false;
    renderLoadingStatus();
    renderFilters();
    renderGrid();
    renderPager();
    if (initialCode && !initialCodeOpened) {
      initialCodeOpened = true;
      void openDetail({ code: initialCode, number: initialCode, id: initialCode });
    }
  }
  function openSubscription(videoData) {
    const codeValue = detailCode(videoData);
    if (!codeValue) {
      sdk.toast?.error?.("\u7F3A\u5C11\u4F5C\u54C1\u756A\u53F7");
      return;
    }
    if (!sdk.subscription?.open) {
      sdk.toast?.error?.("\u8BA2\u9605\u4E2D\u5FC3\u4E0D\u53EF\u7528");
      return;
    }
    return sdk.subscription.open({
      code: codeValue,
      title: detailTitle(videoData),
      cover_url: videoData.cover_url || videoData.thumb_url || "",
      fanart_url: videoData.fanart_url || videoData.cover_url || videoData.thumb_url || "",
      sourcePlugin: "javdb",
      sourceLabel: "JavDB",
      sourceRoute: window.location.pathname + window.location.search,
      sourceContext: "javdb-work",
      defaultMode: "loose",
      requireCracked: false,
      requireSubtitle: false,
      onSuccess: async (result) => {
        sdk.toast?.success?.(result?.created ? "\u8BA2\u9605\u5DF2\u521B\u5EFA" : "\u8BA2\u9605\u5DF2\u5B58\u5728");
        await loadSubscriptionStates();
        renderGrid();
      }
    });
  }
  function renderGrid() {
    grid.innerHTML = "";
    grid.classList.toggle("javdb-grid--actors", isActorRankingFrame() || isActorDirectoryFrame());
    grid.classList.toggle("is-refreshing", state.loading && state.items.length > 0);
    const items = filteredItems();
    if (state.loading && !items.length) {
      renderSkeletonGrid();
      return;
    }
    if (!items.length) {
      grid.appendChild(sdk.ui.emptyState({ text: "\u6682\u65E0\u7B26\u5408\u6761\u4EF6\u7684\u4F5C\u54C1" }));
      return;
    }
    const start = (state.page - 1) * state.limit;
    const visible = usesRemotePaging() ? items : items.slice(start, start + state.limit);
    visible.forEach((item) => {
      if (isActorRankingFrame() || isActorDirectoryFrame()) {
        const actorTitle = item.name_zht || item.name || "-";
        const actorMeta = [item.name, item.other_name].filter(Boolean).join(" \xB7 ");
        const actorCard = el("button", "javdb-actor-card");
        actorCard.type = "button";
        actorCard.onclick = () => setRelation("actor", item.id || item.external_id || item.value, actorTitle, { meta: { ...item, value: item.id || item.external_id || item.value, label: actorTitle } });
        const avatar = el("div", "javdb-actor-avatar");
        if (item.avatar_url) {
          const img = el("img");
          img.src = item.avatar_url;
          img.alt = actorTitle;
          avatar.appendChild(img);
        }
        actorCard.appendChild(avatar);
        actorCard.appendChild(el("div", "javdb-actor-name", actorTitle));
        actorCard.appendChild(el("div", "javdb-actor-meta", actorMeta || ""));
        const badgeRow = el("div", "javdb-actor-badges");
        if (item.uncensored) badgeRow.appendChild(sdk.ui.badge({ label: "\u65E0\u7801", tone: "info" }));
        actorCard.appendChild(badgeRow);
        grid.appendChild(actorCard);
        return;
      }
      const badges = [];
      const magnetText = magnetLabel(item);
      if (magnetText) badges.push(sdk.ui.badge({ label: magnetText, tone: "info" }));
      if (item.has_cnsub || item.play_subtitle) badges.push(sdk.ui.badge({ label: "\u4E2D\u5B57", tone: "success" }));
      if (item.is_cracked) badges.push(sdk.ui.badge({ label: "\u7834\u89E3", tone: "danger" }));
      if (item.library?.in_library) badges.push(sdk.ui.badge({ label: "\u5DF2\u5165\u5E93", tone: "info" }));
      const actionModel = subscriptionActionModel(item);
      const subscribeAction = el("button", `noor-plugin-badge javdb-subscribe-action javdb-subscribe-action--${actionModel.state}`, actionModel.label);
      subscribeAction.type = "button";
      subscribeAction.disabled = !!actionModel.disabled;
      subscribeAction.onclick = (event) => {
        event.stopPropagation();
        event.preventDefault();
        if (!actionModel.disabled) openSubscription(item);
      };
      const card = sdk.ui.mediaCard({
        title: titleOf(item),
        cover: item.cover_url || item.thumb_url,
        sharp: true,
        meta: [classifyCategory(item), fmtMin(item.duration)].filter(Boolean),
        badges,
        coverOnClick: () => openDetail(item),
        titleOnClick: () => openDetail(item),
        className: "javdb-card"
      });
      const badgeHost = card.querySelector(".noor-plugin-media-card__badges");
      if (badgeHost) badgeHost.appendChild(subscribeAction);
      grid.appendChild(card);
    });
  }
  function renderPager() {
    pager.innerHTML = "";
    let totalItems = Number(state.total || 0);
    if (state.tab === "latest" && state.latestSelectedFilters.length && latestRemoteFilter() === "all") {
      totalItems = filteredItems().length;
    }
    if (totalItems <= state.limit) return;
    pager.appendChild(sdk.ui.pagination({
      page: state.page,
      totalPages: Math.ceil(totalItems / state.limit),
      onPage: (next) => {
        state.page = next;
        if (usesRemotePaging()) {
          loadData();
          window.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        renderGrid();
        renderPager();
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    }));
  }
  async function openDetail(item) {
    if (state.activePanel) state.activePanel.close();
    const code = item.number || item.code || item.id;
    const panel = sdk.ui.panel({ title: "\u5F71\u7247\u8BE6\u60C5", eyebrow: "JavDB", scroll: true });
    state.activePanel = panel;
    panel.body.appendChild(sdk.ui.loadingState({ text: "\u6B63\u5728\u8C03\u53D6\u8BE6\u60C5\u6570\u636E..." }));
    try {
      let rebuildProviderGroups = function(keepSelection = true) {
        const providerMap = /* @__PURE__ */ new Map();
        resources.forEach((resource) => {
          const key = String(resource.provider || resource.provider_label || "other");
          const existing = providerMap.get(key) || {
            key,
            label: String(resource.provider_label || resource.provider || "\u672A\u77E5\u6765\u6E90"),
            count: 0,
            isPrivateTracker: false
          };
          existing.count += 1;
          existing.isPrivateTracker = existing.isPrivateTracker || !!resource?.features?.is_private_tracker;
          providerMap.set(key, existing);
        });
        providerGroups = Array.from(providerMap.values()).sort((a, b) => resourceProviderOrder(a) - resourceProviderOrder(b));
        if (!keepSelection || !providerGroups.some((group) => group.key === selectedProvider)) {
          selectedProvider = providerGroups[0]?.key || "";
        }
      }, renderProviderBar = function() {
        providerBar.innerHTML = "";
        providerGroups.forEach((group) => {
          const pill = document.createElement("button");
          pill.type = "button";
          pill.className = `javdb-resource-pill${selectedProvider === group.key ? " is-active" : ""}`;
          if (group.isPrivateTracker) pill.dataset.tone = "warning";
          pill.textContent = `${group.label} ${group.count}`;
          pill.onclick = () => {
            if (selectedProvider === group.key) return;
            selectedProvider = group.key;
            renderProviderBar();
            renderResourceList();
          };
          providerBar.appendChild(pill);
        });
      }, renderResourceList = function() {
        magnetCount.textContent = `${resources.length}`;
        magnetList.innerHTML = "";
        const visibleResources = resources.filter((resource) => String(resource.provider || resource.provider_label || "other") === selectedProvider);
        if (!visibleResources.length) {
          magnetList.appendChild(el("div", "javdb-no-data", "\u6682\u65E0\u78C1\u94FE\u8D44\u6E90"));
          return;
        }
        visibleResources.forEach((resource) => {
          const row = el("div", "javdb-magnet-row");
          const info = el("div", "javdb-magnet-info");
          info.appendChild(el("div", "javdb-magnet-name", resource.title || "\u672A\u77E5\u8D44\u6E90"));
          const magnetMeta = el("div", "javdb-magnet-meta");
          [compactResourceSubtitle(resource)].filter(Boolean).forEach((text, index, array) => {
            magnetMeta.appendChild(el("span", "javdb-magnet-meta__item", text));
            if (index < array.length - 1) magnetMeta.appendChild(el("span", "javdb-magnet-meta__dot", "\xB7"));
          });
          info.appendChild(magnetMeta);
          const tagRow = el("div", "javdb-magnet-tags");
          resourceBadgeModels(resource).forEach((tag) => {
            tagRow.appendChild(sdk.ui.badge({ label: tag.label, tone: tag.tone }));
          });
          if (tagRow.childNodes.length) info.appendChild(tagRow);
          const pushBtn = sdk.ui.submitButton({
            idleLabel: "\u63A8\u9001\u4E0B\u8F7D",
            successLabel: "\u5DF2\u52A0\u5165",
            onClick: () => openResourceDownload(resource)
          });
          const compatibleDownloaders = Array.isArray(resource.compatible_downloaders) ? resource.compatible_downloaders : [];
          if (compatibleDownloaders.length) {
            pushBtn.title = `\u53EF\u7528\u4E0B\u8F7D\u5668\uFF1A${compatibleDownloaders.join(" / ")}`;
          }
          row.append(info, pushBtn);
          magnetList.appendChild(row);
        });
      }, renderResources = function(keepSelection = true) {
        rebuildProviderGroups(keepSelection);
        providerBar.innerHTML = "";
        if (providerGroups.length) {
          renderProviderBar();
          if (!providerBar.parentNode) magnetSection.insertBefore(providerBar, magnetList);
        } else if (providerBar.parentNode) {
          providerBar.remove();
        }
        renderResourceList();
      };
      const expectedMagnetsCount = Number(item?.magnets_count || item?.magnet_count || 0);
      const res = await sdk.api.post("/plugins/javdb/actions/video", { payload: { code, expected_magnets_count: expectedMagnetsCount } });
      const video = res.data.data;
      panel.body.innerHTML = "";
      const content = el("div", "javdb-detail");
      const previewList = Array.isArray(video.previews) ? video.previews : [];
      const images = [video.cover_url, ...previewList].filter(Boolean);
      const isSingleImage = images.length <= 1;
      const gallery = el("div", "javdb-detail-gallery");
      if (isSingleImage) gallery.classList.add("is-single");
      const galleryViewport = el("div", "javdb-detail-gallery__viewport");
      const galleryRail = el("div", "javdb-detail-gallery__rail");
      images.forEach((src) => {
        const frame = el("button", "javdb-gallery-frame");
        frame.type = "button";
        const img = el("img", "javdb-gallery-img");
        img.src = src;
        img.alt = detailTitle(video);
        frame.onclick = () => sdk.ui.previewImage?.(src, images);
        frame.appendChild(img);
        galleryRail.appendChild(frame);
      });
      if (!images.length) galleryRail.appendChild(sdk.ui.emptyState({ text: "\u6682\u65E0\u5C01\u9762\u4E0E\u5267\u7167" }));
      galleryViewport.appendChild(galleryRail);
      gallery.appendChild(galleryViewport);
      if (images.length > 1) {
        const scrollGallery = (direction) => {
          const amount = Math.max(320, galleryViewport.clientWidth);
          galleryViewport.scrollBy({ left: direction * amount, behavior: "smooth" });
        };
        const prevBtn = sdk.ui.button({ label: "\u2039", className: "javdb-gallery-nav javdb-gallery-nav--prev", onClick: () => scrollGallery(-1) });
        const nextBtn = sdk.ui.button({ label: "\u203A", className: "javdb-gallery-nav javdb-gallery-nav--next", onClick: () => scrollGallery(1) });
        const syncGalleryNav = () => {
          const maxLeft = Math.max(0, galleryViewport.scrollWidth - galleryViewport.clientWidth);
          const left = galleryViewport.scrollLeft;
          prevBtn.classList.toggle("javdb-is-hidden", left <= 4);
          nextBtn.classList.toggle("javdb-is-hidden", left >= maxLeft - 4);
        };
        galleryViewport.addEventListener("scroll", syncGalleryNav, { passive: true });
        requestAnimationFrame(syncGalleryNav);
        gallery.append(prevBtn, nextBtn);
      }
      content.appendChild(gallery);
      const hero = el("section", "javdb-detail-section javdb-detail-hero");
      const heroHead = el("div", "javdb-detail-hero__head");
      const heroMeta = el("div", "javdb-detail-hero__meta");
      const codeText = detailCode(video);
      if (codeText) heroMeta.appendChild(el("span", "javdb-detail-hero__code", codeText));
      heroMeta.appendChild(el("h2", "javdb-detail-hero__title", detailTitle(video)));
      const subtitle = String(video?.origin_title || "").trim();
      if (subtitle && subtitle !== String(video?.title || "").trim()) {
        heroMeta.appendChild(el("p", "javdb-detail-hero__subtitle", subtitle));
      }
      const heroBadges = el("div", "javdb-detail-hero__badges");
      const categoryText = classifyCategory(video);
      if (categoryText) heroBadges.appendChild(sdk.ui.badge({ label: categoryText, tone: "info" }));
      if (detectCnsub(video)) heroBadges.appendChild(sdk.ui.badge({ label: "\u4E2D\u5B57", tone: "success" }));
      if (detectCracked(video)) heroBadges.appendChild(sdk.ui.badge({ label: "\u7834\u89E3", tone: "danger" }));
      if (Number(video?.magnets?.length || 0) > 0) heroBadges.appendChild(sdk.ui.badge({ label: `${video.magnets.length} \u78C1\u94FE`, tone: "info" }));
      heroMeta.appendChild(heroBadges);
      heroHead.appendChild(heroMeta);
      hero.appendChild(heroHead);
      const overview = el("div", "javdb-detail-overview");
      [
        ["\u4E0A\u6620\u65E5\u671F", formatReleaseDate(video?.date || video?.release_date)],
        ["\u65F6\u957F", fmtMin(video?.duration)],
        ["\u8BC4\u5206", numericScore(video?.score) ? String(video.score) : ""],
        ["\u6765\u6E90", String(video?.source || video?.site || "JavDB").trim()]
      ].filter(([, value]) => value).forEach(([label, value]) => {
        const card = el("div", "javdb-overview-card");
        card.appendChild(el("span", "javdb-overview-card__label", label));
        card.appendChild(el("strong", "javdb-overview-card__value", value));
        overview.appendChild(card);
      });
      if (overview.childNodes.length) hero.appendChild(overview);
      content.appendChild(hero);
      const detailSection = el("section", "javdb-detail-section");
      const detailHead = el("div", "javdb-detail-section__head");
      detailHead.appendChild(el("span", "javdb-detail-section__title", "\u4F5C\u54C1\u4FE1\u606F"));
      detailSection.appendChild(detailHead);
      const meta = el("div", "javdb-detail-meta");
      const appendMetaRow = (label, source, relType) => {
        if (!source) return;
        const list = (Array.isArray(source) ? source : [source]).filter(Boolean);
        if (!list.length) return;
        const row = el("div", "javdb-meta-row");
        row.appendChild(el("span", "javdb-meta-label", label));
        const badges = el("div", "javdb-meta-badges");
        list.forEach((entry) => {
          const name = entry?.name || entry?.label || String(entry || "");
          const id = entry?.id || entry?.external_id || name;
          badges.appendChild(sdk.ui.badge({
            label: name,
            tone: relType === "category" ? void 0 : "info",
            onClick: () => {
              panel.close();
              setRelation(relType, id, name);
            }
          }));
        });
        row.appendChild(badges);
        meta.appendChild(row);
      };
      appendMetaRow("\u6F14\u5458", video.actors, "actor");
      appendMetaRow("\u7CFB\u5217", video.series, "series");
      appendMetaRow("\u5BFC\u6F14", video.director, "director");
      appendMetaRow("\u5236\u4F5C\u5546", video.maker, "maker");
      appendMetaRow("\u53D1\u884C\u5546", video.publisher, "publisher");
      appendMetaRow("\u7C7B\u578B", video.categories, "category");
      if (meta.childNodes.length) {
        detailSection.appendChild(meta);
        content.appendChild(detailSection);
      }
      const fallbackResources = (Array.isArray(video.magnets) ? video.magnets : []).map((magnet, index) => ({
        id: `javdb:fallback:${index}`,
        provider: "javdb",
        provider_label: "JavDB",
        title: magnet.name || detailTitle(video),
        subtitle: [magnet.size || "", magnet.date || "", magnet.site || "JavDB"].filter(Boolean).join(" \xB7 "),
        url: magnet.magnet || "",
        tags: Array.isArray(magnet.tags) ? magnet.tags : [],
        features: {
          has_subtitle: textHasKeywords(magnet.tags || magnet.name || "", ["\u4E2D\u5B57", "\u5B57\u5E55", "\u4E2D\u6587", "\u4E2D\u6587\u5B57\u5E55", "chs", "cht"]),
          is_cracked: textHasKeywords(magnet.tags || magnet.name || "", ["\u7834\u89E3", "\u7834\u89E3\u7248", "\u65E0\u7801\u7834\u89E3", "uncensored leak"]),
          is_private_tracker: false
        },
        requirements: String(magnet.magnet || "").startsWith("magnet:?") ? { accepts_public_magnet: true } : {},
        compatible_downloaders: [],
        preferred_downloader: null
      }));
      const sortResources = (list) => list.slice().sort((a, b) => {
        const providerDiff = resourceProviderOrder(a) - resourceProviderOrder(b);
        if (providerDiff) return providerDiff;
        const subA = String(a?.subtitle || "");
        const subB = String(b?.subtitle || "");
        return subA.localeCompare(subB);
      });
      let resources = sortResources(fallbackResources);
      const openResourceDownload = async (resource) => {
        const resolved = (await sdk.api.post("/plugins/resources/resolve-download", {
          provider_id: resource.provider,
          item: resource
        })).data;
        const resolvedItem = resolved?.item || resource;
        const resolvedUrl = resolved?.url || resolvedItem?.url;
        const downloaderIds = Array.isArray(resolvedItem?.compatible_downloaders) ? resolvedItem.compatible_downloaders.filter(Boolean) : [];
        const downloaderId = resolvedItem?.preferred_downloader || downloaderIds[0];
        if (!downloaderId) throw new Error("\u6CA1\u6709\u517C\u5BB9\u7684\u4E0B\u8F7D\u5668");
        if (!resolvedUrl) throw new Error("\u8D44\u6E90\u94FE\u63A5\u89E3\u6790\u5931\u8D25");
        return sdk.downloads.open({
          downloaderId,
          downloaderIds,
          url: resolvedUrl,
          title: titleOf(video),
          rename: titleCandidates(video)[0]?.value || titleOf(video),
          titleOptions: titleCandidates(video)
        });
      };
      const magnetSection = el("section", "javdb-detail-section");
      const magnetHead = el("div", "javdb-detail-section__head");
      magnetHead.appendChild(el("span", "javdb-detail-section__title", "\u4E0B\u8F7D\u8D44\u6E90"));
      const magnetCount = el("span", "javdb-detail-section__meta", `${resources.length}`);
      magnetHead.appendChild(magnetCount);
      magnetSection.appendChild(magnetHead);
      const magnetList = el("div", "javdb-magnets");
      const providerBar = el("div", "javdb-resource-providers");
      let providerGroups = [];
      let selectedProvider = "";
      magnetSection.appendChild(magnetList);
      renderResources(false);
      content.appendChild(magnetSection);
      panel.body.appendChild(content);
      sdk.api.post("/plugins/resources/search", {
        query: { code, title: titleOf(item), expected_magnets_count: expectedMagnetsCount },
        providers: ["javdb", "avdb", "mteam-plugin"],
        limit_per_plugin: 6
      }).then((resourceRes) => {
        if (state.activePanel !== panel) return;
        const brokerResources = Array.isArray(resourceRes?.data?.items) ? resourceRes.data.items : [];
        resources = sortResources(mergeResources(brokerResources, fallbackResources));
        renderResources(true);
      }).catch((error) => {
        if (isPluginUnmountError(error)) return;
        if (state.activePanel === panel && !resources.length) {
          magnetList.innerHTML = "";
          magnetList.appendChild(el("div", "javdb-no-data", "\u8D44\u6E90\u641C\u7D22\u5931\u8D25\uFF0C\u6682\u65E0\u78C1\u94FE\u8D44\u6E90"));
        }
      });
    } catch (e) {
      if (isPluginUnmountError(e)) return;
      sdk.toast.error(e.message || "\u52A0\u8F7D\u8BE6\u60C5\u5931\u8D25");
      panel.close();
    }
  }
  renderTabs();
  loadData();
  const onResize = () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const oldLimit = state.limit;
      estimatePageSize();
      if (state.limit !== oldLimit) {
        state.page = 1;
        if (isActorRankingFrame()) {
          renderGrid();
          renderPager();
        } else {
          renderPager();
        }
      }
    }, 120);
  };
  window.addEventListener("resize", onResize);
  return () => {
    loadSeq += 1;
    window.removeEventListener("resize", onResize);
    clearTimeout(resizeTimer);
    chooserState.modal?.close?.();
    chooserState.modal = null;
    state.activePanel?.close();
    state.activePanel = null;
    root.innerHTML = "";
  };
}
export {
  mount
};
