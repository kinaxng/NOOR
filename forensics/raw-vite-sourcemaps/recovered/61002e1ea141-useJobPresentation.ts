import { computed } from 'vue'
import { useI18n } from './useI18n'
import type { Job } from '../api/types'

export function resolveWhisperStrategyKey(job: Partial<Job>) {
  const execution = (job as Job).result_metadata?.whisper_execution as { strategy?: string } | undefined
  const raw = String(execution?.strategy || (job as Job).settings?.strategy || '').trim().toLowerCase()
  if (raw === 'recommended' || raw === 'best' || raw === 'chickenrice' || raw === 'chickenrice-zh') return 'chickenrice'
  return raw ? 'legacy' : ''
}

type JobRuntimeView = {
  status?: string
  phaseKey?: string
  phaseGroup?: string
  phaseLabel?: string
  detail?: string
}

type JobCardView = {
  badgeLabel: string
  badgeTone: string
  iconName: string
  iconClass: string
}

type JobProgressView = {
  mode: 'hidden' | 'running'
  phaseLabel: string
  detailLine: string
  showOverall: boolean
  overallValue: number
  overallText: string
  showPhase: boolean
  phaseValue: number
  phaseText: string
}

type JobDescriptionView = {
  summaryLine: string
  metaLine: string
}

type JobDisplayState = {
  phaseLine: string
  detailLine: string
  summaryLine: string
  metaLine: string
}

type JobChainProgressView = {
  progress: number
  text: string
}

function sortChainJobs(a: Job, b: Job) {
  const order = (job: Job) => {
    if (job.depends_on_task_id) return 1
    if (job.parent_task_id) return 1
    return 0
  }
  const diff = order(a) - order(b)
  if (diff !== 0) return diff
  return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
}

const PHASE_GROUP_MAP: Record<string, string> = {
  prepare: 'prepare',
  extract_audio: 'prepare',
  load_subtitle: 'prepare',
  analyze: 'analyze',
  detect: 'analyze',
  segment: 'analyze',
  segment_text: 'analyze',
  transcribe: 'transcribe',
  transcribe_primary: 'transcribe',
  retry: 'retry',
  align: 'align',
  translate: 'translate',
  process: 'process',
  restore: 'process',
  postprocess: 'process',
  merge_output: 'process',
  encode: 'encode',
  output: 'output',
  write_output: 'output',
  finalize: 'output',
}

