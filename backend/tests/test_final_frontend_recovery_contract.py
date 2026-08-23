from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    path = ROOT / relative
    assert path.is_file(), f"missing source contract file: {path}"
    return path.read_text(encoding="utf-8")


def test_system_settings_final_recovery_contract() -> None:
    source = _read("frontend/src/views/settings/SystemSettings.vue")

    assert "const mdcNgActorMappingPath = ref('')" in source
    assert "mdc_ng_actor_mapping_path: mdcNgActorMappingPath.value" in source
    assert "mdcNgActorMappingPath.value = cfg.mdc_ng_actor_mapping_path || ''" in source

    assert "const webhookGuideVisible = ref(false)" in source
    assert "webhookGuideVisible.value = true" in source
    assert "navigator.clipboard?.writeText && window.isSecureContext" in source
    assert "document.execCommand('copy')" in source

    assert "const { globalBlurEnabled, syncGlobalBlur } = useBlurCover()" in source
    assert "saveGlobalBlur" in source

    assert "const effectiveMode = githubMirror.value || hfMirror.value || pipMirror.value" in source
    assert "github_token: githubToken.value" in source
    assert ".webhook-guide" in source
    assert ".settings-input" in source


def test_facefusion_settings_and_settings_index_final_contract() -> None:
    facefusion = _read("frontend/src/views/settings/FaceFusionSettings.vue")
    settings_index = _read("frontend/src/views/settings/SettingsIndex.vue")

    assert "const badgeAlwaysVisible = ref(false)" in facefusion
    assert "badge_always_visible: badgeAlwaysVisible.value" in facefusion
    assert "const faceTrackerScore = ref(0)" in facefusion
    assert "face_tracker_score: faceTrackerScore.value" in facefusion
    assert "const previewMode = ref('default')" in facefusion
    assert "preview_resolution" in facefusion

    assert "const LocalSubtitleLibrarySettings = defineAsyncComponent" in settings_index
    assert "'local-library'" in settings_index
    assert "t('settings.tab.local-library')" in settings_index
    assert "import('./LocalSubtitleLibrarySettings.vue')" in settings_index


def test_plugin_host_final_contract() -> None:
    source = _read("frontend/src/views/PluginHost.vue")

    assert "import { useRoute, useRouter } from 'vue-router'" in source
    assert "const router = useRouter()" in source
    assert "const { show: showSystemLog } = useSystemLog()" in source
    assert "createSharedDownloaderDialogContext" in source
    assert "openSubscriptionDialog" in source
    assert "let mountSeq = 0" in source
    assert "let sdkAbortController" in source
    assert "let sdkCleanupFns" in source

    assert "function makeTabs(options: any = {})" in source
    assert "routeConfig?.basePath" in source
    assert "routeMode" in source
    assert "window.addEventListener('noor-plugin-route-change'" in source
    assert "options.titleMeta" in source

    assert "function makeControlPanel(options: any = {})" in source
    assert "function makeControlPanelGroup(options: any = {})" in source
    assert "function makeControlPanelRow(options: any = {})" in source
    assert "function makeControlPanelSection(options: any = {})" in source

    assert "avatar: {" in source
    assert "'/plugins/gfriends/actions/candidates'" in source
    assert "function pluginDiagnostic(" in source
    assert "function clearMounted()" in source
    assert "onBeforeUnmount(clearMounted)" in source


def test_lada_panel_final_contract() -> None:
    source = _read("frontend/src/components/noor/LadaPanel.vue")

    assert "import { useI18n } from '../../composables/useI18n'" in source
    assert "import { useJobNavigation } from '../../composables/useJobNavigation'" in source
    assert "const { openJobsFocus } = useJobNavigation()" in source
    assert "initialSelectedPath?: string" in source
    assert "initialSelectedId?: string" in source
    assert "const submitStatus = ref<'idle' | 'running' | 'success' | 'error'>('idle')" in source
    assert "const submitProgress = ref(0)" in source
    assert "submitStatus.value = 'running'" in source
    assert "submitProgress.value = 72" in source
    assert "submitStatus.value = 'success'" in source
    assert "await openJobsFocus({ jobId: createdJob.id, chainId: createdJob.chain_id })" in source
    assert "VuiSubmitButton" in source
    assert "t('ladaPanel.start')" in source
    assert "t('ladaPanel.submitQueued')" in source
    assert "t('ladaPanel.submitFailed')" in source
    assert "panelTitle = computed(() => t('detail.openLada'))" in source


def test_whisper_settings_final_chickenrice_contract() -> None:
    source = _read("frontend/src/views/settings/WhisperSettings.vue")
    profiles = _read("frontend/src/composables/useWhisperProfiles.ts")

    assert "WHISPER_RUNTIME_TIERS" in source
    assert "WHISPER_MODEL_BACKENDS" in source
    assert "const activeRuntimeTier = ref<WhisperRuntimeTier>('gpu_standard')" in source
    assert "const activeModelBackend = ref<WhisperModelBackend>('chickenrice-zh')" in source
    assert "runtime_tier: activeRuntimeTier.value" in source
    assert "vad_backend: vadBackend.value" in source
    assert "timing_refiner: timingRefiner.value" in source
    assert "api.put('/settings/whisper', buildWhisperSettingsPayload())" in source

    assert "WHISPER_RUNTIME_TIERS" in profiles
    assert "export function getWhisperRuntimeTierMeta" in profiles
    assert "buildWhisperProfileWithTranslation" in profiles
    assert "formatWhisperTranslationSummary" in profiles

    retired_markers = (
        "selectedPipelines",
        "PIPELINE_SPECS",
        "pass1_pipeline",
        "pass2_pipeline",
        "merge_strategy",
        "applyBestDefaultsLocally",
        "saveBestDefaults",
        "vocal_isolation",
        "audio_preprocess",
        "enhancerOptions",
    )
    for marker in retired_markers:
        assert marker not in source, f"retired Whisper multi-chain marker leaked: {marker}"
