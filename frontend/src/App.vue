<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

type Job = {
  id: string;
  job_type: string;
  emby_item_name: string;
  status: string;
  progress: number;
  detail?: string;
  error_message?: string;
  phase_label?: string;
  phase_progress?: number;
};
type PluginSetting = {
  type?: "string" | "password" | "number" | "boolean";
  label?: string;
  description?: string;
  min?: number;
  max?: number;
};
type Plugin = {
  id: string;
  name?: string;
  description?: string;
  type?: string;
  enabled: boolean;
  loaded: boolean;
  config?: Record<string, unknown>;
  default_config?: Record<string, unknown>;
  config_schema?: Record<string, PluginSetting>;
};
type Recommendation = {
  code: string;
  title: string;
  cover_url?: string;
  release_date?: string;
  score?: number;
  recommendation_score?: number;
  actors: string[];
  categories: string[];
  is_today_increment: boolean;
  in_library?: boolean;
  subscribed?: boolean;
  has_cnsub?: boolean;
  is_cracked?: boolean;
  source_tags?: Array<{ id?: string; label?: string; date?: string }>;
};
type RecommendationStats = {
  candidates?: number;
  today_increment?: number;
  in_library?: number;
  subscribed?: number;
};
type JavdbItem = {
  code: string;
  title: string;
  cover_url?: string;
  release_date?: string;
  actors?: string[];
  categories?: string[];
  magnets_count?: number;
};
type JavdbDetail = JavdbItem & {
  origin_title?: string;
  duration?: string;
  maker?: string;
  series?: string;
  director?: string;
  magnets?: Array<{ name?: string; size?: string; size_mb?: number }>;
};
type Actor = {
  id: string;
  name: string;
  avatar_url?: string;
  name_zht?: string;
  other_name?: string;
};
type EmbyActor = {
  id: string;
  name: string;
  display_name?: string;
  sort_name?: string;
  avatar_url?: string;
  name_jp?: string;
  name_zh_cn?: string;
  name_zh_tw?: string;
  aliases?: string;
  overview?: string;
  provider_ids?: Record<string, string>;
  emby_url?: string;
};
type HardlinkGroup = {
  code: string;
  hardlink_count?: number;
  orphan_count?: number;
  status?: string;
  entries?: Array<{ source_path?: string; hardlink_paths?: string[] }>;
};
type HardlinkDeletePreview = {
  message?: string;
  detail?: string;
  deleted_files?: string[];
  deleted_dirs?: string[];
  removed_files?: string[];
  removed_dirs?: string[];
  skipped_files?: string[];
  errors?: string[];
  [key: string]: unknown;
};
type HardlinkScanGroup = { source_dir: string; hardlink_dir: string };
type EmbySettings = {
  server: string;
  api_key: string;
  user_id: string;
  enabled_library_ids: string[];
};
type NetworkSettings = {
  acceleration_mode: string;
  http_proxy: string;
  github_mirror: string;
  hf_mirror: string;
  pip_mirror: string;
  hf_token: string;
};
type SystemLog = {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  source: string;
};
type MediaLibrary = { id: string; name: string; collection_type?: string };
type MediaItem = {
  id: string;
  name: string;
  type?: string;
  poster_path?: string;
  date_created?: string;
  path?: string;
  tags?: {
    is_cracked?: boolean;
    has_chinese?: boolean;
    is_uncensored?: boolean;
    is_leaked?: boolean;
  };
};
type FaceFusionSourceImage = {
  id: string;
  name: string;
  preview_url: string;
  path: string;
  size?: number;
};
type LadaChoice = {
  id: string;
  name?: string;
  downloaded?: boolean;
  description_zh?: string;
};
type LadaInfo = {
  devices?: Array<{ id: string; name?: string }>;
  detection_models?: LadaChoice[];
  restoration_models?: LadaChoice[];
  encoding_presets?: Array<{ id: string; name?: string; desc?: string }>;
};
type SubtitleFile = {
  filename: string;
  path: string;
  size: number;
  ext: string;
};
type OnlineSubtitle = {
  name: string;
  url: string;
  ext: string;
  language: string;
  source: string;
  source_key?: string;
  source_type?: string;
};
type Subscription = {
  id: string;
  code?: string;
  title?: string;
  type?: "subscribe" | "upgrade";
  status?: string;
  mode?: string;
  require_cracked?: boolean;
  require_subtitle?: boolean;
  push_status?: string;
  last_submit_error?: string;
  retry_after_at?: string;
};
type BackgroundTask = {
  plugin_id: string;
  plugin_name?: string;
  id: string;
  title?: string;
  status?: string;
  summary?: string;
  detail?: string;
  last_run_at?: string;
  last_finished_at?: string;
  metrics?: Record<string, unknown>;
};
type Resource = {
  id: string;
  title?: string;
  subtitle?: string;
  url?: string;
  size_bytes?: number;
  cover_url?: string;
  compatible_downloaders?: string[];
  preferred_downloader?: string;
  metadata?: { video_code?: string };
};
type Page =
  | "overview"
  | "library"
  | "recommendations"
  | "javdb"
  | "actors"
  | "subscriptions"
  | "files"
  | "tasks"
  | "plugins"
  | "settings";

const page = ref<Page>("overview");
let applyingBrowserRoute = false;

function storedCoverBlurOverride(): boolean | null {
  try {
    const value = window.localStorage.getItem("noor.cover_blur.browser");
    return value === "1" ? true : value === "0" ? false : null;
  } catch {
    return null;
  }
}
const loading = ref(true);
const error = ref("");
const healthy = ref(false);
const jobs = ref<Job[]>([]);
const selectedJob = ref<Job | null>(null);
const selectedJobLogs = ref<string[]>([]);
const jobLogsLoading = ref(false);
const jobCancelling = ref("");
const taskTab = ref<"queue" | "background">("queue");
const backgroundTasks = ref<BackgroundTask[]>([]);
const backgroundTasksLoading = ref(false);
const plugins = ref<Plugin[]>([]);
const selectedPlugin = ref<Plugin | null>(null);
const pluginConfig = ref<Record<string, unknown>>({});
const pluginConfigSaving = ref(false);
const pluginTesting = ref(false);
const pluginTestMessage = ref("");
const settings = ref<Record<string, unknown>>({});
const embySettings = ref<EmbySettings>({
  server: "",
  api_key: "",
  user_id: "",
  enabled_library_ids: [],
});
const networkSettings = ref<NetworkSettings>({
  acceleration_mode: "mirror",
  http_proxy: "",
  github_mirror: "",
  hf_mirror: "",
  pip_mirror: "",
  hf_token: "",
});
const coreSettingsLoading = ref(false);
const embySettingsSaving = ref(false);
const networkSettingsSaving = ref(false);
const coverBlurGlobal = ref(false);
const coverBlurBrowserOverride = ref<boolean | null>(storedCoverBlurOverride());
const coverBlurSaving = ref(false);
const systemLogs = ref<SystemLog[]>([]);
const systemLogsLoading = ref(false);
const webhookInstructionsVisible = ref(false);
const recommendations = ref<Recommendation[]>([]);
const recommendationMode = ref<"latest" | "full">("latest");
const recommendationTotal = ref(0);
const recommendationStats = ref<RecommendationStats>({});
const recommendationPool = ref<{ total?: number; today_increment?: number }>({});
const recommendationSubscribing = ref("");
const javdbItems = ref<JavdbItem[]>([]);
const javdbQuery = ref("");
const javdbLoading = ref(false);
const javdbDetail = ref<JavdbDetail | null>(null);
const actors = ref<Actor[]>([]);
const actorQuery = ref("");
const actorLoading = ref(false);
const selectedActor = ref<Actor | null>(null);
const actorMovies = ref<JavdbItem[]>([]);
const fileTab = ref<"hardlinks" | "actor-management">("hardlinks");
const hardlinkGroups = ref<HardlinkGroup[]>([]);
const hardlinksLoading = ref(false);
const hardlinksScanning = ref(false);
const hardlinkDeleteGroup = ref<HardlinkGroup | null>(null);
const hardlinkDeletePreview = ref<HardlinkDeletePreview | null>(null);
const hardlinkDeleteLoading = ref(false);
const hardlinkDeleting = ref(false);
const hardlinkScanGroups = ref<HardlinkScanGroup[]>([]);
const hardlinkConfigLoading = ref(false);
const hardlinkConfigSaving = ref(false);
const embyActors = ref<EmbyActor[]>([]);
const embyActorsTotal = ref(0);
const embyActorsLoading = ref(false);
const embyActorQuery = ref("");
const embyActorSort = ref<"name" | "recent">("name");
const actorDisplayLanguage = ref<"zh_cn" | "zh_tw" | "jp">("zh_cn");
const mappingStatus = ref<{
  exists?: boolean;
  record_count?: number;
  configured_path?: string;
  configured_root?: string;
} | null>(null);
const mdcNgPath = ref("");
const mappingSaving = ref(false);
const selectedEmbyActor = ref<EmbyActor | null>(null);
const selectedEmbyActorMovies = ref<JavdbItem[]>([]);
const duplicateGroups = ref<Array<{ key: string; actors: EmbyActor[] }>>([]);
const duplicatesLoading = ref(false);
const gfriendsCandidates = ref<
  Array<{ url: string; remote_url: string; name: string; aliases?: string[] }>
>([]);
const gfriendsLoading = ref(false);
const avatarSaving = ref(false);
const mediaLibraries = ref<MediaLibrary[]>([]);
const mediaItems = ref<MediaItem[]>([]);
const mediaTotal = ref(0);
const mediaLoading = ref(false);
const mediaLibraryId = ref("");
const mediaOffset = ref(0);
const mediaPageSize = 48;
const selectedMediaItem = ref<MediaItem | null>(null);
const mediaDeleteGroup = ref<HardlinkGroup | null>(null);
const mediaDeleteLoading = ref("");
const subscriptions = ref<Subscription[]>([]);
const subscriptionLoading = ref(false);
const subscriptionCreating = ref(false);
const subscriptionCode = ref("");
const globalSearchOpen = ref(false);
const globalSearchQuery = ref("");
const globalSearchLoading = ref(false);
const globalSearchGroups = ref<
  Array<{ provider: string; provider_name?: string; items: Resource[] }>
>([]);
const globalResourceSubmitting = ref("");
const facefusionOpen = ref(false);
const facefusionSources = ref<FaceFusionSourceImage[]>([]);
const selectedFacefusionSourceIds = ref<string[]>([]);
const facefusionLoading = ref(false);
const facefusionSubmitting = ref(false);
const facefusionProcessors = ref<string[]>(["face_swapper"]);
const facefusionProvider = ref("cuda");
const facefusionSettings = ref<Record<string, string | number>>({});
const facefusionSettingsLoading = ref(false);
const facefusionSettingsSaving = ref(false);
const whisperSubmitting = ref(false);
const ladaSubmitting = ref(false);
const ladaInfoLoading = ref(false);
const ladaSettingsSaving = ref(false);
const ladaInfo = ref<LadaInfo>({});
const ladaConfig = ref<{ cli_path: string }>({ cli_path: "" });
const ladaDefaults = ref<Record<string, string | number | boolean>>({});
const whisperSettings = ref<Record<string, unknown>>({});
const whisperSettingsLoading = ref(false);
const whisperSettingsSaving = ref(false);
const subtitlesOpen = ref(false);
const subtitlesLoading = ref(false);
const subtitleSearchLoading = ref(false);
const subtitleDownloading = ref("");
const localSubtitles = ref<SubtitleFile[]>([]);
const onlineSubtitles = ref<OnlineSubtitle[]>([]);

const title = computed(
  () =>
    ({
      overview: "概览",
      library: "媒体库",
      recommendations: "推荐中心",
      javdb: "JavDB",
      actors: "演员",
      subscriptions: "订阅中心",
      files: "文件",
      tasks: "任务",
      plugins: "插件",
      settings: "设置",
    })[page.value],
);

const pagePaths: Record<Page, string> = {
  overview: "/",
  library: "/library",
  recommendations: "/recommendations",
  javdb: "/javdb",
  actors: "/actors",
  subscriptions: "/subscriptions",
  files: "/files",
  tasks: "/tasks",
  plugins: "/plugins",
  settings: "/settings",
};

function pageFromPath(pathname = window.location.pathname): Page {
  const normalized = pathname.replace(/\/+$/, "") || "/";
  if (/^\/actor\/emby\/[^/]+$/.test(normalized)) return "files";
  if (/^\/javdb\/[^/]+$/.test(normalized)) return "javdb";
  if (/^\/library\/[^/]+$/.test(normalized)) return "library";
  return (
    (Object.entries(pagePaths).find(([, path]) => path === normalized)?.[0] as Page | undefined) ||
    "overview"
  );
}

function mediaItemIdFromPath(pathname = window.location.pathname) {
  const match = pathname.replace(/\/+$/, "").match(/^\/library\/([^/]+)$/);
  if (!match) return "";
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return "";
  }
}

function javdbCodeFromPath(pathname = window.location.pathname) {
  const match = pathname.replace(/\/+$/, "").match(/^\/javdb\/([^/]+)$/);
  if (!match) return "";
  try {
    return decodeURIComponent(match[1]).trim().toUpperCase();
  } catch {
    return "";
  }
}

function embyActorIdFromPath(pathname = window.location.pathname) {
  const match = pathname.replace(/\/+$/, "").match(/^\/actor\/emby\/([^/]+)$/);
  if (!match) return "";
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return "";
  }
}
const runningJobs = computed(() =>
  jobs.value.filter((job) =>
    ["queued", "running", "blocked"].includes(job.status),
  ),
);
const mediaPage = computed(
  () => Math.floor(mediaOffset.value / mediaPageSize) + 1,
);
const mediaPageCount = computed(() =>
  Math.max(1, Math.ceil(mediaTotal.value / mediaPageSize)),
);
const filteredActors = computed(() => {
  const query = actorQuery.value.trim().toLowerCase();
  if (!query) return actors.value;
  return actors.value.filter((actor) =>
    [actor.name, actor.name_zht, actor.other_name]
      .join(" ")
      .toLowerCase()
      .includes(query),
  );
});
const coverBlurActive = computed(
  () => coverBlurBrowserOverride.value ?? coverBlurGlobal.value,
);
const embyWebhookUrl = computed(() => {
  if (typeof window === "undefined") return "/api/webhooks/emby";
  return `${window.location.origin}/api/webhooks/emby`;
});

const facefusionSettingLabels: Record<string, string> = {
  facefusion_python_path: "Python 路径",
  facefusion_video_memory_strategy: "显存策略",
  facefusion_system_memory_limit: "系统内存限制",
  facefusion_download_providers: "模型下载源",
  facefusion_face_swapper_model: "换脸模型",
  facefusion_face_swapper_pixel_boost: "像素增强",
  facefusion_face_swapper_weight: "换脸权重",
  facefusion_face_enhancer_model: "人脸增强模型",
  facefusion_face_enhancer_blend: "人脸增强融合",
  facefusion_face_enhancer_weight: "人脸增强权重",
  facefusion_frame_enhancer_model: "帧增强模型",
  facefusion_frame_enhancer_blend: "帧增强融合",
  facefusion_face_detector_model: "人脸检测模型",
  facefusion_face_detector_size: "检测尺寸",
  facefusion_face_detector_score: "检测分数",
  facefusion_face_detector_angles: "检测角度",
  facefusion_face_detector_margin: "检测边距",
  facefusion_face_landmarker_model: "关键点模型",
  facefusion_face_landmarker_score: "关键点分数",
  facefusion_face_selector_order: "人脸选择顺序",
  facefusion_face_selector_gender: "性别筛选",
  facefusion_face_selector_age_start: "年龄下限",
  facefusion_face_selector_age_end: "年龄上限",
  facefusion_face_selector_race: "人种筛选",
  facefusion_reference_frame_number: "参考帧",
  facefusion_reference_face_position: "参考人脸位置",
  facefusion_reference_face_distance: "参考人脸距离",
  facefusion_face_mask_types: "遮罩类型",
  facefusion_face_mask_areas: "遮罩区域",
  facefusion_face_mask_regions: "遮罩部位",
  facefusion_face_mask_blur: "遮罩模糊",
  facefusion_face_mask_padding: "遮罩边距",
  facefusion_face_occluder_model: "遮挡模型",
  facefusion_face_parser_model: "解析模型",
  facefusion_output_video_preset: "视频预设",
  facefusion_output_video_quality: "视频质量",
  facefusion_output_video_scale: "视频缩放",
  facefusion_output_video_fps: "输出帧率",
  facefusion_output_audio_encoder: "音频编码器",
  facefusion_output_audio_quality: "音频质量",
  facefusion_output_audio_volume: "音量",
  facefusion_output_image_quality: "图片质量",
  facefusion_output_image_scale: "图片缩放",
  facefusion_temp_frame_format: "临时帧格式",
  facefusion_log_level: "日志级别",
};
const facefusionSettingsGroups = computed(() => {
  const groups = [
    {
      title: "运行时",
      keys: [
        "facefusion_python_path",
        "facefusion_video_memory_strategy",
        "facefusion_system_memory_limit",
        "facefusion_download_providers",
      ],
    },
    {
      title: "处理器",
      keys: [
        "facefusion_face_swapper_model",
        "facefusion_face_swapper_pixel_boost",
        "facefusion_face_swapper_weight",
        "facefusion_face_enhancer_model",
        "facefusion_face_enhancer_blend",
        "facefusion_face_enhancer_weight",
        "facefusion_frame_enhancer_model",
        "facefusion_frame_enhancer_blend",
      ],
    },
    {
      title: "检测与遮罩",
      keys: [
        "facefusion_face_detector_model",
        "facefusion_face_detector_size",
        "facefusion_face_detector_score",
        "facefusion_face_detector_angles",
        "facefusion_face_detector_margin",
        "facefusion_face_landmarker_model",
        "facefusion_face_landmarker_score",
        "facefusion_face_mask_types",
        "facefusion_face_mask_areas",
        "facefusion_face_mask_regions",
        "facefusion_face_mask_blur",
        "facefusion_face_mask_padding",
        "facefusion_face_occluder_model",
        "facefusion_face_parser_model",
      ],
    },
    {
      title: "人脸选择",
      keys: [
        "facefusion_face_selector_order",
        "facefusion_face_selector_gender",
        "facefusion_face_selector_age_start",
        "facefusion_face_selector_age_end",
        "facefusion_face_selector_race",
        "facefusion_reference_frame_number",
        "facefusion_reference_face_position",
        "facefusion_reference_face_distance",
      ],
    },
    {
      title: "输出",
      keys: [
        "facefusion_output_video_preset",
        "facefusion_output_video_quality",
        "facefusion_output_video_scale",
        "facefusion_output_video_fps",
        "facefusion_output_audio_encoder",
        "facefusion_output_audio_quality",
        "facefusion_output_audio_volume",
        "facefusion_output_image_quality",
        "facefusion_output_image_scale",
        "facefusion_temp_frame_format",
        "facefusion_log_level",
      ],
    },
  ];
  return groups
    .map((group) => ({
      ...group,
      fields: group.keys.filter((key) => key in facefusionSettings.value),
    }))
    .filter((group) => group.fields.length);
});