export function useJobPresentation(allJobs?: () => Job[]) {
  const { t, i18nVersion, currentLang } = useI18n()

  const runningLabel = computed(() => { void i18nVersion.value; return t('jobs.running') })
  const connectingLabel = computed(() => { void i18nVersion.value; return t('jobs.status.connecting') })
  const queuedLabel = computed(() => { void i18nVersion.value; return t('jobs.status.queued') })
  const blockedLabel = computed(() => { void i18nVersion.value; return t('jobs.status.blocked') })
  const completedLabel = computed(() => { void i18nVersion.value; return t('jobs.status.completed') })
  const failedLabel = computed(() => { void i18nVersion.value; return t('jobs.status.failed') })
  const cancelledLabel = computed(() => { void i18nVersion.value; return t('jobs.status.cancelled') })
  const skippedLabel = computed(() => { void i18nVersion.value; return t('jobs.status.skipped') })

  const phaseGroupLabel = computed(() => {
    void i18nVersion.value
    return (phaseKey?: string, phaseLabel?: string) => {
      const group = phaseKey ? PHASE_GROUP_MAP[phaseKey] : ''
      if (group === 'prepare') return t('jobs.phase.prepare')
      if (group === 'analyze') return t('jobs.phase.analyze')
      if (group === 'transcribe') return t('jobs.phase.transcribe')
      if (group === 'retry') return t('jobs.phase.retry')
      if (group === 'align') return t('jobs.phase.align')
      if (group === 'translate') return t('jobs.phase.translate')
      if (group === 'process') return t('jobs.phase.process')
      if (group === 'encode') return t('jobs.phase.encode')
      if (group === 'output') return t('jobs.phase.output')
      return phaseLabel || ''
    }
  })

  const fallbackStatusLabel = computed(() => {
    void i18nVersion.value
    return (status: string) => {
      if (status === 'running') return runningLabel.value
      if (status === 'blocked') return blockedLabel.value
      if (status === 'queued' || status === 'pending') return queuedLabel.value
      if (status === 'completed') return completedLabel.value
      if (status === 'failed') return failedLabel.value
      if (status === 'cancelled') return cancelledLabel.value
      if (status === 'skipped') return skippedLabel.value
      return status
    }
  })

  const getJobTypeLabel = computed(() => {
    void i18nVersion.value
    return (jobType?: string) => {
      if (jobType === 'whisper' || jobType === 'whisper_transcribe') return t('jobs.type.whisper')
      if (jobType === 'translate-srt' || jobType === 'subtitle_translate') return t('jobs.translateTag')
      if (jobType === 'lada' || jobType === 'lada_restore') return t('jobs.type.lada')
      if (jobType === 'facefusion_restore') return t('jobs.type.facefusion')
      if (jobType === 'external_task') return t('jobs.type.external')
      return t('dashboard.unknown')
    }
  })

  const getJobTypeLabelForJob = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const ext = job.result_metadata?.external_task as { provider_label?: string } | undefined
      if ((job.job_type === 'external_task' || ext) && ext?.provider_label) {
        return ext.provider_label
      }
      return getJobTypeLabel.value(job.job_type)
    }
  })

  const getWhisperStrategyLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (!(job.job_type === 'whisper' || job.job_type === 'whisper_transcribe')) return ''
      const strategy = resolveWhisperStrategyKey(job)
      if (strategy === 'chickenrice') return t('jobs.strategy.recommended')
      if (strategy) return t('jobs.strategy.legacy')
      return ''
    }
  })

  const getWhisperStrategyHint = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (!(job.job_type === 'whisper' || job.job_type === 'whisper_transcribe')) return ''
      const strategy = resolveWhisperStrategyKey(job)
      if (strategy === 'legacy') return t('jobs.strategyHint.legacy')
      return ''
    }
  })

  const getJobHeaderMetaTokens = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const execution = (job as Job).result_metadata?.whisper_execution as { summary?: string } | undefined
      return [
        getJobTypeLabelForJob.value(job),
        getWhisperStrategyLabel.value(job),
        execution?.summary || '',
        job.chain_id ? getChainStepLabel.value(job) : '',
        getChainPositionLabel.value(job),
        getChainStatusSummary.value(job),
        getJobChainHint.value(job),
      ].filter(Boolean)
    }
  })

  const getDashboardJobMetaTokens = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, createdLabel?: string) => {
      return [
        getJobTypeLabelForJob.value(job),
        createdLabel || '',
      ].filter(Boolean)
    }
  })

  const formatDashboardRelativeTime = computed(() => {
    void i18nVersion.value
    return (dateStr?: string) => {
      if (!dateStr) return t('dashboard.unknown')
      const date = new Date(dateStr)
      const now = new Date()
      const diff = now.getTime() - date.getTime()
      const mins = Math.floor(diff / 60000)
      if (mins < 1) return t('dashboard.justNow')
      if (mins < 60) return t('dashboard.minsAgo', { n: mins })
      const hours = Math.floor(mins / 60)
      if (hours < 24) return t('dashboard.hoursAgo', { n: hours })
      return date.toLocaleDateString('zh-CN')
    }
  })

  const formatJobDateTime = computed(() => {
    void i18nVersion.value
    return (dateStr?: string) => {
      if (!dateStr) return t('common.notAvailable')
      return new Date(dateStr).toLocaleString(currentLang.value === 'zh' ? 'zh-CN' : 'en-US')
    }
  })

  const getDashboardJobChips = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const chips = [] as string[]
      if (job.chain_id) {
        const stepLabel = getChainStepLabel.value(job)
        if (stepLabel) chips.push(stepLabel)
      }
      const positionLabel = getChainPositionLabel.value(job)
      if (positionLabel) chips.push(positionLabel)
      const chainSummary = getChainStatusSummary.value(job)
      if (chainSummary) chips.push(chainSummary)
      const chainHint = getJobChainHint.value(job)
      if (chainHint) chips.push(chainHint)
      return chips
    }
  })


  const getJobTypeChipClass = computed(() => {
    void i18nVersion.value
    return (jobType?: string) => {
      if (jobType === 'translate-srt' || jobType === 'subtitle_translate') {
        return 'bg-accent-cyan/20 text-accent-cyan border-accent-cyan/30'
      }
      if (jobType === 'external_task') {
        return 'bg-accent-blue/18 text-accent-blue border-accent-blue/28'
      }
      return 'bg-accent-magenta/20 text-accent-magenta border-accent-magenta/30'
    }
  })

  const getWhisperStrategyChipClass = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const strategy = resolveWhisperStrategyKey(job)
      if (strategy === 'chickenrice') {
        return 'bg-accent-blue/18 text-accent-blue border-accent-blue/28'
      }
      if (strategy === 'legacy') {
        return 'bg-white/6 text-white/55 border-white/10'
      }
      return 'bg-white/6 text-white/55 border-white/10'
    }
  })

  const getJobDisplayName = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => job.emby_item_name || job.input_path?.split('/')?.pop() || job.id || ''
  })

  const getChainMembers = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (!job.chain_id || !allJobs) return [] as Job[]
      return allJobs().filter(candidate => candidate.chain_id === job.chain_id).sort(sortChainJobs)
    }
  })

  const getChainStepLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.job_type === 'whisper' || job.job_type === 'whisper_transcribe') return t('jobs.chain.stepTranscribe')
      if (job.job_type === 'translate-srt' || job.job_type === 'subtitle_translate') return t('jobs.chain.stepTranslate')
      if (job.job_type === 'lada' || job.job_type === 'lada_restore' || job.job_type === 'facefusion_restore') return t('jobs.chain.stepProcess')
      return t('jobs.chain.stepTask')
    }
  })


  const getChainRoleLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (!job.chain_id) return ''
      if (job.depends_on_task_id) return t('jobs.chain.roleFollowup')
      if (job.id && allJobs && allJobs().some(candidate => candidate.depends_on_task_id === job.id)) {
        return t('jobs.chain.rolePrimary')
      }
      return ''
    }
  })

  const getChainWaitingLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const isTranslate = job.job_type === 'translate-srt' || job.job_type === 'subtitle_translate'
      if (job.status === 'blocked' && isTranslate && job.depends_on_task_id) {
        return t('jobs.chain.waitingPrimaryDone')
      }
      return ''
    }
  })

  const getChainPositionLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const members = getChainMembers.value(job)
      if (members.length <= 1 || !job.id) return ''
      const index = members.findIndex(member => member.id === job.id)
      if (index < 0) return ''
      return t('jobs.chain.position', { current: index + 1, total: members.length })
    }
  })

  const getChainStatusSummary = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const members = getChainMembers.value(job)
      if (members.length <= 1) return ''
      const completed = members.filter(member => member.status === 'completed').length
      return t('jobs.chain.summary', { done: completed, total: members.length })
    }
  })

  const getChainFlowLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const members = getChainMembers.value(job)
      if (members.length <= 1) return ''
      const labels = members
        .map(member => getChainStepLabel.value(member))
        .filter((label, index, arr) => !!label && arr.indexOf(label) === index)
      return labels.join(' → ')
    }
  })

  const getJobChainHint = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const isTranslate = job.job_type === 'translate-srt' || job.job_type === 'subtitle_translate'
      if (job.status === 'blocked' && isTranslate && job.depends_on_task_id) {
        return t('jobs.chain.waitingTranscription')
      }
      if (job.status === 'skipped' && job.depends_on_task_id) {
        return t('jobs.chain.skippedUpstream')
      }
      if (job.parent_task_id) {
        return t('jobs.chain.childTask')
      }
      if (job.id && allJobs && allJobs().some(candidate => candidate.depends_on_task_id === job.id)) {
        return t('jobs.chain.hasFollowUp')
      }
      return ''
    }
  })

  const getJobPhaseLine = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => job.detail || phaseGroupLabel.value(job.phase_group || job.phase_key, job.phase_label) || ''
  })

  const getActivityDetailLine = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      const status = job.status || ''
      if (status === 'failed') {
        return (job as Job).error_message || job.detail || phaseGroupLabel.value(job.phase_group || job.phase_key, job.phase_label) || ''
      }
      if (status === 'running' || status === 'queued' || status === 'blocked' || status === 'pending') {
        return getJobPhaseLine.value(job)
      }
      if (status === 'cancelled' || status === 'skipped') {
        return job.detail || ''
      }
      return ''
    }
  })

  const getEffectiveViewState = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView = {}) => {
      const phaseKey = runtime.phaseKey || job.phase_key || ''
      const phaseGroup = runtime.phaseGroup || job.phase_group || phaseKey
      const phaseLabel = phaseGroupLabel.value(phaseGroup, runtime.phaseLabel || job.phase_label || '') || ''
      const detail = runtime.detail || job.detail || ''
      const statusLabel = runtime.status || fallbackStatusLabel.value(job.status || '')
      return {
        phaseKey,
        phaseLabel,
        detail,
        statusLabel,
      }
    }
  })

  const getDisplayPhaseLine = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView = {}) => {
      const view = getEffectiveViewState.value(job, runtime)
      if (!view.detail) return view.phaseLabel
      if (view.phaseKey === 'retry' || view.phaseKey === 'align') {
        return view.phaseLabel ? `${view.phaseLabel} · ${view.detail}` : view.detail
      }
      return view.detail
    }
  })

  const shouldShowPhaseProgress = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status !== 'running') return false
      if (!job.phase_key) return false
      if (job.phase_key === 'finalize') return false
      const phaseProgress = Number(job.phase_progress ?? 0)
      return phaseProgress >= 0 && phaseProgress <= 100
    }
  })

  const getRunningBadgeLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtimeStatus?: string) => {
      if (job.status === 'queued' || job.status === 'pending') return queuedLabel.value
      if (job.status === 'blocked') return blockedLabel.value
      if (runtimeStatus === connectingLabel.value) return connectingLabel.value
      if (job.status === 'running') return runningLabel.value
      return fallbackStatusLabel.value(job.status || '')
    }
  })

  const getStatusTone = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'completed') return 'success'
      if (job.status === 'failed') return 'error'
      if (job.status === 'cancelled') return 'warning'
      if (job.status === 'skipped') return 'warning'
      if (job.status === 'blocked' || job.status === 'queued' || job.status === 'pending') return 'warning'
      return 'info'
    }
  })

  const getTerminalBadgeVariant = computed(() => {
    void i18nVersion.value
    return (status: string) => (status === 'completed' || status === 'failed' ? 'gradient' : 'standard')
  })

  const getTerminalBadgeLabel = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'cancelled') return cancelledLabel.value
      if (job.status === 'skipped') return skippedLabel.value
      if (job.status === 'failed') return failedLabel.value
      if (job.status === 'completed') return completedLabel.value
      return fallbackStatusLabel.value(job.status || '')
    }
  })

  const getHistoryProgressValue = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'completed') return 100
      if (job.status === 'failed' || job.status === 'cancelled' || job.status === 'skipped') return 0
      return job.progress || 0
    }
  })

  const getHistoryProgressTone = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'completed') return 'success'
      if (job.status === 'failed') return 'error'
      if (job.status === 'cancelled' || job.status === 'skipped') return 'warning'
      return 'info'
    }
  })

  const getTerminalIconName = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'skipped') return 'minus'
      if (job.status === 'cancelled') return 'clock'
      if (job.status === 'completed') return 'check'
      return 'x'
    }
  })

  const getTerminalIconClass = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'skipped') return 'job-card__icon--skipped'
      if (job.status === 'cancelled') return 'job-card__icon--cancelled'
      if (job.status === 'completed') return 'job-card__icon--completed'
      return 'job-card__icon--failed'
    }
  })

  const getDashboardStatusTone = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'running') return 'primary'
      return getStatusTone.value(job)
    }
  })

  const getDashboardIconName = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>) => {
      if (job.status === 'completed') return 'check'
      if (job.status === 'failed') return 'x'
      if (job.status === 'cancelled') return 'clock'
      if (job.status === 'running') return 'loading'
      if (job.status === 'skipped') return 'minus'
      return 'clock'
    }
  })

  const getCardView = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView = {}): JobCardView => {
      const status = job.status || ''
      if (status === 'running' || status === 'queued' || status === 'blocked' || status === 'pending') {
        return {
          badgeLabel: getRunningBadgeLabel.value(job, runtime.status),
          badgeTone: status === 'running' ? 'info' : 'warning',
          iconName: status === 'running' ? 'loading' : 'clock',
          iconClass: status === 'running' ? 'job-card__icon--running' : 'job-card__icon--queued',
        }
      }

      if (status === 'completed') {
        return {
          badgeLabel: getTerminalBadgeLabel.value(job),
          badgeTone: getStatusTone.value(job),
          iconName: getTerminalIconName.value(job),
          iconClass: getTerminalIconClass.value(job),
        }
      }

      return {
        badgeLabel: getTerminalBadgeLabel.value(job),
        badgeTone: getStatusTone.value(job),
        iconName: getTerminalIconName.value(job),
        iconClass: getTerminalIconClass.value(job),
      }
    }
  })

  const getProgressView = computed(() => {
    void i18nVersion.value
    return (
      job: Partial<Job>,
      runtime: JobRuntimeView & { progress?: number; phaseProgress?: number } = {},
    ): JobProgressView => {
      const effective = getEffectiveViewState.value(job, runtime)
      const status = job.status || ''
      const overallValue = Math.max(0, Math.min(100, Number(runtime.progress ?? job.progress ?? 0)))
      const phaseKey = runtime.phaseKey || job.phase_key || ''
      const phaseValue = Math.max(0, Math.min(100, Number(runtime.phaseProgress ?? job.phase_progress ?? 0)))
      const showOverall = status === 'running'
      const showPhase = status === 'running' && !!phaseKey && phaseKey !== 'finalize' && phaseValue >= 0 && phaseValue <= 100
      const phaseLabel = status === 'running'
        ? (effective.phaseLabel || '')
        : ''
      const detailLine = getDisplayPhaseLine.value(job, runtime)

      return {
        mode: showOverall ? 'running' : 'hidden',
        phaseLabel,
        detailLine,
        showOverall,
        overallValue,
        overallText: `${overallValue}%`,
        showPhase,
        phaseValue,
        phaseText: `${phaseValue}%`,
      }
    }
  })

  const getChainProgressView = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView & { progress?: number; phaseProgress?: number } = {}): JobChainProgressView => {
      const status = job.status || ''
      const progress = Math.max(0, Math.min(100, Number(runtime.progress ?? job.progress ?? 0)))
      const phaseProgress = Math.max(0, Math.min(100, Number(runtime.phaseProgress ?? job.phase_progress ?? 0)))
      if (status === 'running' && phaseProgress > 0) return { progress, text: `${progress}% · ${phaseProgress}%` }
      if (status === 'running') return { progress, text: progress > 0 ? `${progress}%` : '' }
      return { progress, text: '' }
    }
  })

  const getDisplayState = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView & { progress?: number; phaseProgress?: number } = {}): JobDisplayState => {
      const progressView = getProgressView.value(job, runtime)
      const status = job.status || ''
      const phaseLine = getDisplayPhaseLine.value(job, runtime)
      const errorLine = (job as Job).error_message || ''
      const rawDetailLine = runtime.detail || job.detail || ''
      let detailLine = ''
      let metaLine = ''

      if (status === 'failed') {
        detailLine = errorLine || phaseLine
        metaLine = detailLine !== phaseLine ? phaseLine : ''
      } else if (status === 'running' || status === 'queued' || status === 'blocked' || status === 'pending') {
        detailLine = progressView.detailLine || phaseLine
      } else if (status === 'cancelled' || status === 'skipped') {
        detailLine = rawDetailLine || phaseLine
      }

      return {
        phaseLine,
        detailLine,
        summaryLine: detailLine,
        metaLine,
      }
    }
  })

  const getDescriptionView = computed(() => {
    void i18nVersion.value
    return (job: Partial<Job>, runtime: JobRuntimeView = {}): JobDescriptionView => {
      const displayState = getDisplayState.value(job, runtime)
      return {
        summaryLine: displayState.summaryLine,
        metaLine: displayState.metaLine,
      }
    }
  })

  return {
    runningLabel,
    connectingLabel,
    queuedLabel,
    blockedLabel,
    completedLabel,
    failedLabel,
    cancelledLabel,
    skippedLabel,
    fallbackStatusLabel,
    phaseGroupLabel,
    getJobTypeLabel,
    getJobTypeLabelForJob,
    getJobTypeChipClass,
    getWhisperStrategyLabel,
    getWhisperStrategyHint,
    getJobHeaderMetaTokens,
    getDashboardJobMetaTokens,
    getDashboardJobChips,
    formatDashboardRelativeTime,
    formatJobDateTime,
    getWhisperStrategyChipClass,
    getJobDisplayName,
    getChainMembers,
    getChainStepLabel,
    getChainRoleLabel,
    getChainWaitingLabel,
    getChainPositionLabel,
    getChainStatusSummary,
    getChainFlowLabel,
    getJobChainHint,
    getJobPhaseLine,
    getActivityDetailLine,
    getEffectiveViewState,
    getDisplayPhaseLine,
    shouldShowPhaseProgress,
    getRunningBadgeLabel,
    getStatusTone,
    getTerminalBadgeVariant,
    getTerminalBadgeLabel,
    getHistoryProgressValue,
    getHistoryProgressTone,
    getTerminalIconName,
    getTerminalIconClass,
    getDashboardStatusTone,
    getDashboardIconName,
    getCardView,
    getProgressView,
    getChainProgressView,
    getDescriptionView,
    getDisplayState,
  }
}
