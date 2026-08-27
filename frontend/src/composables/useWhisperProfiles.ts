export type WhisperModelBackend = 'chickenrice-zh' | 'anime-whisper' | 'large-v3'
export type WhisperStrategyMode = WhisperModelBackend
export type WhisperRuntimeTier = 'gpu_standard' | 'gpu_low_vram' | 'cpu'

export type WhisperTranslationOverrides = {
  runtime_tier?: string
  vad_backend?: string
  timing_refiner?: string
  translate_enabled?: boolean
  translate_to?: string
  translate_base_url?: string
  translate_api_key?: string
  translate_model?: string
  translate_style?: string
}

export type WhisperEditableDefaults = {
  model_backend: WhisperModelBackend
  runtime_tier: WhisperRuntimeTier
  vad_backend: string
  timing_refiner: string
  translate_enabled: boolean
  translate_to: string
  translate_base_url: string
  translate_api_key: string
  translate_model: string
  translate_style: string
}

export const WHISPER_MODEL_BACKENDS: WhisperModelBackend[] = [
  'chickenrice-zh',
  'anime-whisper',
  'large-v3',
]

export const WHISPER_RUNTIME_TIERS: WhisperRuntimeTier[] = [
  'gpu_standard',
  'gpu_low_vram',
  'cpu',
]

export function normalizeWhisperRuntimeTier(value?: string | null): WhisperRuntimeTier {
  const normalized = String(value || '').trim().toLowerCase().replace('-', '_')
  if (normalized === 'gpu_low_vram' || normalized === 'low_vram' || normalized === 'int8_float16') return 'gpu_low_vram'
  if (normalized === 'cpu' || normalized === 'cpu_int8') return 'cpu'
  return 'gpu_standard'
}

export function normalizeWhisperModelBackend(value?: string | null): WhisperModelBackend {
  const normalized = String(value || '').trim().toLowerCase()
  if (normalized === 'anime' || normalized === 'anime-whisper') return 'anime-whisper'
  if (normalized === 'large-v3' || normalized === 'large_v3') return 'large-v3'
  return 'chickenrice-zh'
}

export function isDirectWhisperTranslationBackend(modelBackend?: string | null) {
  return normalizeWhisperModelBackend(modelBackend) === 'chickenrice-zh'
}

export function buildWhisperProfile(modelBackend: WhisperModelBackend = 'chickenrice-zh', runtimeTier: WhisperRuntimeTier = 'gpu_standard') {
  const backend = normalizeWhisperModelBackend(modelBackend)
  const runtime_tier = normalizeWhisperRuntimeTier(runtimeTier)
  if (backend === 'anime-whisper') {
    return {
      strategy: 'chickenrice',
      subtitle_profile: 'standard',
      model_backend: 'anime-whisper',
      runtime_tier,
      whisper_task: 'transcribe',
      model: 'anime-whisper',
      pipeline_mode: 'anime',
      language: 'ja',
      sensitivity: 'balanced',
      chunker: 'smart_vad_chunk',
      target_chunk_duration_s: 30,
      max_chunk_duration_s: 30,
      segment_merge_max_gap_ms: 2000,
      segment_merge_max_duration_ms: 20000,
      timing_refiner: 'none',
    }
  }

  if (backend === 'large-v3') {
    return {
      strategy: 'chickenrice',
      subtitle_profile: 'standard',
      model_backend: 'large-v3',
      runtime_tier,
      whisper_task: 'transcribe',
      model: 'large-v3',
      pipeline_mode: 'faster',
      language: 'ja',
      sensitivity: 'balanced',
      chunker: 'smart_vad_chunk',
      target_chunk_duration_s: 30,
      max_chunk_duration_s: 30,
      segment_merge_max_gap_ms: 2000,
      segment_merge_max_duration_ms: 20000,
      timing_refiner: 'none',
    }
  }

  return {
    strategy: 'chickenrice',
    subtitle_profile: 'standard',
    model_backend: 'chickenrice-zh',
    runtime_tier,
    whisper_task: 'translate',
    model: 'chickenrice-zh',
    pipeline_mode: 'faster',
    language: 'ja',
    sensitivity: 'balanced',
    chunker: 'smart_vad_chunk',
    target_chunk_duration_s: 30,
    max_chunk_duration_s: 30,
    segment_merge_max_gap_ms: 2000,
    segment_merge_max_duration_ms: 20000,
    timing_refiner: 'none',
  }
}

export function resolveWhisperStrategyMode(strategy?: string | null, modelBackend?: string | null): WhisperModelBackend {
  return normalizeWhisperModelBackend(modelBackend || strategy)
}

export function resolveWhisperSelectableMode(strategy?: string | null, modelBackend?: string | null): WhisperModelBackend {
  return resolveWhisperStrategyMode(strategy, modelBackend)
}