function actorName(actor: EmbyActor) {
  if (actorDisplayLanguage.value === "jp")
    return actor.name_jp || actor.sort_name || actor.name;
  if (actorDisplayLanguage.value === "zh_tw")
    return actor.name_zh_tw || actor.name_zh_cn || actor.name_jp || actor.name;
  return actor.name_zh_cn || actor.name_jp || actor.name;
}

function providerUrl(provider: string, value: string) {
  const key = provider.toLowerCase();
  if (key === "tmdb")
    return `https://www.themoviedb.org/person/${encodeURIComponent(value)}`;
  if (key === "imdb")
    return `https://www.imdb.com/name/${encodeURIComponent(value)}`;
  return "";
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok)
    throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

function applyCoreSettings(data: Record<string, unknown>) {
  settings.value = data;
  const emby = data.emby as Partial<EmbySettings> | undefined;
  const network = data.network as Partial<NetworkSettings> | undefined;
  if (emby) {
    embySettings.value = {
      server: String(emby.server || ""),
      api_key: String(emby.api_key || ""),
      user_id: String(emby.user_id || ""),
      enabled_library_ids: Array.isArray(emby.enabled_library_ids)
        ? emby.enabled_library_ids.map(String)
        : [],
    };
  }
  if (network) {
    networkSettings.value = {
      acceleration_mode: String(network.acceleration_mode || "mirror"),
      http_proxy: String(network.http_proxy || ""),
      github_mirror: String(network.github_mirror || ""),
      hf_mirror: String(network.hf_mirror || ""),
      pip_mirror: String(network.pip_mirror || ""),
      hf_token: String(network.hf_token || ""),
    };
  }
}

async function loadCoreSettings() {
  coreSettingsLoading.value = true;
  try {
    applyCoreSettings(await request<Record<string, unknown>>("/api/settings"));
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "基础设置读取失败";
  } finally {
    coreSettingsLoading.value = false;
  }
}

async function saveEmbySettings() {
  embySettingsSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/settings/emby", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(embySettings.value),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    await loadCoreSettings();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "Emby 设置保存失败";
  } finally {
    embySettingsSaving.value = false;
  }
}

async function saveNetworkSettings() {
  networkSettingsSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/settings/network", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(networkSettings.value),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    await loadCoreSettings();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "网络设置保存失败";
  } finally {
    networkSettingsSaving.value = false;
  }
}

async function loadSystemLogs() {
  systemLogsLoading.value = true;
  try {
    const result = await request<{ logs?: SystemLog[] }>("/api/logs?tail=12");
    systemLogs.value = result.logs || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "系统日志读取失败";
  } finally {
    systemLogsLoading.value = false;
  }
}

async function loadUiSettings() {
  try {
    const settings = await request<{ cover_blur?: boolean }>("/api/ui-settings");
    coverBlurGlobal.value = Boolean(settings.cover_blur);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "界面设置读取失败";
  }
}

async function saveCoverBlurGlobal() {
  coverBlurSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/ui-settings", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ cover_blur: coverBlurGlobal.value }),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    const result = (await response.json()) as { cover_blur?: boolean };
    coverBlurGlobal.value = Boolean(result.cover_blur);
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "封面模糊设置保存失败";
  } finally {
    coverBlurSaving.value = false;
  }
}

function toggleCoverBlurBrowser() {
  const next = !coverBlurActive.value;
  coverBlurBrowserOverride.value = next;
  try {
    window.localStorage.setItem("noor.cover_blur.browser", next ? "1" : "0");
  } catch {
    // The control remains effective for this session when browser storage is unavailable.
  }
}

function handleCoverBlurShortcut(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null;
  if (
    event.key.toLowerCase() !== "h" ||
    target?.matches("input, textarea, select, [contenteditable='true']")
  )
    return;
  event.preventDefault();
  toggleCoverBlurBrowser();
}

async function copyEmbyWebhookUrl() {
  try {
    await navigator.clipboard.writeText(embyWebhookUrl.value);
  } catch {
    const input = document.createElement("textarea");
    input.value = embyWebhookUrl.value;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.append(input);
    input.select();
    const copied = document.execCommand("copy");
    input.remove();
    if (!copied) {
      error.value = "复制失败，请手动复制 Webhook 地址";
      return;
    }
  }
  webhookInstructionsVisible.value = true;
}