export function buildWhisperProfileWithTranslation(
  modelBackend: WhisperModelBackend,
  overrides: WhisperTranslationOverrides = {},
) {
  const profile = buildWhisperProfile(modelBackend, normalizeWhisperRuntimeTier(overrides.runtime_tier))
  const directTranslate = profile.model_backend === 'chickenrice-zh'
  return {
    ...profile,
    runtime_tier: normalizeWhisperRuntimeTier(overrides.runtime_tier || (profile as any).runtime_tier),
    vad_backend: overrides.vad_backend || (profile as any).vad_backend || 'whisper_vad_onnx',
    timing_refiner: overrides.timing_refiner || (profile as any).timing_refiner || 'none',
    translate_to: directTranslate || overrides.translate_enabled == false ? '' : (overrides.translate_to || ''),
    translate_base_url: overrides.translate_base_url,
    translate_api_key: overrides.translate_api_key,
    translate_model: overrides.translate_model,
    translate_style: overrides.translate_style,
  }
}

export function resolveWhisperEditableDefaults(payload?: Record<string, any> | null): WhisperEditableDefaults {
  const whisper = payload || {}
  return {
    model_backend: normalizeWhisperModelBackend(whisper.model_backend || whisper.model || whisper.strategy),
    runtime_tier: normalizeWhisperRuntimeTier(whisper.runtime_tier),
    vad_backend: whisper.vad_backend || 'whisper_vad_onnx',
    timing_refiner: whisper.timing_refiner || 'none',
    translate_enabled: !!whisper.translate_to,
    translate_to: whisper.translate_to || 'zh',
    translate_base_url: whisper.translate_base_url || 'https://api.openai.com/v1',
    translate_api_key: whisper.translate_api_key || '',
    translate_model: whisper.translate_model || 'gpt-4o-mini',
    translate_style: whisper.translate_style || 'adult_explicit',
  }
}

export function getWhisperRuntimeTierMeta(runtimeTier: WhisperRuntimeTier) {
  const tier = normalizeWhisperRuntimeTier(runtimeTier)
  if (tier === 'gpu_low_vram') {
    return {
      titleKey: 'settings.whisper.runtimeTier.gpuLowVram.title',
      descKey: 'settings.whisper.runtimeTier.gpuLowVram.desc',
      badgeKey: 'settings.whisper.runtimeTier.gpuLowVram.badge',
    }
  }
  if (tier === 'cpu') {
    return {
      titleKey: 'settings.whisper.runtimeTier.cpu.title',
      descKey: 'settings.whisper.runtimeTier.cpu.desc',
      badgeKey: 'settings.whisper.runtimeTier.cpu.badge',
    }
  }
  return {
    titleKey: 'settings.whisper.runtimeTier.gpuStandard.title',
    descKey: 'settings.whisper.runtimeTier.gpuStandard.desc',
    badgeKey: 'settings.whisper.runtimeTier.gpuStandard.badge',
  }
}

export function getWhisperModelBackendMeta(modelBackend: WhisperModelBackend) {
  const backend = normalizeWhisperModelBackend(modelBackend)
  if (backend === 'anime-whisper') {
    return {
      titleKey: 'whisper.modelBackend.anime.title',
      descKey: 'whisper.modelBackend.anime.desc',
      stackKey: 'whisper.modelBackend.anime.stack',
      badgeKey: 'whisper.modelBackend.anime.badge',
    }
  }

  if (backend === 'large-v3') {
    return {
      titleKey: 'whisper.modelBackend.largeV3.title',
      descKey: 'whisper.modelBackend.largeV3.desc',
      stackKey: 'whisper.modelBackend.largeV3.stack',
      badgeKey: 'whisper.modelBackend.largeV3.badge',
    }
  }

  return {
    titleKey: 'whisper.recommended.title',
    descKey: 'whisper.recommended.desc',
    stackKey: 'whisper.recommended.stack',
    badgeKey: 'whisper.recommended.badge',
  }
}

export function getWhisperStrategyMeta(modelBackend: WhisperStrategyMode) {
  return getWhisperModelBackendMeta(modelBackend)
}

export function formatWhisperTranslationSummary(
  t: (key: string) => string,
  options: { translateEnabled: boolean; translateTo?: string; translateModel?: string; directTranslate?: boolean },
) {
  if (options.directTranslate) return t('settings.whisper.directTranslateOn')
  if (!options.translateEnabled) return t('settings.whisper.translationOff')
  return `${options.translateTo || 'zh'} · ${options.translateModel || 'gpt-4o-mini'}`
}

export function getWhisperSelectableStrategyPresentation(
  _t: (key: string) => string,
  modelBackend: WhisperStrategyMode,
) {
  const direct = normalizeWhisperModelBackend(modelBackend) === 'chickenrice-zh'
  return {
    summaryClass: '',
    badgeColor: direct ? 'info' : 'secondary',
  }
}