async function pluginAction<T>(
  plugin: string,
  action: string,
  payload: Record<string, unknown> = {},
): Promise<T> {
  const response = await fetch(`/api/plugins/${plugin}/actions/${action}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ payload }),
  });
  if (!response.ok)
    throw new Error(`${response.status} ${response.statusText}`);
  return response.json() as Promise<T>;
}

async function togglePlugin(plugin: Plugin) {
  error.value = "";
  try {
    const response = await fetch(
      `/api/plugins/${encodeURIComponent(plugin.id)}/enabled`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ enabled: !plugin.enabled }),
      },
    );
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    plugin.enabled = !plugin.enabled;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "插件状态更新失败";
  }
}

async function openPluginConfig(plugin: Plugin) {
  error.value = "";
  try {
    const response = await request<{ config: Record<string, unknown> }>(
      `/api/plugins/${encodeURIComponent(plugin.id)}/config`,
    );
    selectedPlugin.value = plugin;
    pluginConfig.value = {
      ...(plugin.default_config || {}),
      ...(response.config || {}),
    };
    pluginTestMessage.value = "";
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "插件配置读取失败";
  }
}

function canTestPlugin(plugin: Plugin | null) {
  return [
    "javdb",
    "gfriends",
    "qbittorrent",
    "xunlei-remote",
    "transmission",
    "mteam-plugin",
    "avdb",
  ].includes(plugin?.id || "");
}

async function testPlugin() {
  const plugin = selectedPlugin.value;
  if (!plugin || !canTestPlugin(plugin)) return;
  pluginTesting.value = true;
  pluginTestMessage.value = "";
  error.value = "";
  try {
    const result = await pluginAction<{ ok?: boolean; message?: string }>(
      plugin.id,
      "test",
    );
    pluginTestMessage.value =
      result.message || (result.ok ? "连接成功" : "连接失败");
  } catch (cause) {
    pluginTestMessage.value =
      cause instanceof Error ? cause.message : "连接测试失败";
  } finally {
    pluginTesting.value = false;
  }
}

async function savePluginConfig() {
  const plugin = selectedPlugin.value;
  if (!plugin) return;
  pluginConfigSaving.value = true;
  error.value = "";
  try {
    const response = await fetch(
      `/api/plugins/${encodeURIComponent(plugin.id)}/config`,
      {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ config: pluginConfig.value }),
      },
    );
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    plugin.config = { ...pluginConfig.value };
    selectedPlugin.value = null;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "插件配置保存失败";
  } finally {
    pluginConfigSaving.value = false;
  }
}

async function loadRecommendations() {
  const data = await pluginAction<{
    items: Recommendation[];
    total?: number;
    stats?: RecommendationStats;
    pool?: { total?: number; today_increment?: number };
  }>(
    "av-recommend",
    "recommendations",
    { limit: 48, source_mode: recommendationMode.value },
  );
  recommendations.value = data.items || [];
  recommendationTotal.value = Number(data.total || 0);
  recommendationStats.value = data.stats || {};
  recommendationPool.value = data.pool || {};
}

async function setRecommendationMode(mode: "latest" | "full") {
  recommendationMode.value = mode;
  loading.value = true;
  error.value = "";
  try {
    await loadRecommendations();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "推荐加载失败";
  } finally {
    loading.value = false;
  }
}

async function feedback(
  item: Recommendation,
  kind: "like" | "dislike" | "ignore",
) {
  try {
    await pluginAction("av-recommend", "feedback", {
      kind,
      code: item.code,
      actors: item.actors,
      categories: item.categories,
    });
    await loadRecommendations();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "保存反馈失败";
  }
}

async function subscribeRecommendation(item: Recommendation) {
  if (!item.code || item.subscribed) return;
  recommendationSubscribing.value = item.code;
  error.value = "";
  try {
    await pluginAction("subscription-core", "create", {
      code: item.code,
      title: item.title,
      cover_url: item.cover_url || "",
      source_plugin_id: "av-recommend",
      source_label: "推荐中心",
    });
    await loadRecommendations();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "创建订阅失败";
  } finally {
    recommendationSubscribing.value = "";
  }
}

async function loadJavdb() {
  javdbLoading.value = true;
  error.value = "";
  try {
    const query = javdbQuery.value.trim();
    const result = query
      ? await pluginAction<{ items: JavdbItem[] }>("javdb", "search", {
          q: query,
          page: 1,
          limit: 30,
        })
      : await pluginAction<{ items: JavdbItem[] }>("javdb", "latest", {
          page: 1,
          limit: 30,
          type: "all",
          filter_by: "magnets",
          sort_by: "update",
        });
    javdbItems.value = result.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "JavDB 加载失败";
  } finally {
    javdbLoading.value = false;
  }
}

async function openJavdbDetail(item: JavdbItem, pushRoute = true) {
  const code = item.code.trim().toUpperCase();
  if (!code) return;
  if (pushRoute) {
    const path = `/javdb/${encodeURIComponent(code)}`;
    if (window.location.pathname !== path)
      window.history.pushState({ javdbCode: code }, "", path);
  }
  try {
    const result = await pluginAction<{ data: JavdbDetail }>("javdb", "video", {
      code,
    });
    javdbDetail.value = result.data || null;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "作品详情加载失败";
  }
}

async function viewJavdbDetail(item: JavdbItem) {
  page.value = "javdb";
  await openJavdbDetail(item);
}

function closeJavdbDetail() {
  javdbDetail.value = null;
  if (javdbCodeFromPath()) window.history.replaceState({ page: "javdb" }, "", "/javdb");
}

async function loadMediaLibrary(resetOffset = false) {
  if (resetOffset) mediaOffset.value = 0;
  mediaLoading.value = true;
  error.value = "";
  try {
    if (!mediaLibraries.value.length) {
      const libraries = await request<{ libraries: MediaLibrary[] }>(
        "/api/media-library/libraries",
      );
      mediaLibraries.value = libraries.libraries || [];
    }
    const params = new URLSearchParams({
      limit: String(mediaPageSize),
      offset: String(mediaOffset.value),
    });
    if (mediaLibraryId.value) params.set("library_id", mediaLibraryId.value);
    const data = await request<{ items: MediaItem[]; total: number }>(
      `/api/media-library/items?${params.toString()}`,
    );
    mediaItems.value = data.items || [];
    mediaTotal.value = data.total || 0;
  } catch (cause) {
    mediaItems.value = [];
    mediaTotal.value = 0;
    error.value = cause instanceof Error ? cause.message : "媒体库加载失败";
  } finally {
    mediaLoading.value = false;
  }
}

async function loadBackgroundTasks() {
  backgroundTasksLoading.value = true;
  error.value = "";
  try {
    const result = await request<{ items?: BackgroundTask[] }>(
      "/api/plugins/background/tasks",
    );
    backgroundTasks.value = result.items || [];
  } catch (cause) {
    backgroundTasks.value = [];
    error.value = cause instanceof Error ? cause.message : "后台任务读取失败";
  } finally {
    backgroundTasksLoading.value = false;
  }
}

async function openTasks(tab: "queue" | "background" = "queue") {
  page.value = "tasks";
  taskTab.value = tab;
  if (tab === "background") await loadBackgroundTasks();
}

async function openJob(job: Job) {
  selectedJob.value = job;
  selectedJobLogs.value = [];
  jobLogsLoading.value = true;
  error.value = "";
  try {
    const result = await request<{ logs?: string[] }>(
      `/api/jobs/${encodeURIComponent(job.id)}/logs`,
    );
    selectedJobLogs.value = result.logs || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "任务日志读取失败";
  } finally {
    jobLogsLoading.value = false;
  }
}

async function cancelJob(job: Job) {
  if (!["queued", "running", "blocked"].includes(job.status)) return;
  jobCancelling.value = job.id;
  error.value = "";
  try {
    const response = await fetch(
      `/api/jobs/${encodeURIComponent(job.id)}/cancel`,
      { method: "POST" },
    );
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    await refresh();
    if (selectedJob.value?.id === job.id)
      await openJob({ ...job, status: "cancelled" });
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "取消任务失败";
  } finally {
    jobCancelling.value = "";
  }
}

async function openMediaItem(item: MediaItem, pushRoute = true) {
  if (pushRoute) {
    const path = `/library/${encodeURIComponent(item.id)}`;
    if (window.location.pathname !== path)
      window.history.pushState({ mediaItemId: item.id }, "", path);
  }
  try {
    selectedMediaItem.value = await request<MediaItem>(
      `/api/media-library/item/${encodeURIComponent(item.id)}`,
    );
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "媒体详情加载失败";
  }
}

function closeMediaItem() {
  selectedMediaItem.value = null;
  facefusionOpen.value = false;
  subtitlesOpen.value = false;
  if (mediaItemIdFromPath()) window.history.replaceState({ page: "library" }, "", "/library");
}

function mediaCode(item: MediaItem) {
  const match = item.name.match(/\b([a-z]{2,6}-\d+)\b/i);
  return match?.[1]?.toUpperCase() || "";
}

function isFacefusionItem(item: MediaItem) {
  const value = `${item.name} ${item.path || ""}`;
  return /facefusion|(?:^|[._\s-])ff(?:$|[._\s-])/i.test(value);
}

async function openMediaDeleteMenu(item: MediaItem) {
  const code = mediaCode(item);
  if (!code) {
    error.value = "无法从作品名称识别番号，不能执行删除";
    return;
  }
  mediaDeleteLoading.value = item.id;
  error.value = "";
  try {
    if (!hardlinkGroups.value.length) await loadHardlinks();
    const group = hardlinkGroups.value.find((candidate) => candidate.code === code);
    if (!group?.entries?.length) {
      throw new Error("未找到已扫描的硬链接记录，请先在文件 - 硬链接中扫描后再删除");
    }
    mediaDeleteGroup.value = group;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "读取作品删除信息失败";
  } finally {
    mediaDeleteLoading.value = "";
  }
}

async function openFacefusion() {
  if (!selectedMediaItem.value?.path) {
    error.value = "当前媒体项目没有可处理的本地文件路径";
    return;
  }
  facefusionOpen.value = true;
  facefusionLoading.value = true;
  error.value = "";
  try {
    const result = await request<{
      items?: FaceFusionSourceImage[];
      files?: FaceFusionSourceImage[];
    }>(
      "/api/facefusion/source-images",
    );
    facefusionSources.value = result.items || result.files || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "源脸图片库加载失败";
  } finally {
    facefusionLoading.value = false;
  }
}

function toggleFacefusionSource(sourceId: string) {
  selectedFacefusionSourceIds.value =
    selectedFacefusionSourceIds.value.includes(sourceId)
      ? selectedFacefusionSourceIds.value.filter((id) => id !== sourceId)
      : [...selectedFacefusionSourceIds.value, sourceId];
}

async function uploadFacefusionSources(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  if (!files.length) return;
  facefusionLoading.value = true;
  error.value = "";
  try {
    const body = new FormData();
    files.forEach((file) => body.append("files", file));
    const response = await fetch("/api/facefusion/source-images", {
      method: "POST",
      body,
    });
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    const result = (await response.json()) as {
      items?: FaceFusionSourceImage[];
      files?: FaceFusionSourceImage[];
    };
    facefusionSources.value = result.items || result.files || facefusionSources.value;
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "源脸图片上传失败";
  } finally {
    input.value = "";
    facefusionLoading.value = false;
  }
}

async function deleteFacefusionSource(source: FaceFusionSourceImage) {
  if (!source.id) return;
  facefusionLoading.value = true;
  error.value = "";
  try {
    const response = await fetch(
      `/api/facefusion/source-images/${encodeURIComponent(source.id)}`,
      { method: "DELETE" },
    );
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    facefusionSources.value = facefusionSources.value.filter(
      (item) => item.id !== source.id,
    );
    selectedFacefusionSourceIds.value = selectedFacefusionSourceIds.value.filter(
      (id) => id !== source.id,
    );
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "删除源脸图片失败";
  } finally {
    facefusionLoading.value = false;
  }
}

async function submitFacefusion() {
  const item = selectedMediaItem.value;
  const sourcePaths = facefusionSources.value
    .filter((source) => selectedFacefusionSourceIds.value.includes(source.id))
    .map((source) => source.path);
  if (!item?.path) {
    error.value = "当前媒体项目没有可处理的本地文件路径";
    return;
  }
  if (!sourcePaths.length) {
    error.value = "请至少选择一张源脸图片";
    return;
  }
  facefusionSubmitting.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/facefusion/jobs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        emby_item_id: item.id,
        emby_item_name: item.name,
        input_path: item.path,
        settings: {
          source_paths: sourcePaths,
          processors: facefusionProcessors.value,
          execution_provider: facefusionProvider.value,
        },
      }),
    });
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    facefusionOpen.value = false;
    await refresh();
    page.value = "tasks";
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "FaceFusion 任务提交失败";
  } finally {
    facefusionSubmitting.value = false;
  }
}

async function submitWhisper() {
  const item = selectedMediaItem.value;
  if (!item?.path) {
    error.value = "当前媒体项目没有可处理的本地文件路径";
    return;
  }
  whisperSubmitting.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/whisper/tasks", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ video_path: item.path }),
    });
    if (!response.ok) {
      const detail = await response.text();
      throw new Error(detail || `${response.status} ${response.statusText}`);
    }
    selectedMediaItem.value = null;
    await refresh();
    page.value = "tasks";
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Whisper 任务提交失败";
  } finally {
    whisperSubmitting.value = false;
  }
}

async function submitLada() {
  const item = selectedMediaItem.value;
  if (!item?.path) {
    error.value = "当前媒体项目没有可处理的本地文件路径";
    return;
  }
  ladaSubmitting.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        emby_item_id: item.id,
        emby_item_name: item.name,
        input_path: item.path,
        settings: ladaDefaults.value,
      }),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    selectedMediaItem.value = null;
    await refresh();
    await openTasks();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "LADA 任务提交失败";
  } finally {
    ladaSubmitting.value = false;
  }
}

function subtitleSize(size: number) {
  return size >= 1024 * 1024
    ? `${(size / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(size / 1024))} KB`;
}

async function openSubtitles() {
  const item = selectedMediaItem.value;
  if (!item?.path) {
    error.value = "当前媒体项目没有可读取的本地文件路径";
    return;
  }
  subtitlesOpen.value = true;
  subtitlesLoading.value = true;
  onlineSubtitles.value = [];
  error.value = "";
  try {
    const params = new URLSearchParams({ video_path: item.path });
    const result = await request<{ subtitles?: SubtitleFile[] }>(
      `/api/subtitles?${params.toString()}`,
    );
    localSubtitles.value = result.subtitles || [];
  } catch (cause) {
    localSubtitles.value = [];
    error.value = cause instanceof Error ? cause.message : "本地字幕读取失败";
  } finally {
    subtitlesLoading.value = false;
  }
}

async function searchOnlineSubtitles() {
  const item = selectedMediaItem.value;
  if (!item?.path) return;
  subtitleSearchLoading.value = true;
  error.value = "";
  try {
    const params = new URLSearchParams({
      video_path: item.path,
      local_only: "false",
    });
    const result = await request<{ results?: OnlineSubtitle[] }>(
      `/api/subtitles/search?${params.toString()}`,
    );
    onlineSubtitles.value = result.results || [];
  } catch (cause) {
    onlineSubtitles.value = [];
    error.value = cause instanceof Error ? cause.message : "在线字幕搜索失败";
  } finally {
    subtitleSearchLoading.value = false;
  }
}

async function downloadOnlineSubtitle(subtitle: OnlineSubtitle) {
  const item = selectedMediaItem.value;
  if (!item?.path || !subtitle.url) return;
  subtitleDownloading.value = subtitle.url;
  error.value = "";
  try {
    const params = new URLSearchParams({
      url: subtitle.url,
      video_path: item.path,
      source: subtitle.source || "",
      source_key: subtitle.source_key || "",
      source_type: subtitle.source_type || "",
    });
    const response = await fetch(
      `/api/subtitles/download?${params.toString()}`,
    );
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    await openSubtitles();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "字幕下载失败";
  } finally {
    subtitleDownloading.value = "";
  }
}

async function loadFacefusionSettings() {
  facefusionSettingsLoading.value = true;
  try {
    const result = await request<{ settings: Record<string, string | number> }>(
      "/api/facefusion/settings",
    );
    facefusionSettings.value = result.settings || {};
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "FaceFusion 设置读取失败";
  } finally {
    facefusionSettingsLoading.value = false;
  }
}

async function saveFacefusionSettings() {
  facefusionSettingsSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/facefusion/settings", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ settings: facefusionSettings.value }),
    });
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    const result = (await response.json()) as {
      settings?: Record<string, string | number>;
    };
    facefusionSettings.value = result.settings || facefusionSettings.value;
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "FaceFusion 设置保存失败";
  } finally {
    facefusionSettingsSaving.value = false;
  }
}

async function loadWhisperSettings() {
  whisperSettingsLoading.value = true;
  try {
    const result = await request<{ whisper?: Record<string, unknown> }>(
      "/api/settings",
    );
    whisperSettings.value = { ...(result.whisper || {}) };
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Whisper 设置读取失败";
  } finally {
    whisperSettingsLoading.value = false;
  }
}

async function saveWhisperSettings() {
  whisperSettingsSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/settings/whisper", {
      method: "PUT",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(whisperSettings.value),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    const refreshed = await request<{ whisper?: Record<string, unknown> }>(
      "/api/settings",
    );
    whisperSettings.value = { ...(refreshed.whisper || whisperSettings.value) };
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Whisper 设置保存失败";
  } finally {
    whisperSettingsSaving.value = false;
  }
}

async function loadLadaSettings() {
  ladaInfoLoading.value = true;
  try {
    const [settingsData, info] = await Promise.all([
      request<{
        lada?: { cli_path?: string };
        lada_defaults?: Record<string, string | number | boolean>;
      }>("/api/settings"),
      request<LadaInfo>("/api/settings/lada/info"),
    ]);
    ladaConfig.value = { cli_path: settingsData.lada?.cli_path || "" };
    ladaDefaults.value = { ...(settingsData.lada_defaults || {}) };
    ladaInfo.value = info || {};
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "LADA 设置读取失败";
  } finally {
    ladaInfoLoading.value = false;
  }
}

async function saveLadaSettings() {
  ladaSettingsSaving.value = true;
  error.value = "";
  try {
    const [cliResponse, defaultsResponse] = await Promise.all([
      fetch("/api/settings/lada", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          cli_path: ladaConfig.value.cli_path,
          is_docker: false,
        }),
      }),
      fetch("/api/settings/lada/defaults", {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(ladaDefaults.value),
      }),
    ]);
    if (!cliResponse.ok)
      throw new Error(
        (await cliResponse.text()) ||
          `${cliResponse.status} ${cliResponse.statusText}`,
      );
    if (!defaultsResponse.ok)
      throw new Error(
        (await defaultsResponse.text()) ||
          `${defaultsResponse.status} ${defaultsResponse.statusText}`,
      );
    await loadLadaSettings();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "LADA 设置保存失败";
  } finally {
    ladaSettingsSaving.value = false;
  }
}

async function openMediaLibrary() {
  page.value = "library";
  await loadMediaLibrary();
}

async function changeMediaPage(direction: number) {
  const next = Math.max(
    0,
    Math.min(
      mediaOffset.value + direction * mediaPageSize,
      Math.max(0, (mediaPageCount.value - 1) * mediaPageSize),
    ),
  );
  if (next === mediaOffset.value) return;
  mediaOffset.value = next;
  await loadMediaLibrary();
}

async function loadActors() {
  actorLoading.value = true;
  error.value = "";
  try {
    const result = await pluginAction<{ items: Actor[] }>("javdb", "actors", {
      type: 0,
    });
    actors.value = result.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "演员列表加载失败";
  } finally {
    actorLoading.value = false;
  }
}

async function loadSubscriptions() {
  subscriptionLoading.value = true;
  error.value = "";
  try {
    const result = await pluginAction<{ items: Subscription[] }>(
      "subscription-core",
      "overview",
    );
    subscriptions.value = result.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "订阅中心加载失败";
  } finally {
    subscriptionLoading.value = false;
  }
}

async function openSubscriptions() {
  page.value = "subscriptions";
  await loadSubscriptions();
}

async function createSubscription() {
  const code = subscriptionCode.value.trim();
  if (!code) return;
  subscriptionCreating.value = true;
  error.value = "";
  try {
    await pluginAction("subscription-core", "create", { code });
    subscriptionCode.value = "";
    await loadSubscriptions();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "创建订阅失败";
  } finally {
    subscriptionCreating.value = false;
  }
}

async function actOnSubscription(
  action: "check_once" | "retry_submit" | "delete" | "reset_submit",
  subscription: Subscription,
) {
  error.value = "";
  try {
    await pluginAction("subscription-core", action, {
      id: subscription.id,
      force: true,
    });
    await loadSubscriptions();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "订阅操作失败";
  }
}

function formatResourceSize(size: number | undefined) {
  const bytes = Number(size || 0);
  if (!bytes) return "";
  return bytes >= 1024 ** 3
    ? `${(bytes / 1024 ** 3).toFixed(2)} GB`
    : `${(bytes / 1024 ** 2).toFixed(0)} MB`;
}

async function runGlobalSearch() {
  const query = globalSearchQuery.value.trim();
  if (!query) return;
  globalSearchLoading.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, limit: 24 }),
    });
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    const result = (await response.json()) as {
      groups?: typeof globalSearchGroups.value;
    };
    globalSearchGroups.value = result.groups || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "全局搜索失败";
  } finally {
    globalSearchLoading.value = false;
  }
}

function compatibleDownloaderFor(resource: Resource): string {
  const candidates: string[] = [];
  for (const pluginId of [
    resource.preferred_downloader,
    ...(resource.compatible_downloaders || []),
  ]) {
    if (pluginId && !candidates.includes(pluginId)) candidates.push(pluginId);
  }
  return (
    candidates.find((pluginId) =>
      plugins.value.some((plugin) => plugin.id === pluginId && plugin.enabled),
    ) || ""
  );
}

async function submitGlobalResource(resource: Resource) {
  const downloaderId = compatibleDownloaderFor(resource);
  if (!downloaderId) {
    error.value = "没有已启用的兼容下载器，请先在插件中完成配置并启用。";
    return;
  }
  if (!resource.url) {
    error.value = "该资源没有可提交的下载链接";
    return;
  }
  globalResourceSubmitting.value = resource.id;
  error.value = "";
  try {
    const code = resource.metadata?.video_code || "";
    const response = await fetch(
      `/api/plugins/${encodeURIComponent(downloaderId)}/downloads`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          payload: {
            url: resource.url,
            title: code || resource.title || "NOOR 下载",
            name: code || resource.title || "NOOR 下载",
            rename: code,
          },
        }),
      },
    );
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    globalSearchOpen.value = false;
    await refresh();
    await openTasks();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "下载任务提交失败";
  } finally {
    globalResourceSubmitting.value = "";
  }
}

async function openActor(actor: Actor) {
  selectedActor.value = actor;
  actorMovies.value = [];
  try {
    const result = await pluginAction<{ items: JavdbItem[] }>(
      "javdb",
      "actor_movies",
      { actor_id: actor.id, page: 1, limit: 24 },
    );
    actorMovies.value = result.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "演员作品加载失败";
  }
}

async function loadHardlinks() {
  hardlinksLoading.value = true;
  error.value = "";
  try {
    const data = await request<{ groups: HardlinkGroup[] }>(
      "/api/media-library/hardlinks/groups",
    );
    hardlinkGroups.value = data.groups || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "硬链接列表加载失败";
  } finally {
    hardlinksLoading.value = false;
  }
}

async function scanHardlinks() {
  hardlinksScanning.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/media-library/hardlinks/scan", {
      method: "POST",
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    const data = (await response.json()) as { groups?: HardlinkGroup[] };
    hardlinkGroups.value = data.groups || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "硬链接扫描失败";
  } finally {
    hardlinksScanning.value = false;
  }
}

async function loadHardlinkConfig() {
  hardlinkConfigLoading.value = true;
  try {
    const data = await request<{ config?: { scan_groups?: HardlinkScanGroup[] } }>(
      "/api/media-library/config",
    );
    hardlinkScanGroups.value = (data.config?.scan_groups || []).map((group) => ({
      source_dir: String(group.source_dir || ""),
      hardlink_dir: String(group.hardlink_dir || ""),
    }));
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "硬链接配置读取失败";
  } finally {
    hardlinkConfigLoading.value = false;
  }
}

function addHardlinkScanGroup() {
  hardlinkScanGroups.value = [
    ...hardlinkScanGroups.value,
    { source_dir: "", hardlink_dir: "" },
  ];
}

function removeHardlinkScanGroup(index: number) {
  hardlinkScanGroups.value = hardlinkScanGroups.value.filter(
    (_group, groupIndex) => groupIndex !== index,
  );
}

async function saveHardlinkConfig() {
  const groups = hardlinkScanGroups.value
    .map((group) => ({
      source_dir: group.source_dir.trim(),
      hardlink_dir: group.hardlink_dir.trim(),
    }))
    .filter((group) => group.source_dir && group.hardlink_dir);
  if (groups.length !== hardlinkScanGroups.value.length) {
    error.value = "每组硬链接扫描路径都需要填写源目录和媒体库目录";
    return;
  }
  hardlinkConfigSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/media-library/config", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ scan_groups: groups }),
    });
    if (!response.ok)
      throw new Error(
        (await response.text()) || `${response.status} ${response.statusText}`,
      );
    await loadHardlinkConfig();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "硬链接配置保存失败";
  } finally {
    hardlinkConfigSaving.value = false;
  }
}

async function hardlinkDeleteRequest(
  group: HardlinkGroup,
  dryRun: boolean,
): Promise<HardlinkDeletePreview> {
  const response = await fetch("/api/media-library/hardlinks/delete-group", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      code: group.code,
      entries: group.entries || [],
      dry_run: dryRun,
    }),
  });
  if (!response.ok)
    throw new Error(
      (await response.text()) || `${response.status} ${response.statusText}`,
    );
  return (await response.json()) as HardlinkDeletePreview;
}

function previewPaths(preview: HardlinkDeletePreview | null, keys: string[]) {
  if (!preview) return [];
  return keys.flatMap((key) => {
    const value = preview[key];
    return Array.isArray(value)
      ? value.filter((path): path is string => typeof path === "string")
      : [];
  });
}

async function openHardlinkDelete(group: HardlinkGroup) {
  hardlinkDeleteGroup.value = group;
  hardlinkDeletePreview.value = null;
  hardlinkDeleteLoading.value = true;
  error.value = "";
  try {
    hardlinkDeletePreview.value = await hardlinkDeleteRequest(group, true);
  } catch (cause) {
    hardlinkDeleteGroup.value = null;
    error.value = cause instanceof Error ? cause.message : "删除预演失败";
  } finally {
    hardlinkDeleteLoading.value = false;
  }
}

function closeHardlinkDelete() {
  hardlinkDeleteGroup.value = null;
  hardlinkDeletePreview.value = null;
  mediaDeleteGroup.value = null;
}

async function confirmHardlinkDelete() {
  const group = hardlinkDeleteGroup.value;
  if (!group) return;
  hardlinkDeleting.value = true;
  error.value = "";
  try {
    await hardlinkDeleteRequest(group, false);
    closeHardlinkDelete();
    await loadHardlinks();
    if (page.value === "library") {
      selectedMediaItem.value = null;
      await loadMediaLibrary();
    }
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "删除硬链接组失败";
  } finally {
    hardlinkDeleting.value = false;
  }
}

async function loadEmbyActors() {
  embyActorsLoading.value = true;
  error.value = "";
  try {
    const query = embyActorQuery.value.trim();
    const sortBy = embyActorSort.value === "recent" ? "DateCreated" : "SortName";
    const sortOrder = embyActorSort.value === "recent" ? "Descending" : "Ascending";
    const [actorsData, status] = await Promise.all([
      request<{ actors: EmbyActor[]; total: number }>(
        `/api/media-library/actors?limit=60&sort_by=${sortBy}&sort_order=${sortOrder}&lang=${actorDisplayLanguage.value}${query ? `&q=${encodeURIComponent(query)}` : ""}`,
      ),
      request<{
        exists?: boolean;
        record_count?: number;
        configured_path?: string;
        configured_root?: string;
      }>("/api/media-library/actors/mapping/status"),
    ]);
    embyActors.value = actorsData.actors || [];
    embyActorsTotal.value = actorsData.total || 0;
    mappingStatus.value = status;
    mdcNgPath.value = status.configured_root || "";
  } catch (cause) {
    embyActors.value = [];
    embyActorsTotal.value = 0;
    mappingStatus.value = null;
    error.value =
      cause instanceof Error ? cause.message : "Emby 演员列表加载失败";
  } finally {
    embyActorsLoading.value = false;
  }
}

async function loadMappingStatus() {
  try {
    const status = await request<{
      exists?: boolean;
      record_count?: number;
      configured_path?: string;
      configured_root?: string;
    }>("/api/media-library/actors/mapping/status");
    mappingStatus.value = status;
    mdcNgPath.value = status.configured_root || "";
  } catch {
    mappingStatus.value = null;
  }
}

async function saveMdcNgPath() {
  mappingSaving.value = true;
  error.value = "";
  try {
    const response = await fetch("/api/media-library/actors/mapping/source", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ mdc_ng_path: mdcNgPath.value }),
    });
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    await loadMappingStatus();
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "映射表路径保存失败";
  } finally {
    mappingSaving.value = false;
  }
}

async function openEmbyActor(actor: EmbyActor, pushRoute = true) {
  selectedEmbyActor.value = actor;
  selectedEmbyActorMovies.value = [];
  gfriendsCandidates.value = [];
  if (pushRoute) {
    const path = `/actor/emby/${encodeURIComponent(actor.id)}`;
    if (window.location.pathname !== path)
      window.history.pushState({ actorId: actor.id }, "", path);
  }
  try {
    const [detail, movies] = await Promise.all([
      request<{ actor?: EmbyActor }>(
        `/api/media-library/actor/${encodeURIComponent(actor.id)}?lang=${actorDisplayLanguage.value}`,
      ),
      request<{ items: JavdbItem[] }>(
        `/api/media-library/actor/${encodeURIComponent(actor.id)}/movies?limit=48`,
      ),
    ]);
    selectedEmbyActor.value = detail.actor || actor;
    selectedEmbyActorMovies.value = movies.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "演员作品加载失败";
  }
}

function closeEmbyActor() {
  selectedEmbyActor.value = null;
  selectedEmbyActorMovies.value = [];
  if (embyActorIdFromPath()) window.history.replaceState({ page: "files" }, "", "/files");
}

async function loadActorDuplicates() {
  duplicatesLoading.value = true;
  error.value = "";
  try {
    const data = await request<{
      groups: Array<{ key: string; actors: EmbyActor[] }>;
    }>("/api/media-library/actors/duplicates?limit=3000");
    duplicateGroups.value = data.groups || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "演员重名检测失败";
  } finally {
    duplicatesLoading.value = false;
  }
}

async function loadGfriendsCandidates() {
  const actor = selectedEmbyActor.value;
  if (!actor) return;
  gfriendsLoading.value = true;
  error.value = "";
  try {
    const aliases = [
      actor.name_jp,
      actor.name_zh_cn,
      actor.name_zh_tw,
      actor.sort_name,
      actor.aliases,
    ].filter((value): value is string => Boolean(value));
    const result = await pluginAction<{
      items: Array<{
        url: string;
        remote_url: string;
        name: string;
        aliases?: string[];
      }>;
    }>("gfriends", "candidates", { name: actor.name, aliases, limit: 24 });
    gfriendsCandidates.value = result.items || [];
  } catch (cause) {
    error.value =
      cause instanceof Error ? cause.message : "Gfriends 候选加载失败";
  } finally {
    gfriendsLoading.value = false;
  }
}

async function applyGfriendsAvatar(candidate: { remote_url: string }) {
  const actor = selectedEmbyActor.value;
  if (!actor || !candidate.remote_url) return;
  avatarSaving.value = true;
  error.value = "";
  try {
    const response = await fetch(
      `/api/media-library/actor/${encodeURIComponent(actor.id)}/avatar-url`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ url: candidate.remote_url }),
      },
    );
    if (!response.ok)
      throw new Error(`${response.status} ${response.statusText}`);
    actor.avatar_url = candidate.remote_url;
    const index = embyActors.value.findIndex((item) => item.id === actor.id);
    if (index >= 0) embyActors.value[index] = { ...actor };
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "写入 Emby 头像失败";
  } finally {
    avatarSaving.value = false;
  }
}

async function openFiles(
  tab: "hardlinks" | "actor-management" = fileTab.value,
) {
  page.value = "files";
  fileTab.value = tab;
  if (tab === "hardlinks") await loadHardlinks();
  else await loadEmbyActors();
}

async function refresh() {
  loading.value = true;
  error.value = "";
  try {
    const [health, jobData, pluginData, settingsData, recommendationData] =
      await Promise.all([
        request<{ status: string }>("/api/health"),
        request<{ jobs: Job[] }>("/api/jobs"),
        request<{ items: Plugin[] }>("/api/plugins"),
        request<Record<string, unknown>>("/api/settings"),
        pluginAction<{ items: Recommendation[] }>(
          "av-recommend",
          "recommendations",
          { limit: 48, source_mode: recommendationMode.value },
        ),
      ]);
    healthy.value = health.status === "ok";
    jobs.value = jobData.jobs || [];
    plugins.value = pluginData.items || [];
    applyCoreSettings(settingsData);
    recommendations.value = recommendationData.items || [];
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : "无法连接 NOOR 后端";
    healthy.value = false;
  } finally {
    loading.value = false;
  }
}

async function loadPageData(target: Page) {
  if (target === "library") await loadMediaLibrary();
  else if (target === "javdb") await loadJavdb();
  else if (target === "actors") await loadActors();
  else if (target === "subscriptions") await openSubscriptions();
  else if (target === "files") await openFiles();
  else if (target === "tasks") await openTasks();
  else if (target === "settings") {
    await Promise.all([
      loadCoreSettings(),
      loadSystemLogs(),
      loadMappingStatus(),
      loadHardlinkConfig(),
      loadFacefusionSettings(),
      loadWhisperSettings(),
      loadLadaSettings(),
    ]);
  }
}

async function loadBrowserRoute() {
  const mediaItemId = mediaItemIdFromPath();
  if (mediaItemId) {
    page.value = "library";
    await loadMediaLibrary();
    await openMediaItem({ id: mediaItemId, name: "" }, false);
    return;
  }
  const javdbCode = javdbCodeFromPath();
  if (javdbCode) {
    page.value = "javdb";
    javdbDetail.value = null;
    await loadJavdb();
    await openJavdbDetail({ code: javdbCode, title: javdbCode }, false);
    return;
  }
  const actorId = embyActorIdFromPath();
  if (actorId) {
    page.value = "files";
    fileTab.value = "actor-management";
    await loadEmbyActors();
    await openEmbyActor({ id: actorId, name: "" }, false);
    return;
  }
  selectedEmbyActor.value = null;
  selectedEmbyActorMovies.value = [];
  await loadPageData(page.value);
}

watch(page, (target) => {
  if (applyingBrowserRoute) return;
  const path = pagePaths[target];
  if (window.location.pathname !== path) window.history.pushState({ page: target }, "", path);
});

onMounted(async () => {
  applyingBrowserRoute = true;
  page.value = pageFromPath();
  applyingBrowserRoute = false;
  await refresh();
  await loadBrowserRoute();
  window.addEventListener("popstate", async () => {
    applyingBrowserRoute = true;
    page.value = pageFromPath();
    applyingBrowserRoute = false;
    await loadBrowserRoute();
  });
  window.addEventListener("keydown", handleCoverBlurShortcut);
  await loadUiSettings();
});
</script>

<template>
  <div :class="['app-shell', { 'cover-blurred': coverBlurActive }]">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">N</span><span>NOOR</span>
      </div>
      <nav aria-label="主导航">
        <button
          :class="{ active: page === 'overview' }"
          @click="page = 'overview'"
        >
          概览
        </button>
        <button
          :class="{ active: page === 'library' }"
          @click="openMediaLibrary"
        >
          媒体库
        </button>
        <button
          :class="{ active: page === 'recommendations' }"
          @click="page = 'recommendations'"
        >
          推荐
        </button>
        <button
          :class="{ active: page === 'javdb' }"
          @click="
            page = 'javdb';
            loadJavdb();
          "
        >
          JavDB
        </button>
        <button
          :class="{ active: page === 'actors' }"
          @click="
            page = 'actors';
            loadActors();
          "
        >
          演员
        </button>
        <button
          :class="{ active: page === 'subscriptions' }"
          @click="openSubscriptions"
        >
          订阅
        </button>
        <button :class="{ active: page === 'files' }" @click="openFiles()">
          文件
        </button>
        <button :class="{ active: page === 'tasks' }" @click="openTasks()">
          任务
          <span v-if="runningJobs.length" class="count">{{
            runningJobs.length
          }}</span>
        </button>
        <button
          :class="{ active: page === 'plugins' }"
          @click="page = 'plugins'"
        >
          插件
        </button>
        <button
          :class="{ active: page === 'settings' }"
          @click="
            page = 'settings';
            loadCoreSettings();
            loadSystemLogs();
            loadMappingStatus();
            loadHardlinkConfig();
            loadFacefusionSettings();
            loadWhisperSettings();
            loadLadaSettings();
            loadUiSettings();
          "
        >
          设置
        </button>
      </nav>
      <div class="sidebar-foot">
        <span :class="['status-dot', { online: healthy }]" />{{
          healthy ? "后端已连接" : "后端未连接"
        }}
      </div>
    </aside>
    <main>
      <header>
        <div>
          <p class="eyebrow">NOOR RECOVERY</p>
          <h1>{{ title }}</h1>
        </div>
        <div class="header-actions">
          <button
            class="header-command"
            title="全局搜索"
            @click="globalSearchOpen = !globalSearchOpen"
          >
            搜索</button
          ><button
            :class="['icon-button', { active: coverBlurActive }]"
            title="封面模糊 (H)"
            aria-label="封面模糊 (H)"
            @click="toggleCoverBlurBrowser"
          >
            ◐
          </button><button
            class="icon-button"
            title="刷新"
            aria-label="刷新"
            @click="refresh"
          >
            ↻
          </button>
        </div>
      </header>
      <section v-if="globalSearchOpen" class="global-search-panel">
        <form class="javdb-search" @submit.prevent="runGlobalSearch">
          <input
            v-model="globalSearchQuery"
            aria-label="全局搜索"
            placeholder="番号或作品标题"
            autofocus
          /><button type="submit">搜索</button
          ><button
            type="button"
            title="关闭搜索"
            aria-label="关闭搜索"
            @click="globalSearchOpen = false"
          >
            x
          </button>
        </form>
        <p v-if="globalSearchLoading" class="empty">正在搜索资源...</p>
        <div v-else class="global-search-results">
          <section v-for="group in globalSearchGroups" :key="group.provider">
            <h2>{{ group.provider_name || group.provider }}</h2>
            <div class="resource-list">
              <article
                v-for="resource in group.items"
                :key="resource.id"
                class="resource-row"
              >
                <img
                  v-if="resource.cover_url"
                  :src="resource.cover_url"
                  :alt="resource.title"
                  loading="lazy"
                />
                <div>
                  <b>{{ resource.metadata?.video_code || resource.title }}</b
                  ><small
                    >{{ resource.subtitle
                    }}<template v-if="formatResourceSize(resource.size_bytes)">
                      · {{ formatResourceSize(resource.size_bytes) }}</template
                    ></small
                  >
                </div>
                <div class="resource-actions">
                  <button
                    v-if="resource.metadata?.video_code"
                    title="查看 JavDB 详情"
                    aria-label="查看 JavDB 详情"
                    @click="
                      javdbQuery = resource.metadata.video_code || '';
                      globalSearchOpen = false;
                      page = 'javdb';
                      loadJavdb();
                    "
                  >
                    查看</button
                  ><button
                    v-if="compatibleDownloaderFor(resource)"
                    :disabled="globalResourceSubmitting === resource.id"
                    title="推送下载"
                    aria-label="推送下载"
                    @click="submitGlobalResource(resource)"
                  >
                    {{
                      globalResourceSubmitting === resource.id
                        ? "提交中"
                        : "推送"
                    }}
                  </button>
                </div>
              </article>
              <p v-if="!group.items.length" class="empty">暂无资源</p>
            </div>
          </section>
          <p
            v-if="
              globalSearchQuery &&
              !globalSearchGroups.some((group) => group.items.length)
            "
            class="empty"
          >
            未找到可用资源
          </p>
        </div>
      </section>
      <section v-if="error" class="notice error">{{ error }}</section>
      <section v-else-if="loading" class="notice">
        正在读取 NOOR 状态...
      </section>
      <template v-else>
        <section v-if="page === 'overview'" class="overview-grid">
          <article class="stat">
            <span>活动任务</span><strong>{{ runningJobs.length }}</strong>
          </article>
          <article class="stat">
            <span>全部任务</span><strong>{{ jobs.length }}</strong>
          </article>
          <article class="stat">
            <span>已加载插件</span
            ><strong>{{ plugins.filter((item) => item.loaded).length }}</strong>
          </article>
          <article class="stat">
            <span>媒体服务器</span
            ><strong>{{ settings.emby ? "已配置" : "未配置" }}</strong>
          </article>
          <section class="panel wide">
            <div class="panel-heading">
              <h2>最近任务</h2>
              <button @click="openTasks()">查看全部</button>
            </div>
            <p v-if="!jobs.length" class="empty">暂无任务</p>
            <div v-for="job in jobs.slice(0, 6)" :key="job.id" class="job-row">
              <div>
                <b>{{ job.emby_item_name || job.job_type }}</b
                ><small
                  >{{ job.job_type }} ·
                  {{ job.phase_label || job.detail || job.status }}</small
                >
              </div>
              <span>{{ job.progress }}%</span>
            </div>
          </section>
        </section>
        <section v-else-if="page === 'tasks'" class="panel">
          <div class="panel-heading">
            <div>
              <h2>任务</h2>
              <small>执行队列与后台维护</small>
            </div>
            <button
              @click="
                taskTab === 'background' ? loadBackgroundTasks() : refresh()
              "
            >
              刷新
            </button>
          </div>
          <div class="file-tabs task-tabs" role="tablist" aria-label="任务类型">
            <button
              :class="{ active: taskTab === 'queue' }"
              @click="taskTab = 'queue'"
            >
              任务队列</button
            ><button
              :class="{ active: taskTab === 'background' }"
              @click="
                taskTab = 'background';
                loadBackgroundTasks();
              "
            >
              后台
            </button>
          </div>
          <template v-if="taskTab === 'queue'"
            ><p v-if="!jobs.length" class="empty">暂无任务</p>
            <div
              v-for="job in jobs"
              :key="job.id"
              class="job-row job-row-actionable"
              @click="openJob(job)"
            >
              <div>
                <b>{{ job.emby_item_name || job.job_type }}</b
                ><small
                  >{{ job.job_type }} ·
                  {{ job.phase_label || job.detail || job.status
                  }}<template v-if="job.phase_progress != null">
                    {{ job.phase_progress }}%</template
                  ></small
                >
                <div class="progress">
                  <i :style="{ width: `${job.progress}%` }" />
                </div>
              </div>
              <div class="job-actions">
                <span :class="['badge', job.status]">{{ job.status }}</span
                ><button
                  v-if="['queued', 'running', 'blocked'].includes(job.status)"
                  :disabled="jobCancelling === job.id"
                  title="取消任务"
                  aria-label="取消任务"
                  @click.stop="cancelJob(job)"
                >
                  {{ jobCancelling === job.id ? "取消中" : "取消" }}
                </button>
              </div>
            </div>
            <section v-if="selectedJob" class="detail-panel job-detail">
              <div class="panel-heading">
                <div>
                  <h2>
                    {{ selectedJob.emby_item_name || selectedJob.job_type }}
                  </h2>
                  <small
                    >{{ selectedJob.job_type }} · {{ selectedJob.status }} ·
                    {{ selectedJob.progress }}%</small
                  >
                </div>
                <div class="detail-actions">
                  <a
                    v-if="selectedJob.status === 'completed'"
                    :href="`/api/jobs/${encodeURIComponent(selectedJob.id)}/download`"
                    target="_blank"
                    rel="noopener"
                    >下载结果</a
                  ><button
                    title="关闭任务详情"
                    aria-label="关闭任务详情"
                    @click="selectedJob = null"
                  >
                    x
                  </button>
                </div>
              </div>
              <p v-if="selectedJob.detail" class="muted">
                {{ selectedJob.detail }}
              </p>
              <p v-if="selectedJob.error_message" class="job-error">
                {{ selectedJob.error_message }}
              </p>
              <p v-if="jobLogsLoading" class="empty">正在读取任务日志...</p>
              <pre v-else-if="selectedJobLogs.length" class="job-log">{{
                selectedJobLogs.join("\n")
              }}</pre>
              <p v-else class="empty">该任务尚未产生日志</p>
            </section></template
          ><template v-else
            ><p v-if="backgroundTasksLoading" class="empty">
              正在读取后台任务...
            </p>
            <p v-else-if="!backgroundTasks.length" class="empty">
              没有已启用插件的后台任务
            </p>
            <div
              v-else
              v-for="task in backgroundTasks"
              :key="`${task.plugin_id}:${task.id}`"
              class="job-row"
            >
              <div>
                <b>{{ task.title || task.id }}</b
                ><small
                  >{{ task.plugin_name || task.plugin_id }} ·
                  {{
                    task.summary || task.detail || task.status || "未知状态"
                  }}</small
                ><small v-if="task.last_finished_at"
                  >上次完成：{{
                    new Date(task.last_finished_at).toLocaleString()
                  }}</small
                >
              </div>
              <span
                :class="[
                  'badge',
                  task.status === 'completed'
                    ? 'completed'
                    : task.status === 'failed'
                      ? 'failed'
                      : 'queued',
                ]"
                >{{ task.status || "idle" }}</span
              >
            </div></template
          >
        </section>
        <section v-else-if="page === 'library'" class="media-library">
          <div class="panel-heading media-library__controls">
            <div class="library-picker">
              <button
                :class="{ active: !mediaLibraryId }"
                @click="
                  mediaLibraryId = '';
                  loadMediaLibrary(true);
                "
              >
                全部</button
              ><button
                v-for="library in mediaLibraries"
                :key="library.id"
                :class="{ active: mediaLibraryId === library.id }"
                @click="
                  mediaLibraryId = library.id;
                  loadMediaLibrary(true);
                "
              >
                {{ library.name }}
              </button>
            </div>
            <button @click="loadMediaLibrary()">刷新</button>
          </div>
          <p v-if="mediaLoading" class="empty">正在读取媒体库...</p>
          <template v-else
            ><p v-if="!mediaItems.length" class="empty">当前媒体库没有影片</p>
            <div class="media-grid">
              <article
                v-for="item in mediaItems"
                :key="item.id"
                :class="[
                  'media-card',
                  { 'delete-menu-open': mediaDeleteGroup?.code === mediaCode(item) },
                ]"
                @click="openMediaItem(item)"
                @contextmenu.prevent="openMediaDeleteMenu(item)"
              >
                <div class="media-poster">
                  <img
                    v-if="item.poster_path"
                    :src="item.poster_path"
                    :alt="item.name"
                    loading="lazy"
                  /><span v-if="isFacefusionItem(item)" class="facefusion-badge">换脸</span
                  ><button
                    v-if="mediaDeleteGroup?.code === mediaCode(item)"
                    class="media-delete-button"
                    :disabled="mediaDeleteLoading === item.id"
                    @click.stop="openHardlinkDelete(mediaDeleteGroup)"
                  >
                    删除作品
                  </button>
                </div>
                <div>
                  <b>{{ item.name }}</b
                  ><small>{{
                    item.date_created
                      ? new Date(item.date_created).toLocaleDateString()
                      : "日期未知"
                  }}</small>
                </div>
              </article>
            </div>
            <div v-if="mediaTotal > mediaPageSize" class="media-pagination">
              <button :disabled="mediaPage <= 1" @click="changeMediaPage(-1)">
                上一页</button
              ><span
                >{{ mediaPage }} / {{ mediaPageCount }} ·
                {{ mediaTotal }} 部</span
              ><button
                :disabled="mediaPage >= mediaPageCount"
                @click="changeMediaPage(1)"
              >
                下一页
              </button>
            </div></template
          >
          <section v-if="selectedMediaItem" class="detail-panel">
            <div class="panel-heading">
              <div>
                <h2>{{ selectedMediaItem.name }}</h2>
                <small>{{ selectedMediaItem.type || "媒体项目" }}</small>
              </div>
              <div class="detail-actions">
                <button
                  v-if="selectedMediaItem.path"
                  :disabled="ladaSubmitting"
                  title="LADA 去码"
                  aria-label="LADA 去码"
                  @click="submitLada"
                >
                  {{ ladaSubmitting ? "提交中" : "去码" }}</button
                ><button
                  v-if="selectedMediaItem.path"
                  title="字幕库"
                  aria-label="字幕库"
                  @click="openSubtitles"
                >
                  字幕库</button
                ><button
                  v-if="selectedMediaItem.path"
                  :disabled="whisperSubmitting"
                  title="生成字幕"
                  aria-label="生成字幕"
                  @click="submitWhisper"
                >
                  {{ whisperSubmitting ? "提交中" : "生成字幕" }}</button
                ><button
                  v-if="selectedMediaItem.path"
                  title="换脸"
                  aria-label="换脸"
                  @click="openFacefusion"
                >
                  换脸</button
                ><button
                  title="关闭详情"
                  aria-label="关闭详情"
                  @click="closeMediaItem"
                >
                  x
                </button>
              </div>
            </div>
            <img
              v-if="selectedMediaItem.poster_path"
              class="detail-cover"
              :src="selectedMediaItem.poster_path"
              :alt="selectedMediaItem.name"
            />
            <p v-if="selectedMediaItem.path" class="media-path">
              {{ selectedMediaItem.path }}
            </p>
            <section v-if="subtitlesOpen" class="subtitle-panel">
              <div class="panel-heading">
                <div>
                  <h3>字幕库</h3>
                  <small>本地字幕与在线搜索</small>
                </div>
                <div class="detail-actions">
                  <button
                    :disabled="subtitleSearchLoading"
                    @click="searchOnlineSubtitles"
                  >
                    {{
                      subtitleSearchLoading ? "搜索中" : "搜索在线字幕"
                    }}</button
                  ><button
                    title="关闭字幕库"
                    aria-label="关闭字幕库"
                    @click="subtitlesOpen = false"
                  >
                    x
                  </button>
                </div>
              </div>
              <p v-if="subtitlesLoading" class="empty">正在读取本地字幕...</p>
              <template v-else
                ><div class="subtitle-list">
                  <div
                    v-for="subtitle in localSubtitles"
                    :key="subtitle.path"
                    class="subtitle-row"
                  >
                    <div>
                      <b>{{ subtitle.filename }}</b
                      ><small
                        >{{ subtitle.ext.toUpperCase() }} ·
                        {{ subtitleSize(subtitle.size) }}</small
                      >
                    </div>
                    <a
                      :href="`/api/subtitles/file?path=${encodeURIComponent(subtitle.path)}`"
                      target="_blank"
                      rel="noopener"
                      >打开</a
                    >
                  </div>
                  <p v-if="!localSubtitles.length" class="empty">
                    当前作品目录没有字幕文件
                  </p>
                </div>
                <div v-if="onlineSubtitles.length" class="subtitle-online">
                  <h3>在线结果</h3>
                  <div class="subtitle-list">
                    <div
                      v-for="subtitle in onlineSubtitles"
                      :key="subtitle.url"
                      class="subtitle-row"
                    >
                      <div>
                        <b>{{ subtitle.name }}</b
                        ><small
                          >{{ subtitle.source }} ·
                          {{ subtitle.language || subtitle.ext }}</small
                        >
                      </div>
                      <button
                        :disabled="subtitleDownloading === subtitle.url"
                        @click="downloadOnlineSubtitle(subtitle)"
                      >
                        {{
                          subtitleDownloading === subtitle.url
                            ? "下载中"
                            : "下载"
                        }}
                      </button>
                    </div>
                  </div>
                </div></template
              >
            </section>
            <section v-if="facefusionOpen" class="facefusion-panel">
              <div class="panel-heading">
                <div>
                  <h2>换脸</h2>
                  <small>任务将由 NOOR 队列执行</small>
                </div>
                <button
                  title="关闭换脸面板"
                  aria-label="关闭换脸面板"
                  @click="facefusionOpen = false"
                >
                  x
                </button>
              </div>
              <div class="facefusion-controls">
                <label
                  >执行后端<select v-model="facefusionProvider">
                    <option value="cuda">CUDA</option>
                    <option value="tensorrt">TensorRT</option>
                    <option value="cpu">CPU</option>
                  </select></label
                ><label
                  >处理器
                  <div class="processor-options">
                    <label
                      ><input
                        v-model="facefusionProcessors"
                        value="face_swapper"
                        type="checkbox"
                      />换脸</label
                    ><label
                      ><input
                        v-model="facefusionProcessors"
                        value="face_enhancer"
                        type="checkbox"
                      />人脸增强</label
                    >
                  </div></label
                >
              </div>
              <div class="panel-heading facefusion-source-heading">
                <div>
                  <h3>源脸图片</h3>
                  <small>可多选；上传后会保留在图片库</small>
                </div>
                <label class="upload-button"
                  >上传图片<input
                    type="file"
                    accept="image/*"
                    multiple
                    @change="uploadFacefusionSources"
                /></label>
              </div>
              <p v-if="facefusionLoading" class="empty">正在读取图片库...</p>
              <div v-else class="facefusion-source-grid">
                <article
                  v-for="source in facefusionSources"
                  :key="source.id"
                  class="facefusion-source"
                >
                  <button
                    :class="{
                      selected: selectedFacefusionSourceIds.includes(source.id),
                    }"
                    :title="source.name"
                    @click="toggleFacefusionSource(source.id)"
                  >
                    <img
                      :src="source.preview_url"
                      :alt="source.name"
                      loading="lazy"
                    /><span>{{ source.name }}</span>
                  </button>
                  <button
                    class="facefusion-source-delete"
                    title="从图库删除"
                    aria-label="从图库删除"
                    @click="deleteFacefusionSource(source)"
                  >
                    x
                  </button>
                </article>
                <p v-if="!facefusionSources.length" class="empty">
                  尚未上传源脸图片
                </p>
              </div>
              <div class="facefusion-submit">
                <button
                  :disabled="
                    facefusionSubmitting ||
                    !selectedFacefusionSourceIds.length ||
                    !facefusionProcessors.length
                  "
                  @click="submitFacefusion"
                >
                  {{ facefusionSubmitting ? "提交中" : "提交换脸任务" }}
                </button>
              </div>
            </section>
          </section>
        </section>
        <section v-else-if="page === 'recommendations'">
          <div class="panel-heading recommendation-controls">
            <div class="segmented" aria-label="推荐范围">
              <button
                :class="{ active: recommendationMode === 'latest' }"
                @click="setRecommendationMode('latest')"
              >
                最新推荐</button
              ><button
                :class="{ active: recommendationMode === 'full' }"
                @click="setRecommendationMode('full')"
              >
                完整推荐
              </button>
            </div>
            <span class="muted"
              >{{ recommendations.length }}/{{ recommendationTotal }} 部</span
            >
          </div>
          <div class="recommendation-summary">
            <span>候选池 {{ recommendationPool.total || 0 }}</span>
            <span>今日增量 {{ recommendationPool.today_increment || 0 }}</span>
            <span>当前推荐 {{ recommendationStats.candidates || 0 }}</span>
          </div>
          <div class="recommendations">
            <p v-if="!recommendations.length" class="empty">候选池暂无作品</p>
            <article
              v-for="item in recommendations"
              :key="item.code"
              class="work-card clickable"
              @click="viewJavdbDetail(item)"
            >
              <div class="poster">
                <img
                  v-if="item.cover_url"
                  :src="item.cover_url"
                  :alt="item.title"
                  loading="lazy"
                /><span v-if="item.is_today_increment">今日</span>
              </div>
              <div>
                <div class="card-title">
                  <b>{{ item.code }}</b
                  ><strong>{{
                    item.recommendation_score ?? item.score ?? 0
                  }}</strong>
                </div>
                <p>{{ item.title }}</p>
                <small
                  >{{ item.release_date || "日期未知"
                  }}<template v-if="item.actors.length">
                    · {{ item.actors.slice(0, 2).join("、") }}</template
                  ></small
                >
                <div v-if="item.source_tags?.length" class="recommendation-sources">
                  <span
                    v-for="tag in item.source_tags.slice(0, 3)"
                    :key="`${item.code}:${tag.id}:${tag.date}`"
                    >{{ tag.label || tag.id }}</span
                  >
                </div>
                <div class="card-actions">
                  <button
                    title="喜欢"
                    aria-label="喜欢"
                    @click.stop="feedback(item, 'like')"
                  >
                    +</button
                  ><button
                    title="不喜欢"
                    aria-label="不喜欢"
                    @click.stop="feedback(item, 'dislike')"
                  >
                    -</button
                  ><button
                    title="忽略"
                    aria-label="忽略"
                    @click.stop="feedback(item, 'ignore')"
                  >
                    x
                  </button>
                  <button
                    :disabled="item.subscribed || recommendationSubscribing === item.code"
                    :title="item.subscribed ? '已订阅' : '订阅作品'"
                    :aria-label="item.subscribed ? '已订阅' : '订阅作品'"
                    @click.stop="subscribeRecommendation(item)"
                  >
                    {{ recommendationSubscribing === item.code ? "..." : item.subscribed ? "✓" : "+" }}
                  </button>
                </div>
              </div>
            </article>
          </div>
        </section>
        <section v-else-if="page === 'javdb'">
          <form class="javdb-search" @submit.prevent="loadJavdb">
            <input
              v-model="javdbQuery"
              aria-label="搜索作品"
              placeholder="番号或标题"
            /><button type="submit">搜索</button
            ><button
              type="button"
              title="恢复最近更新"
              @click="
                javdbQuery = '';
                loadJavdb();
              "
            >
              最新
            </button>
          </form>
          <p v-if="javdbLoading" class="empty">正在读取 JavDB...</p>
          <div v-else class="recommendations">
            <p v-if="!javdbItems.length" class="empty">没有找到作品</p>
            <article
              v-for="item in javdbItems"
              :key="item.code"
              class="work-card clickable"
              @click="openJavdbDetail(item)"
            >
              <div class="poster">
                <img
                  v-if="item.cover_url"
                  :src="item.cover_url"
                  :alt="item.title"
                  loading="lazy"
                />
              </div>
              <div>
                <div class="card-title">
                  <b>{{ item.code }}</b
                  ><strong v-if="item.magnets_count"
                    >{{ item.magnets_count }} 磁链</strong
                  >
                </div>
                <p>{{ item.title }}</p>
                <small
                  >{{ item.release_date || "日期未知"
                  }}<template v-if="item.actors?.length">
                    · {{ item.actors.slice(0, 2).join("、") }}</template
                  ></small
                >
              </div>
            </article>
          </div>
          <section v-if="javdbDetail" class="detail-panel">
            <div class="panel-heading">
              <div>
                <h2>{{ javdbDetail.code }}</h2>
                <small>{{ javdbDetail.title }}</small>
              </div>
              <button
                title="关闭详情"
                aria-label="关闭详情"
                @click="closeJavdbDetail"
              >
                x
              </button>
            </div>
            <img
              v-if="javdbDetail.cover_url"
              class="detail-cover"
              :src="javdbDetail.cover_url"
              :alt="javdbDetail.title"
            />
            <p v-if="javdbDetail.origin_title">
              {{ javdbDetail.origin_title }}
            </p>
            <p><b>演员：</b>{{ javdbDetail.actors?.join("、") || "未知" }}</p>
            <p>
              <b>类型：</b>{{ javdbDetail.categories?.join("、") || "未知" }}
            </p>
            <p><b>磁链：</b>{{ javdbDetail.magnets?.length || 0 }}</p>
          </section>
        </section>
        <section v-else-if="page === 'actors'">
          <div class="javdb-search">
            <input
              v-model="actorQuery"
              aria-label="筛选演员"
              placeholder="筛选演员名称"
            /><button type="button" title="刷新演员列表" @click="loadActors()">
              刷新
            </button>
          </div>
          <p v-if="actorLoading" class="empty">正在读取演员列表...</p>
          <div v-else class="actor-grid">
            <button
              v-for="actor in filteredActors"
              :key="actor.id"
              class="actor-card"
              @click="openActor(actor)"
            >
              <img
                v-if="actor.avatar_url"
                :src="actor.avatar_url"
                :alt="actor.name"
                loading="lazy"
              /><span v-else class="actor-placeholder">{{
                actor.name.slice(0, 1)
              }}</span
              ><b>{{ actor.name }}</b
              ><small>{{ actor.name_zht || actor.other_name }}</small>
            </button>
          </div>
          <section v-if="selectedActor" class="detail-panel">
            <div class="panel-heading">
              <div class="actor-heading">
                <img
                  v-if="selectedActor.avatar_url"
                  :src="selectedActor.avatar_url"
                  :alt="selectedActor.name"
                />
                <div>
                  <h2>{{ selectedActor.name }}</h2>
                  <small>{{
                    selectedActor.name_zht || selectedActor.other_name
                  }}</small>
                </div>
              </div>
              <button
                title="关闭演员详情"
                aria-label="关闭演员详情"
                @click="selectedActor = null"
              >
                x
              </button>
            </div>
            <div class="recommendations compact">
              <article
                v-for="item in actorMovies"
                :key="item.code"
                class="work-card clickable"
                @click="viewJavdbDetail(item)"
              >
                <div class="poster">
                  <img
                    v-if="item.cover_url"
                    :src="item.cover_url"
                    :alt="item.title"
                    loading="lazy"
                  />
                </div>
                <div>
                  <b>{{ item.code }}</b>
                  <p>{{ item.title }}</p>
                </div>
              </article>
            </div>
          </section>
        </section>
        <section v-else-if="page === 'subscriptions'" class="subscription-page">
          <div class="panel-heading">
            <div>
              <h2>订阅中心</h2>
              <small>订阅与洗版监控</small>
            </div>
            <button @click="loadSubscriptions">刷新</button>
          </div>
          <form
            class="subscription-create"
            @submit.prevent="createSubscription"
          >
            <input
              v-model="subscriptionCode"
              aria-label="创建订阅"
              placeholder="输入番号创建订阅"
            /><button
              :disabled="subscriptionCreating || !subscriptionCode.trim()"
              type="submit"
            >
              {{ subscriptionCreating ? "创建中" : "创建" }}
            </button>
          </form>
          <p v-if="subscriptionLoading" class="empty">正在读取订阅...</p>
          <div v-else class="subscription-list">
            <article
              v-for="subscription in subscriptions"
              :key="subscription.id"
              class="subscription-row"
            >
              <div>
                <div class="subscription-heading">
                  <b>{{
                    subscription.code || subscription.title || "未命名订阅"
                  }}</b
                  ><span
                    :class="[
                      'badge',
                      subscription.type === 'upgrade' ? 'upgrade' : 'completed',
                    ]"
                    >{{
                      subscription.type === "upgrade" ? "洗版" : "订阅"
                    }}</span
                  ><span
                    :class="[
                      'badge',
                      subscription.status === 'submitted'
                        ? 'completed'
                        : subscription.status === 'waiting_quota'
                          ? 'queued'
                          : '',
                    ]"
                    >{{ subscription.status || "active" }}</span
                  >
                </div>
                <small
                  v-if="
                    subscription.title &&
                    subscription.title !== subscription.code
                  "
                  >{{ subscription.title }}</small
                ><small
                  v-if="subscription.last_submit_error"
                  class="subscription-error"
                  >{{ subscription.last_submit_error }}</small
                ><small v-else-if="subscription.retry_after_at"
                  >下次重试：{{
                    new Date(subscription.retry_after_at).toLocaleString()
                  }}</small
                >
              </div>
              <div class="detail-actions">
                <button
                  title="立即检测"
                  aria-label="立即检测"
                  @click="actOnSubscription('check_once', subscription)"
                >
                  检测</button
                ><button
                  v-if="
                    subscription.status === 'submitted' ||
                    subscription.status === 'waiting_quota' ||
                    subscription.status === 'submit_failed'
                  "
                  title="重新提交"
                  aria-label="重新提交"
                  @click="
                    actOnSubscription(
                      subscription.status === 'submitted'
                        ? 'reset_submit'
                        : 'retry_submit',
                      subscription,
                    )
                  "
                >
                  重试</button
                ><button
                  title="删除订阅"
                  aria-label="删除订阅"
                  @click="actOnSubscription('delete', subscription)"
                >
                  x
                </button>
              </div>
            </article>
            <p v-if="!subscriptions.length" class="empty">暂无订阅</p>
          </div>
        </section>
        <section v-else-if="page === 'files'">
          <div class="file-tabs" role="tablist" aria-label="文件功能">
            <button
              :class="{ active: fileTab === 'hardlinks' }"
              @click="openFiles('hardlinks')"
            >
              硬链接
            </button>
            <button
              :class="{ active: fileTab === 'actor-management' }"
              @click="openFiles('actor-management')"
            >
              演员管理
            </button>
          </div>
          <template v-if="fileTab === 'hardlinks'">
            <div class="panel-heading">
              <div>
                <h2>硬链接</h2>
                <small>源文件与媒体库硬链接关系</small>
              </div>
              <div class="detail-actions">
                <button :disabled="hardlinksScanning" @click="scanHardlinks">
                  {{ hardlinksScanning ? "扫描中" : "扫描" }}
                </button>
                <button :disabled="hardlinksScanning" @click="loadHardlinks">
                  刷新
                </button>
              </div>
            </div>
            <p v-if="hardlinksLoading" class="empty">正在读取硬链接...</p>
            <div v-else class="hardlink-list">
              <article
                v-for="group in hardlinkGroups"
                :key="group.code"
                class="hardlink-row"
              >
                <div>
                  <b>{{ group.code }}</b
                  ><small
                    v-for="(entry, index) in group.entries?.slice(0, 2)"
                    :key="index"
                    >{{ entry.source_path || "源文件缺失" }}</small
                  >
                </div>
                <span
                  :class="[
                    'badge',
                    group.status === 'healthy' ? 'completed' : 'failed',
                  ]"
                  >{{ group.hardlink_count || 0 }} 个硬链接</span
                >
                <button
                  class="danger-button"
                  :disabled="!group.entries?.length"
                  @click="openHardlinkDelete(group)"
                >
                  删除
                </button>
              </article>
              <p v-if="!hardlinkGroups.length" class="empty">暂无硬链接记录</p>
            </div>
          </template>
          <template v-else>
            <div class="panel-heading">
              <div>
                <h2>演员管理</h2>
                <small>{{
                  embyActorsTotal
                    ? `${embyActorsTotal} 位 Emby 演员`
                    : "以 Emby 演员库为准"
                }}</small>
              </div>
              <div class="detail-actions">
                <button
                  :disabled="duplicatesLoading"
                  @click="loadActorDuplicates"
                >
                  {{ duplicatesLoading ? "检测中" : "检查重名" }}</button
                ><button @click="loadEmbyActors">刷新</button>
              </div>
            </div>
            <div class="actor-management-tools">
              <input
                v-model="embyActorQuery"
                aria-label="搜索 Emby 演员"
                placeholder="搜索 Emby 演员"
                @keyup.enter="loadEmbyActors"
              /><button @click="loadEmbyActors">搜索</button
              ><select v-model="embyActorSort" aria-label="演员排序" @change="loadEmbyActors">
                <option value="name">名称</option>
                <option value="recent">最近更新</option>
              </select
              ><span v-if="mappingStatus" class="muted"
                >映射表：{{
                  mappingStatus.exists
                    ? `${mappingStatus.record_count || 0} 条`
                    : "未配置"
                }}</span
              >
            </div>
            <div class="segmented actor-language" aria-label="演员名称显示语言">
              <button
                :class="{ active: actorDisplayLanguage === 'zh_cn' }"
                @click="
                  actorDisplayLanguage = 'zh_cn';
                  loadEmbyActors();
                "
              >
                简中</button
              ><button
                :class="{ active: actorDisplayLanguage === 'zh_tw' }"
                @click="
                  actorDisplayLanguage = 'zh_tw';
                  loadEmbyActors();
                "
              >
                繁中</button
              ><button
                :class="{ active: actorDisplayLanguage === 'jp' }"
                @click="
                  actorDisplayLanguage = 'jp';
                  loadEmbyActors();
                "
              >
                日文
              </button>
            </div>
            <section v-if="duplicateGroups.length" class="duplicate-groups">
              <div class="panel-heading">
                <div>
                  <h2>重名候选</h2>
                  <small
                    >{{
                      duplicateGroups.length
                    }}
                    组，点击演员查看资料与关联作品</small
                  >
                </div>
                <button @click="duplicateGroups = []">关闭</button>
              </div>
              <div
                v-for="group in duplicateGroups"
                :key="group.key"
                class="duplicate-group"
              >
                <span class="muted">{{ group.key }}</span
                ><button
                  v-for="actor in group.actors"
                  :key="actor.id"
                  class="duplicate-actor"
                  @click="openEmbyActor(actor)"
                >
                  <img
                    v-if="actor.avatar_url"
                    :src="actor.avatar_url"
                    :alt="actor.name"
                    loading="lazy"
                  /><span>{{ actor.display_name || actor.name }}</span>
                </button>
              </div>
            </section>
            <p v-if="embyActorsLoading" class="empty">正在读取 Emby 演员...</p>
            <div v-else class="actor-grid emby-actor-grid">
              <button
                v-for="actor in embyActors"
                :key="actor.id"
                class="actor-card"
                @click="openEmbyActor(actor)"
              >
                <img
                  v-if="actor.avatar_url"
                  :src="actor.avatar_url"
                  :alt="actor.name"
                  loading="lazy"
                /><span v-else class="actor-placeholder">{{
                  actor.name.slice(0, 1)
                }}</span
                ><b>{{ actorName(actor) }}</b
                ><small>{{
                  actor.name_jp || actor.sort_name || actor.name
                }}</small>
              </button>
            </div>
            <section v-if="selectedEmbyActor" class="detail-panel">
              <div class="panel-heading">
                <div class="actor-heading">
                  <img
                    v-if="selectedEmbyActor.avatar_url"
                    :src="selectedEmbyActor.avatar_url"
                    :alt="selectedEmbyActor.name"
                  />
                  <div>
                    <h2>{{ actorName(selectedEmbyActor) }}</h2>
                    <small>{{
                      selectedEmbyActor.name_jp || selectedEmbyActor.sort_name
                    }}</small>
                  </div>
                </div>
                <div class="detail-actions">
                  <button
                    :disabled="gfriendsLoading"
                    @click="loadGfriendsCandidates"
                  >
                    {{ gfriendsLoading ? "加载中" : "Gfriends" }}</button
                  ><a
                    v-if="selectedEmbyActor.emby_url"
                    :href="selectedEmbyActor.emby_url"
                    target="_blank"
                    rel="noopener"
                    >Emby</a
                  ><button
                    title="关闭演员详情"
                    aria-label="关闭演员详情"
                    @click="closeEmbyActor"
                  >
                    x
                  </button>
                </div>
              </div>
              <div class="actor-profile">
                <div>
                  <span>Emby 名称</span
                  ><b>{{ selectedEmbyActor.name || "未设置" }}</b>
                </div>
                <div>
                  <span>Emby 排序名</span
                  ><b>{{ selectedEmbyActor.sort_name || "未设置" }}</b>
                </div>
                <div>
                  <span>简中名</span
                  ><b>{{ selectedEmbyActor.name_zh_cn || "未匹配" }}</b>
                </div>
                <div>
                  <span>繁中名</span
                  ><b>{{ selectedEmbyActor.name_zh_tw || "未匹配" }}</b>
                </div>
                <div>
                  <span>日文名</span
                  ><b>{{ selectedEmbyActor.name_jp || "未匹配" }}</b>
                </div>
                <div class="actor-profile-aliases">
                  <span>别名</span
                  ><b>{{ selectedEmbyActor.aliases || "无" }}</b>
                </div>
              </div>
              <p v-if="selectedEmbyActor.overview" class="actor-overview">
                {{ selectedEmbyActor.overview }}
              </p>
              <div
                v-if="
                  selectedEmbyActor.provider_ids &&
                  Object.keys(selectedEmbyActor.provider_ids).length
                "
                class="actor-provider-links"
              >
                <template
                  v-for="(value, provider) in selectedEmbyActor.provider_ids"
                  :key="provider"
                  ><a
                    v-if="providerUrl(provider, value)"
                    :href="providerUrl(provider, value)"
                    target="_blank"
                    rel="noopener"
                    >{{ provider }}</a
                  ><span v-else>{{ provider }}: {{ value }}</span></template
                >
              </div>
              <div v-if="gfriendsCandidates.length" class="gfriends-grid">
                <button
                  v-for="candidate in gfriendsCandidates"
                  :key="candidate.remote_url"
                  :disabled="avatarSaving"
                  class="gfriends-candidate"
                  :title="candidate.name"
                  @click="applyGfriendsAvatar(candidate)"
                >
                  <img
                    :src="candidate.url"
                    :alt="candidate.name"
                    loading="lazy"
                  /><span>{{ candidate.name }}</span>
                </button>
              </div>
              <div class="recommendations compact">
                <article
                  v-for="item in selectedEmbyActorMovies"
                  :key="item.code"
                  class="work-card clickable"
                @click="viewJavdbDetail(item)"
                >
                  <div class="poster">
                    <img
                      v-if="item.cover_url"
                      :src="item.cover_url"
                      :alt="item.title"
                      loading="lazy"
                    />
                  </div>
                  <div>
                    <b>{{ item.code }}</b>
                    <p>{{ item.title }}</p>
                  </div>
                </article>
                <p v-if="!selectedEmbyActorMovies.length" class="empty">
                  未读取到关联作品
                </p>
              </div>
            </section>
          </template>
        </section>
        <section v-else-if="page === 'plugins'" class="panel">
          <div class="panel-heading">
            <h2>插件</h2>
            <button @click="refresh">重新扫描</button>
          </div>
          <p v-if="!plugins.length" class="empty">尚未恢复插件源码</p>
          <div v-for="plugin in plugins" :key="plugin.id" class="job-row">
            <div>
              <b>{{ plugin.name || plugin.id }}</b
              ><small>{{ plugin.description || plugin.id }}</small>
            </div>
            <div class="plugin-actions">
              <button
                class="plugin-config-button"
                title="配置插件"
                aria-label="配置插件"
                @click="openPluginConfig(plugin)"
              >
                ⚙</button
              ><span
                :class="['badge', plugin.loaded ? 'completed' : 'failed']"
                >{{ plugin.loaded ? "已加载" : "加载失败" }}</span
              ><button
                :class="['plugin-toggle', { enabled: plugin.enabled }]"
                :title="plugin.enabled ? '停用插件' : '启用插件'"
                :aria-label="plugin.enabled ? '停用插件' : '启用插件'"
                @click="togglePlugin(plugin)"
              >
                <i />
              </button>
            </div>
          </div>
          <section
            v-if="selectedPlugin"
            class="detail-panel plugin-config-panel"
          >
            <div class="panel-heading">
              <div>
                <h2>{{ selectedPlugin.name || selectedPlugin.id }}</h2>
                <small>插件配置</small>
              </div>
              <button
                title="关闭配置"
                aria-label="关闭配置"
                @click="selectedPlugin = null"
              >
                x
              </button>
            </div>
            <div class="config-fields">
              <label
                v-for="(schema, key) in selectedPlugin.config_schema || {}"
                :key="key"
                ><span>{{ schema.label || key }}</span
                ><input
                  v-if="schema.type !== 'boolean'"
                  v-model="pluginConfig[key]"
                  :type="
                    schema.type === 'password'
                      ? 'password'
                      : schema.type === 'number'
                        ? 'number'
                        : 'text'
                  "
                  :min="schema.min"
                  :max="schema.max"
                /><input
                  v-else
                  v-model="pluginConfig[key]"
                  type="checkbox"
                /><small v-if="schema.description">{{
                  schema.description
                }}</small></label
              >
            </div>
            <p v-if="pluginTestMessage" class="plugin-test-message">
              {{ pluginTestMessage }}
            </p>
            <div class="config-save">
              <button
                v-if="canTestPlugin(selectedPlugin)"
                :disabled="pluginTesting"
                @click="testPlugin"
              >
                {{ pluginTesting ? "测试中" : "测试连接" }}</button
              ><button :disabled="pluginConfigSaving" @click="savePluginConfig">
                {{ pluginConfigSaving ? "保存中" : "保存配置" }}
              </button>
            </div>
          </section>
        </section>
        <section v-else class="panel">
          <div class="panel-heading">
            <div>
              <h2>设置</h2>
              <small>恢复中的基础配置</small>
            </div>
            <button
              @click="
                loadMappingStatus();
                loadCoreSettings();
                loadSystemLogs();
                loadHardlinkConfig();
                loadFacefusionSettings();
                loadWhisperSettings();
                loadLadaSettings();
                loadUiSettings();
              "
            >
              刷新
            </button>
          </div>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>界面</h3>
                <small>设定所有浏览器的封面模糊默认状态</small>
              </div>
            </div>
            <label class="settings-toggle">
              <input
                v-model="coverBlurGlobal"
                type="checkbox"
                :disabled="coverBlurSaving"
                @change="saveCoverBlurGlobal"
              />
              <span>{{ coverBlurSaving ? "正在保存..." : "默认模糊作品封面" }}</span>
            </label>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>Emby</h3>
                <small>媒体库、演员与封面读取使用此连接</small>
              </div>
              <button :disabled="coreSettingsLoading" @click="loadCoreSettings">
                刷新
              </button>
            </div>
            <div class="config-fields">
              <label
                ><span>服务器地址</span
                ><input v-model="embySettings.server" type="text" placeholder="http://host:8096"
              /></label>
              <label
                ><span>API 密钥</span
                ><input v-model="embySettings.api_key" type="password" autocomplete="off"
              /></label>
              <label
                ><span>用户 ID</span
                ><input v-model="embySettings.user_id" type="text"
              /></label>
            </div>
            <div class="config-save">
              <button :disabled="embySettingsSaving" @click="saveEmbySettings">
                {{ embySettingsSaving ? "保存中" : "保存 Emby 设置" }}
              </button>
            </div>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>网络</h3>
                <small>下载模型、插件和映射表时使用</small>
              </div>
              <button :disabled="coreSettingsLoading" @click="loadCoreSettings">
                刷新
              </button>
            </div>
            <div class="config-fields">
              <label
                ><span>加速模式</span
                ><select v-model="networkSettings.acceleration_mode">
                  <option value="mirror">镜像</option>
                  <option value="proxy">代理</option>
                  <option value="direct">直连</option>
                </select></label>
              <label
                ><span>HTTP 代理</span
                ><input v-model="networkSettings.http_proxy" type="text" placeholder="http://host:port"
              /></label>
              <label
                ><span>GitHub 镜像</span
                ><input v-model="networkSettings.github_mirror" type="text"
              /></label>
              <label
                ><span>Hugging Face 镜像</span
                ><input v-model="networkSettings.hf_mirror" type="text"
              /></label>
              <label
                ><span>PyPI 镜像</span
                ><input v-model="networkSettings.pip_mirror" type="text"
              /></label>
              <label
                ><span>Hugging Face Token</span
                ><input v-model="networkSettings.hf_token" type="password" autocomplete="off"
              /></label>
            </div>
            <div class="config-save">
              <button :disabled="networkSettingsSaving" @click="saveNetworkSettings">
                {{ networkSettingsSaving ? "保存中" : "保存网络设置" }}
              </button>
            </div>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>Emby Webhook</h3>
                <small>接收 Emby 的媒体变更或测试通知</small>
              </div>
              <button :disabled="systemLogsLoading" @click="loadSystemLogs">
                刷新日志
              </button>
            </div>
            <div class="webhook-url-row">
              <code>{{ embyWebhookUrl }}</code>
              <button @click="copyEmbyWebhookUrl">复制</button>
            </div>
            <div v-if="webhookInstructionsVisible" class="webhook-instructions">
              <p>在 Emby 管理后台的 Webhook 插件中新建通知，并填写上方地址。</p>
              <p>请求内容类型选择 <code>application/json</code>；发送测试通知后，下方应出现接收日志。</p>
            </div>
            <p v-if="systemLogsLoading" class="empty">正在读取系统日志...</p>
            <div v-else class="system-log-list">
              <p v-if="!systemLogs.length" class="empty">暂无系统日志</p>
              <div v-for="entry in systemLogs" :key="entry.id" class="system-log-row">
                <time>{{ new Date(entry.timestamp).toLocaleString() }}</time>
                <span>{{ entry.source }}</span>
                <b>{{ entry.message }}</b>
              </div>
            </div>
          </section>
          <section class="settings-section">
            <h3>Emby 演员映射</h3>
            <p>
              填写 MDC-NG 根目录，NOOR 会自动读取其
              `data/data/mapping_actor.xml`。
            </p>
            <div class="settings-inline">
              <input
                v-model="mdcNgPath"
                aria-label="MDC-NG 路径"
                placeholder="/path/to/mdc-ng"
              /><button :disabled="mappingSaving" @click="saveMdcNgPath">
                {{ mappingSaving ? "保存中" : "保存" }}
              </button>
            </div>
            <small v-if="mappingStatus">{{
              mappingStatus.exists
                ? `已加载 ${mappingStatus.record_count || 0} 条映射`
                : "尚未找到映射表"
            }}</small>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>Whisper</h3>
                <small>媒体详情中的字幕任务会使用这些默认参数</small>
              </div>
              <button @click="loadWhisperSettings">刷新</button>
            </div>
            <p v-if="whisperSettingsLoading" class="empty">
              正在读取 Whisper 设置...
            </p>
            <div v-else class="config-fields">
              <label
                ><span>识别模型</span
                ><select v-model="whisperSettings.model">
                  <option value="anime-whisper">Anime Whisper</option>
                  <option value="large-v3">Faster Whisper large-v3</option>
                  <option value="whisper-ja">Whisper Japanese</option>
                  <option value="qwen">Qwen ASR</option>
                </select></label
              ><label
                ><span>语言</span
                ><select v-model="whisperSettings.language">
                  <option value="ja">日语</option>
                  <option value="auto">自动</option>
                </select></label
              ><label
                ><span>VAD</span
                ><select v-model="whisperSettings.vad_method">
                  <option value="semantic">语义 VAD</option>
                  <option value="silero">Silero VAD</option>
                  <option value="none">关闭</option>
                </select></label
              ><label
                ><span>翻译目标</span
                ><select v-model="whisperSettings.translate_to">
                  <option value="">不翻译</option>
                  <option value="zh">简体中文</option>
                  <option value="zh-TW">繁体中文</option>
                </select></label
              ><label
                ><span>翻译模型</span
                ><input
                  v-model="whisperSettings.translate_model"
                  type="text" /></label
              ><label
                ><span>翻译服务地址</span
                ><input
                  v-model="whisperSettings.translate_base_url"
                  type="text"
              /></label>
            </div>
            <div class="config-save">
              <button
                :disabled="whisperSettingsSaving || whisperSettingsLoading"
                @click="saveWhisperSettings"
              >
                {{ whisperSettingsSaving ? "保存中" : "保存 Whisper 设置" }}
              </button>
            </div>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>硬链接扫描</h3>
                <small>仅用于识别源文件与媒体库中的同一文件</small>
              </div>
              <button :disabled="hardlinkConfigLoading" @click="loadHardlinkConfig">
                刷新
              </button>
            </div>
            <p v-if="hardlinkConfigLoading" class="empty">正在读取扫描路径...</p>
            <template v-else>
              <div class="hardlink-settings-groups">
                <div
                  v-for="(group, index) in hardlinkScanGroups"
                  :key="index"
                  class="hardlink-settings-row"
                >
                  <label
                    ><span>源目录</span
                    ><input v-model="group.source_dir" type="text" placeholder="源文件目录"
                  /></label>
                  <label
                    ><span>媒体库目录</span
                    ><input v-model="group.hardlink_dir" type="text" placeholder="硬链接目录"
                  /></label>
                  <button
                    class="icon-button"
                    title="删除扫描组"
                    aria-label="删除扫描组"
                    @click="removeHardlinkScanGroup(index)"
                  >
                    x
                  </button>
                </div>
              </div>
              <div class="config-save hardlink-settings-actions">
                <button :disabled="hardlinkConfigSaving" @click="addHardlinkScanGroup">
                  添加扫描组
                </button>
                <button
                  class="primary-button"
                  :disabled="hardlinkConfigSaving"
                  @click="saveHardlinkConfig"
                >
                  {{ hardlinkConfigSaving ? "保存中" : "保存扫描路径" }}
                </button>
              </div>
            </template>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>LADA</h3>
                <small>去码任务默认使用以下模型与编码参数</small>
              </div>
              <button :disabled="ladaInfoLoading" @click="loadLadaSettings">
                刷新
              </button>
            </div>
            <p v-if="ladaInfoLoading" class="empty">正在读取 LADA 设置...</p>
            <template v-else>
              <div class="config-fields">
                <label
                  ><span>CLI 路径</span
                  ><input v-model="ladaConfig.cli_path" type="text"
                /></label>
                <label
                  ><span>执行设备</span
                  ><select v-model="ladaDefaults.device">
                    <option v-for="device in ladaInfo.devices || []" :key="device.id" :value="device.id">
                      {{ device.name || device.id }}
                    </option>
                  </select></label>
                <label
                  ><span>检测模型</span
                  ><select v-model="ladaDefaults.detection_model">
                    <option
                      v-for="model in ladaInfo.detection_models || []"
                      :key="model.id"
                      :value="model.id"
                      :disabled="!model.downloaded"
                    >
                      {{ model.name || model.id }}{{ model.downloaded ? "" : "（未下载）" }}
                    </option>
                  </select></label>
                <label
                  ><span>恢复模型</span
                  ><select v-model="ladaDefaults.restoration_model">
                    <option
                      v-for="model in ladaInfo.restoration_models || []"
                      :key="model.id"
                      :value="model.id"
                      :disabled="!model.downloaded"
                    >
                      {{ model.name || model.id }}{{ model.downloaded ? "" : "（未下载）" }}
                    </option>
                  </select></label>
                <label
                  ><span>编码预设</span
                  ><select v-model="ladaDefaults.encoding_preset">
                    <option v-for="preset in ladaInfo.encoding_presets || []" :key="preset.id" :value="preset.id">
                      {{ preset.name || preset.id }}
                    </option>
                  </select></label>
                <label
                  ><span>最大分段秒数</span
                  ><input v-model.number="ladaDefaults.max_clip_length" type="number" min="10" max="3600"
                /></label>
                <label
                  ><span>半精度 FP16</span
                  ><input v-model="ladaDefaults.fp16" type="checkbox"
                /></label>
                <label
                  ><span>检测人脸马赛克</span
                  ><input v-model="ladaDefaults.detect_face_mosaics" type="checkbox"
                /></label>
              </div>
              <div class="config-save">
                <button :disabled="ladaSettingsSaving" @click="saveLadaSettings">
                  {{ ladaSettingsSaving ? "保存中" : "保存 LADA 设置" }}
                </button>
              </div>
            </template>
          </section>
          <section class="settings-section">
            <div class="panel-heading">
              <div>
                <h3>换脸</h3>
                <small>默认参数会在提交任务时使用</small>
              </div>
              <button @click="loadFacefusionSettings">刷新</button>
            </div>
            <p v-if="facefusionSettingsLoading" class="empty">
              正在读取换脸设置...
            </p>
            <template v-else
              ><div class="config-fields">
                <label
                  ><span>FaceFusion 目录</span
                  ><input
                    v-model="facefusionSettings.facefusion_dir"
                    type="text" /></label
                ><label
                  ><span>模型目录</span
                  ><input
                    v-model="facefusionSettings.facefusion_model_dir"
                    type="text" /></label
                ><label
                  ><span>运行时缓存</span
                  ><input
                    v-model="facefusionSettings.facefusion_cache_dir"
                    type="text" /></label
                ><label
                  ><span>临时文件</span
                  ><input
                    v-model="facefusionSettings.facefusion_temp_dir"
                    type="text" /></label
                ><label
                  ><span>执行后端</span
                  ><select
                    v-model="facefusionSettings.facefusion_execution_provider"
                  >
                    <option value="cuda">CUDA</option>
                    <option value="tensorrt">TensorRT</option>
                    <option value="cpu">CPU</option>
                  </select></label
                ><label
                  ><span>设备 ID</span
                  ><input
                    v-model="facefusionSettings.facefusion_device_ids"
                    type="text" /></label
                ><label
                  ><span>处理器</span
                  ><input
                    v-model="facefusionSettings.facefusion_processors"
                    type="text" /></label
                ><label
                  ><span>执行线程</span
                  ><input
                    v-model.number="facefusionSettings.facefusion_thread_count"
                    type="number"
                    min="1"
                    max="32" /></label
                ><label
                  ><span>人脸选择</span
                  ><select
                    v-model="facefusionSettings.facefusion_face_selector_mode"
                  >
                    <option value="reference">参考脸</option>
                    <option value="many">全部</option>
                    <option value="one">单脸</option>
                  </select></label
                ><label
                  ><span>视频编码</span
                  ><select
                    v-model="facefusionSettings.facefusion_output_video_encoder"
                  >
                    <option value="libx264">H.264</option>
                    <option value="h264_nvenc">H.264 NVENC</option>
                    <option value="hevc_nvenc">HEVC NVENC</option>
                    <option value="libx265">H.265</option>
                  </select></label
                >
              </div>
              <section
                v-for="group in facefusionSettingsGroups"
                :key="group.title"
                class="facefusion-settings-group"
              >
                <h4>{{ group.title }}</h4>
                <div class="config-fields">
                  <label v-for="key in group.fields" :key="key"
                    ><span>{{ facefusionSettingLabels[key] || key }}</span
                    ><input
                      v-if="typeof facefusionSettings[key] === 'number'"
                      v-model.number="facefusionSettings[key]"
                      type="number" /><input
                      v-else
                      v-model="facefusionSettings[key]"
                      type="text"
                  /></label>
                </div>
              </section>
              <div class="config-save">
                <button
                  :disabled="facefusionSettingsSaving"
                  @click="saveFacefusionSettings"
                >
                  {{ facefusionSettingsSaving ? "保存中" : "保存换脸设置" }}
                </button>
              </div></template
            >
          </section>
        </section>
      </template>
    </main>
    <div
      v-if="hardlinkDeleteGroup"
      class="modal-backdrop"
      role="presentation"
      @click.self="closeHardlinkDelete"
    >
      <section
        class="modal-dialog delete-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="hardlink-delete-title"
      >
        <div class="modal-heading">
          <div>
            <h2 id="hardlink-delete-title">
              删除 {{ hardlinkDeleteGroup.code }}
            </h2>
            <small>将删除媒体库硬链接、源文件及其关联 NFO</small>
          </div>
          <button
            class="icon-button"
            aria-label="关闭"
            :disabled="hardlinkDeleting"
            @click="closeHardlinkDelete"
          >
            x
          </button>
        </div>
        <p v-if="hardlinkDeleteLoading" class="empty">正在检查将删除的文件...</p>
        <template v-else>
          <p class="delete-warning">
            此操作不可恢复。空的作品目录会一并清理；共享目录中其他作品的文件不会删除。
          </p>
          <div class="delete-preview">
            <div>
              <b>{{ previewPaths(hardlinkDeletePreview, ['deleted_files', 'removed_files']).length || hardlinkDeleteGroup.hardlink_count || 0 }}</b>
              <small>文件将被删除</small>
            </div>
            <div>
              <b>{{ previewPaths(hardlinkDeletePreview, ['deleted_dirs', 'removed_dirs']).length }}</b>
              <small>空目录将被清理</small>
            </div>
            <div>
              <b>{{ hardlinkDeleteGroup.orphan_count || 0 }}</b>
              <small>异常链接</small>
            </div>
          </div>
          <div class="delete-paths">
            <small>源文件与硬链接</small>
            <code
              v-for="(entry, index) in hardlinkDeleteGroup.entries"
              :key="`${entry.source_path}-${index}`"
              >{{ entry.source_path || '源文件缺失' }}</code
            >
          </div>
          <p v-if="hardlinkDeletePreview?.detail || hardlinkDeletePreview?.message" class="muted">
            {{ hardlinkDeletePreview?.detail || hardlinkDeletePreview?.message }}
          </p>
          <div class="modal-actions">
            <button :disabled="hardlinkDeleting" @click="closeHardlinkDelete">取消</button>
            <button class="danger-button" :disabled="hardlinkDeleting" @click="confirmHardlinkDelete">
              {{ hardlinkDeleting ? '正在删除...' : '确认删除' }}
            </button>
          </div>
        </template>
      </section>
    </div>
  </div>
</template>

<style>
:root {
  color: #e9edf2;
  background: #11151b;
  font-family: Inter, "Noto Sans SC", system-ui, sans-serif;
}
* {
  box-sizing: border-box;
}
body {
  margin: 0;
  min-width: 320px;
}
button {
  font: inherit;
  cursor: pointer;
}
.app-shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 224px minmax(0, 1fr);
  background: #11151b;
}
.sidebar {
  background: #171c24;
  border-right: 1px solid #2b333f;
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  letter-spacing: 0;
  padding: 0 8px;
}
.brand-mark {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  background: #168bdf;
  color: white;
  font-size: 14px;
}
nav {
  display: grid;
  gap: 4px;
}
nav button {
  color: #aab4c1;
  background: transparent;
  border: 0;
  text-align: left;
  padding: 10px 12px;
  border-radius: 5px;
  display: flex;
  justify-content: space-between;
}
nav button:hover,
nav button.active {
  color: #fff;
  background: #26313e;
}
.count {
  color: #b9dfff;
  font-size: 12px;
}
.sidebar-foot {
  margin-top: auto;
  color: #8995a5;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 8px;
}
.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cf5663;
}
.status-dot.online {
  background: #45c18a;
}
main {
  min-width: 0;
  padding: 30px;
  max-width: 1440px;
  width: 100%;
  margin: auto;
}
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}
.header-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.header-command {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 8px 11px;
}
.eyebrow {
  color: #6e8095;
  font-size: 12px;
  margin: 0 0 5px;
}
h1,
h2,
p {
  margin-top: 0;
}
h1 {
  font-size: 26px;
  margin-bottom: 0;
}
h2 {
  font-size: 16px;
}
.icon-button {
  width: 36px;
  height: 36px;
  border: 1px solid #3a4655;
  background: #202833;
  color: #e9edf2;
  border-radius: 5px;
  font-size: 20px;
}
.header-actions .icon-button {
  width: 36px;
  height: 36px;
}
.header-actions .icon-button.active {
  background: #176fae;
  border-color: #38a2ec;
  color: #fff;
}
.cover-blurred .poster,
.cover-blurred .media-poster {
  overflow: hidden;
}
.cover-blurred .poster img,
.cover-blurred .media-poster img,
.cover-blurred .detail-cover,
.cover-blurred .work-card img {
  filter: blur(18px);
  transform: scale(1.04);
}
.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.stat,
.panel,
.notice {
  background: #1a212b;
  border: 1px solid #303a47;
  border-radius: 6px;
}
.stat {
  padding: 18px;
  display: grid;
  gap: 8px;
}
.stat span,
small {
  color: #98a6b7;
}
.stat strong {
  font-size: 30px;
}
.wide {
  grid-column: 1 / -1;
}
.panel {
  padding: 18px;
}
.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-heading button {
  color: #8fc9f5;
  border: 0;
  background: none;
}
.job-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  padding: 13px 0;
  border-top: 1px solid #2b3440;
}
.job-row div {
  min-width: 0;
}
.job-row b,
.job-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.job-row small {
  margin-top: 4px;
}
.badge {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 999px;
  background: #394553;
  color: #dce5ee;
}
.badge.completed {
  background: #173f31;
  color: #8fe4b8;
}
.badge.failed {
  background: #4b2830;
  color: #ffafb9;
}
.progress {
  margin-top: 8px;
  height: 4px;
  background: #303a47;
  width: min(300px, 100%);
}
.progress i {
  display: block;
  height: 100%;
  background: #168bdf;
}
.notice {
  padding: 14px;
  color: #aeb9c6;
}
.notice.error {
  border-color: #80424d;
  color: #ffbec6;
}
.empty {
  color: #93a0b0;
  padding: 22px 0;
}
pre {
  max-height: 60vh;
  overflow: auto;
  color: #cdd9e6;
  font-size: 12px;
  line-height: 1.55;
}
.recommendation-controls {
  margin-bottom: 14px;
}
.recommendation-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
}
.recommendation-summary span,
.recommendation-sources span {
  display: inline-flex;
  align-items: center;
  border: 1px solid #354454;
  border-radius: 4px;
  background: #17202a;
  color: #aab9c9;
  font-size: 11px;
  line-height: 1;
}
.recommendation-summary span {
  padding: 7px 9px;
}
.segmented {
  display: inline-flex;
  border: 1px solid #3a4655;
  border-radius: 5px;
  overflow: hidden;
}
.segmented button {
  border: 0;
  background: transparent;
  color: #aab4c1;
  padding: 7px 11px;
}
.segmented button.active {
  background: #26394c;
  color: #fff;
}
.muted {
  color: #98a6b7;
  font-size: 12px;
}
.javdb-search {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.javdb-search input {
  flex: 1;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.javdb-search button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
}
.recommendations {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 14px;
}
.work-card {
  min-width: 0;
  background: #1a212b;
  border: 1px solid #303a47;
  border-radius: 6px;
  overflow: hidden;
}
.work-card.clickable {
  cursor: pointer;
}
.poster {
  position: relative;
  aspect-ratio: 2 / 3;
  background: #242d39;
}
.poster img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.poster span {
  position: absolute;
  top: 8px;
  left: 8px;
  padding: 3px 6px;
  background: #168bdf;
  color: white;
  font-size: 11px;
  border-radius: 4px;
}
.work-card > div:last-child {
  padding: 10px;
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.work-card b {
  color: #a9d5f7;
  font-size: 12px;
}
.card-title strong {
  color: #8fe4b8;
  font-size: 14px;
}
.work-card p {
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.4;
  min-height: 54px;
  overflow: hidden;
}
.work-card small {
  line-height: 1.4;
}
.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 5px;
  margin-top: 10px;
}
.recommendation-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  min-height: 21px;
  margin-top: 8px;
}
.recommendation-sources span {
  padding: 4px 5px;
}
.card-actions button {
  width: 25px;
  height: 25px;
  border: 1px solid #3a4655;
  background: #202833;
  color: #c9d3dd;
  border-radius: 4px;
}
.card-actions button:disabled {
  cursor: default;
  opacity: 0.55;
}
.actor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(116px, 1fr));
  gap: 10px;
}
.actor-card {
  min-width: 0;
  border: 1px solid #303a47;
  border-radius: 6px;
  padding: 8px;
  background: #1a212b;
  color: #dce5ee;
  text-align: left;
  display: grid;
  gap: 6px;
}
.actor-card img,
.actor-placeholder {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  background: #242d39;
  display: grid;
  place-items: center;
  color: #98a6b7;
}
.actor-card b,
.actor-card small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actor-card small {
  color: #98a6b7;
}
.detail-panel {
  margin-top: 18px;
  padding: 18px;
  background: #1a212b;
  border: 1px solid #303a47;
  border-radius: 6px;
  overflow: auto;
}
.detail-panel .panel-heading button {
  width: 30px;
  height: 30px;
  border: 1px solid #3a4655;
  background: #202833;
  color: #dce5ee;
  border-radius: 4px;
}
.detail-cover {
  width: min(240px, 100%);
  margin: 12px 0;
  display: block;
}
.actor-heading {
  display: flex;
  align-items: center;
  gap: 12px;
}
.actor-heading img {
  width: 64px;
  height: 64px;
  object-fit: cover;
}
.compact {
  margin-top: 14px;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
}
.global-search-panel {
  border: 1px solid #303a47;
  border-radius: 6px;
  background: #171c24;
  padding: 16px;
  margin: -12px 0 22px;
}
.global-search-results {
  display: grid;
  gap: 16px;
}
.global-search-results h2 {
  margin: 0 0 8px;
  color: #aab4c1;
  font-size: 13px;
}
.resource-list {
  border-top: 1px solid #2b3440;
}
.resource-row {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 9px 0;
  border-bottom: 1px solid #2b3440;
}
.resource-row img {
  width: 36px;
  height: 50px;
  object-fit: cover;
  background: #242d39;
}
.resource-row div {
  min-width: 0;
}
.resource-row b,
.resource-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.resource-row small {
  margin-top: 4px;
}
.resource-actions {
  display: inline-flex;
  gap: 6px;
}
.resource-row button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 6px 9px;
}
.resource-row button:disabled {
  opacity: 0.55;
  cursor: default;
}
.media-library__controls {
  margin-bottom: 16px;
}
.library-picker {
  display: flex;
  min-width: 0;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.library-picker button,
.media-pagination button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
  white-space: nowrap;
}
.library-picker button.active {
  background: #1b5b88;
  border-color: #218bd0;
  color: #fff;
}
.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}
.media-card {
  min-width: 0;
  cursor: pointer;
  border: 1px solid #303a47;
  border-radius: 6px;
  overflow: hidden;
  background: #1a212b;
}
.media-card:hover {
  border-color: #4e7492;
}
.media-poster {
  position: relative;
  aspect-ratio: 2 / 3;
  background: #242d39;
}
.media-poster img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.media-poster span {
  position: absolute;
  top: 7px;
  left: 7px;
  background: #177ebc;
  color: #fff;
  font-size: 11px;
  padding: 3px 5px;
  border-radius: 3px;
}
.media-poster .facefusion-badge {
  opacity: 0;
  background: #a04fba;
  transition: opacity 0.15s ease;
}
.media-card:hover .media-poster .facefusion-badge,
.media-card:focus-within .media-poster .facefusion-badge {
  opacity: 1;
}
.media-delete-button {
  position: absolute;
  inset: 50% auto auto 50%;
  transform: translate(-50%, -50%);
  z-index: 1;
  border: 1px solid #b15862;
  border-radius: 5px;
  background: rgba(67, 30, 37, 0.96);
  color: #fff1f2;
  padding: 8px 12px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
  white-space: nowrap;
}
.media-card.delete-menu-open .media-poster::after {
  position: absolute;
  inset: 0;
  content: "";
  background: rgba(4, 8, 12, 0.48);
}
.media-card > div:last-child {
  display: grid;
  gap: 5px;
  padding: 9px;
}
.media-card b {
  color: #dce5ee;
  font-size: 13px;
  line-height: 1.35;
  height: 3.9em;
  overflow: hidden;
}
.media-card small {
  font-size: 11px;
}
.media-pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  margin: 22px 0 4px;
  color: #98a6b7;
  font-size: 12px;
}
.media-pagination button:disabled {
  opacity: 0.45;
  cursor: default;
}
.media-path {
  color: #98a6b7;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.file-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid #303a47;
  margin-bottom: 20px;
}
.file-tabs button {
  border: 0;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: #9ba8b6;
  padding: 9px 12px;
}
.file-tabs button.active {
  border-bottom-color: #168bdf;
  color: #fff;
}
.task-tabs {
  margin-top: 16px;
}
.hardlink-list {
  display: grid;
  gap: 8px;
}
.hardlink-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 13px 0;
  border-bottom: 1px solid #2b3440;
}
.hardlink-row div {
  min-width: 0;
}
.hardlink-row b,
.hardlink-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.hardlink-row small {
  margin-top: 5px;
}
.danger-button {
  border: 1px solid #994952;
  border-radius: 5px;
  background: #392229;
  color: #ffc0c8;
  padding: 6px 10px;
  white-space: nowrap;
}
.danger-button:disabled {
  cursor: default;
  opacity: 0.48;
}
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(5, 9, 13, 0.72);
}
.modal-dialog {
  width: min(600px, 100%);
  max-height: min(720px, calc(100vh - 40px));
  overflow: auto;
  border: 1px solid #3a4655;
  border-radius: 6px;
  background: #1a212b;
  box-shadow: 0 20px 70px rgba(0, 0, 0, 0.45);
  padding: 20px;
}
.modal-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.modal-heading h2 {
  margin: 0;
  font-size: 18px;
}
.modal-heading small {
  display: block;
  margin-top: 6px;
}
.icon-button {
  width: 30px;
  height: 30px;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
}
.delete-warning {
  margin: 20px 0 14px;
  color: #ffc8ce;
  line-height: 1.55;
}
.delete-preview {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border: 1px solid #303a47;
  background: #171c24;
}
.delete-preview > div {
  display: grid;
  gap: 4px;
  padding: 12px;
  border-left: 1px solid #303a47;
}
.delete-preview > div:first-child {
  border-left: 0;
}
.delete-preview b {
  color: #f3f6fa;
  font-size: 18px;
}
.delete-preview small,
.delete-paths > small {
  color: #98a6b7;
  font-size: 12px;
}
.delete-paths {
  display: grid;
  gap: 7px;
  margin-top: 16px;
}
.delete-paths code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: 1px solid #303a47;
  background: #121820;
  color: #c9d4df;
  padding: 7px 9px;
  font-size: 12px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.modal-actions > button:not(.danger-button) {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 6px 10px;
}
.actor-management-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 0;
}
.actor-management-tools input,
.actor-management-tools select {
  flex: 1;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.actor-management-tools select {
  flex: 0 0 auto;
  max-width: 112px;
}
.actor-management-tools button,
.detail-actions a {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
  text-decoration: none;
}
.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.emby-actor-grid {
  margin-top: 12px;
}
.subscription-create {
  display: flex;
  gap: 8px;
  margin: 16px 0;
}
.subscription-create input {
  flex: 1;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.subscription-create button,
.detail-actions button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
}
.subscription-create button:disabled {
  opacity: 0.5;
  cursor: default;
}
.subscription-list {
  display: grid;
  gap: 0;
}
.subscription-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 14px 0;
  border-top: 1px solid #2b3440;
}
.subscription-row > div:first-child {
  min-width: 0;
  display: grid;
  gap: 5px;
}
.subscription-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
}
.badge.upgrade {
  background: #453a26;
  color: #f2cf82;
}
.badge.queued {
  background: #303d52;
  color: #a8cafa;
}
.subscription-error {
  color: #ffb4bc;
}
.settings-section {
  border-top: 1px solid #2b3440;
  border-bottom: 1px solid #2b3440;
  padding: 16px 0;
  margin: 16px 0;
}
.settings-section h3 {
  margin: 0 0 6px;
  font-size: 14px;
}
.settings-section p {
  color: #98a6b7;
  font-size: 13px;
}
.settings-toggle {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: #dce5ee;
  font-size: 13px;
}
.settings-toggle input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #168bdf;
}
.settings-inline {
  display: flex;
  gap: 8px;
}
.settings-inline input {
  flex: 1;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.settings-inline button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
}
.facefusion-settings-group {
  border-top: 1px solid #2b3440;
  margin-top: 18px;
  padding-top: 16px;
}
.facefusion-settings-group h4 {
  margin: 0 0 12px;
  font-size: 13px;
  color: #b9c6d4;
}
.gfriends-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 8px;
  margin: 16px 0;
}
.gfriends-candidate {
  min-width: 0;
  padding: 5px;
  border: 1px solid #3a4655;
  border-radius: 5px;
  color: #cdd9e6;
  background: #202833;
  display: grid;
  gap: 5px;
  text-align: left;
}
.gfriends-candidate img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  background: #171c24;
}
.gfriends-candidate span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
.facefusion-panel {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #303a47;
}
.facefusion-controls {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin: 14px 0;
}
.facefusion-controls > label {
  display: grid;
  gap: 6px;
  color: #cdd9e6;
  font-size: 13px;
}
.facefusion-controls select {
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.processor-options {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-height: 36px;
  align-items: center;
}
.processor-options label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #bfcbd7;
}
.facefusion-source-heading {
  margin: 18px 0 10px;
}
.facefusion-source-heading h3 {
  margin: 0 0 4px;
  font-size: 14px;
}
.upload-button {
  display: inline-flex;
  align-items: center;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
  cursor: pointer;
}
.upload-button input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}
.facefusion-source-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  gap: 8px;
}
.facefusion-source {
  position: relative;
  min-width: 0;
}
.facefusion-source > button:first-child {
  width: 100%;
  min-width: 0;
  padding: 4px;
  border: 1px solid #3a4655;
  border-radius: 5px;
  color: #cdd9e6;
  background: #202833;
  display: grid;
  gap: 5px;
  text-align: left;
}
.facefusion-source > button:first-child.selected {
  border-color: #33a3ed;
  box-shadow: inset 0 0 0 1px #33a3ed;
}
.facefusion-source > button:first-child img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  background: #171c24;
}
.facefusion-source > button:first-child span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}
.facefusion-source-delete {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 22px;
  height: 22px;
  border: 1px solid #6d424a;
  border-radius: 4px;
  background: #2c2025;
  color: #ffd8dc;
  line-height: 1;
}
.facefusion-submit {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.facefusion-submit button {
  border: 1px solid #177bc2;
  border-radius: 5px;
  background: #168bdf;
  color: #fff;
  padding: 8px 12px;
}
.facefusion-submit button:disabled {
  opacity: 0.5;
  cursor: default;
}
.subtitle-panel {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #303a47;
}
.subtitle-panel h3 {
  margin: 0 0 4px;
  font-size: 14px;
}
.subtitle-list {
  border-top: 1px solid #2b3440;
  margin-top: 14px;
}
.subtitle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #2b3440;
}
.subtitle-row div {
  min-width: 0;
}
.subtitle-row b,
.subtitle-row small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.subtitle-row small {
  margin-top: 4px;
}
.subtitle-row a,
.subtitle-row button {
  flex: none;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 6px 9px;
  text-decoration: none;
}
.subtitle-row button:disabled {
  opacity: 0.55;
  cursor: default;
}
.subtitle-online {
  margin-top: 20px;
}
.plugin-actions {
  display: inline-flex;
  align-items: center;
  gap: 9px;
}
.plugin-toggle {
  width: 32px;
  height: 18px;
  border: 0;
  border-radius: 9px;
  padding: 2px;
  background: #485463;
}
.plugin-toggle i {
  display: block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #d7dee7;
  transition: transform 0.16s ease;
}
.plugin-toggle.enabled {
  background: #168bdf;
}
.plugin-toggle.enabled i {
  transform: translateX(14px);
}
.plugin-config-button {
  width: 28px;
  height: 28px;
  border: 1px solid #3a4655;
  border-radius: 5px;
  color: #cdd9e6;
  background: #202833;
}
.config-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
  margin-top: 16px;
}
.config-fields label {
  display: grid;
  align-content: start;
  gap: 6px;
  color: #cdd9e6;
  font-size: 13px;
}
.config-fields input[type="text"],
.config-fields input[type="password"],
.config-fields input[type="number"],
.config-fields select {
  width: 100%;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.config-fields input[type="checkbox"] {
  width: 16px;
  height: 16px;
  margin: 2px 0;
  accent-color: #168bdf;
}
.config-fields small {
  color: #98a6b7;
  line-height: 1.4;
}
.config-save {
  display: flex;
  justify-content: flex-end;
  margin-top: 18px;
}
.config-save button {
  border: 1px solid #177bc2;
  border-radius: 5px;
  background: #168bdf;
  color: white;
  padding: 8px 12px;
}
.primary-button {
  border-color: #177bc2 !important;
  background: #168bdf !important;
  color: #fff !important;
}
.hardlink-settings-groups {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}
.hardlink-settings-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 30px;
  align-items: end;
  gap: 10px;
}
.hardlink-settings-row label {
  display: grid;
  gap: 6px;
  color: #cdd9e6;
  font-size: 13px;
}
.hardlink-settings-row input {
  width: 100%;
  min-width: 0;
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #171c24;
  color: #e9edf2;
  padding: 8px 10px;
}
.hardlink-settings-actions {
  justify-content: space-between;
}
.hardlink-settings-actions button:first-child {
  border-color: #3a4655;
  background: #202833;
  color: #dce5ee;
}
.webhook-url-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  margin-top: 14px;
}
.webhook-url-row code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  border: 1px solid #303a47;
  background: #171c24;
  color: #c9d4df;
  padding: 8px 10px;
}
.webhook-url-row button {
  border: 1px solid #3a4655;
  border-radius: 5px;
  background: #202833;
  color: #dce5ee;
  padding: 7px 11px;
}
.webhook-instructions {
  margin-top: 12px;
  padding: 10px 12px;
  border-left: 2px solid #168bdf;
  background: #172331;
  color: #c7d4e2;
  font-size: 13px;
  line-height: 1.5;
}
.webhook-instructions p {
  margin: 2px 0;
}
.system-log-list {
  display: grid;
  gap: 0;
  margin-top: 14px;
  border-top: 1px solid #303a47;
}
.system-log-row {
  display: grid;
  grid-template-columns: 156px 140px minmax(0, 1fr);
  gap: 10px;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid #2b3440;
  font-size: 12px;
}
.system-log-row time,
.system-log-row span {
  color: #98a6b7;
}
.system-log-row b {
  color: #dce5ee;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.plugin-test-message {
  margin: 14px 0 0;
  color: #aabbd0;
  font-size: 13px;
  line-height: 1.5;
}
.job-row-actionable {
  cursor: pointer;
}
.job-row-actionable:hover {
  background: #1d2732;
}
.job-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.job-actions button {
  border: 1px solid #854550;
  border-radius: 5px;
  background: #362229;
  color: #ffc0c8;
  padding: 6px 9px;
}
.job-actions button:disabled {
  opacity: 0.55;
  cursor: default;
}
.job-detail {
  margin-top: 16px;
}
.job-log {
  margin: 12px 0 0;
  padding: 12px;
  border: 1px solid #303a47;
  border-radius: 5px;
  background: #121820;
  max-height: 380px;
  white-space: pre-wrap;
  word-break: break-word;
}
.job-error {
  color: #ffb4bc;
  margin: 10px 0;
}
.duplicate-groups {
  border-top: 1px solid #303a47;
  border-bottom: 1px solid #303a47;
  margin: 16px 0;
  padding: 13px 0;
}
.duplicate-group {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  padding: 9px 0;
  border-top: 1px solid #2b3440;
}
.duplicate-group > .muted {
  flex-basis: 100%;
}
.duplicate-actor {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 220px;
  border: 1px solid #3a4655;
  border-radius: 5px;
  padding: 4px 7px 4px 4px;
  color: #dce5ee;
  background: #202833;
}
.duplicate-actor img {
  width: 28px;
  height: 28px;
  object-fit: cover;
  background: #171c24;
}
.duplicate-actor span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actor-language {
  margin: 0 0 14px;
}
.actor-profile {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  margin: 16px 0;
}
.actor-profile > div {
  min-width: 0;
  padding: 10px;
  border: 1px solid #303a47;
  border-radius: 5px;
  background: #171c24;
  display: grid;
  gap: 5px;
}
.actor-profile span {
  color: #98a6b7;
  font-size: 11px;
}
.actor-profile b {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
}
.actor-profile-aliases {
  grid-column: 1 / -1;
}
.actor-overview {
  color: #c4cfda;
  white-space: pre-wrap;
  line-height: 1.6;
}
.actor-provider-links {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin: 14px 0;
}
.actor-provider-links a,
.actor-provider-links span {
  border: 1px solid #3a4655;
  border-radius: 5px;
  padding: 5px 8px;
  color: #b9dfff;
  background: #202833;
  font-size: 12px;
  text-decoration: none;
}
@media (max-width: 760px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    position: sticky;
    top: 0;
    z-index: 2;
    padding: 10px;
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }
  .brand {
    padding: 0;
  }
  .sidebar nav {
    display: flex;
    overflow-x: auto;
    flex: 1;
  }
  .sidebar nav button {
    white-space: nowrap;
  }
  .sidebar-foot {
    display: none;
  }
  main {
    padding: 18px;
  }
  .overview-grid,
  .facefusion-controls {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .wide {
    grid-column: 1 / -1;
  }
  .hardlink-settings-row {
    grid-template-columns: minmax(0, 1fr) 30px;
  }
  .hardlink-settings-row label:first-child {
    grid-column: 1 / -1;
  }
  .system-log-row {
    grid-template-columns: 1fr;
    gap: 3px;
  }
}
</style>
