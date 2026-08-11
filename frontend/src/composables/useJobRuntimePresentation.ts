
import { computed, type ComputedRef, type Ref } from 'vue'
import type { Job, RecommendedDiagnostics } from '../api/types'
import type { JobCardViewModel } from '../components/noor/JobCard.vue'
import type { JobChainMemberViewModel } from '../components/noor/JobChainPanel.vue'
import { useI18n } from './useI18n'
import { useJobPresentation } from './useJobPresentation'
import type { JobRuntimeStatus } from './useJobEventState'

export type JobRuntimeSnapshot = {
  status: string
  progress: number
  phaseKey?: string
  phaseGroup?: string
  phaseLabel?: string
  detail?: string
  phaseProgress?: number
}

export type JobRuntimeViewState = {
  status?: string
  phaseKey?: string
  phaseGroup?: string
  phaseLabel?: string
  detail?: string
}

export type JobTabKey = 'running' | 'completed' | 'failed'

type UseJobRuntimePresentationOptions = {
  allJobs: () => Job[]
  jobStatuses: Ref<Record<string, JobRuntimeStatus>>
  selectedJobId: Ref<string | null>
  flashJobId: Ref<string | null>
  activeTab: Ref<JobTabKey>
  currentTabJobs: ComputedRef<Job[]>
  selectedJob: ComputedRef<Job | null>
  selectedJobChain: ComputedRef<Job[]>
  cancelLabel: ComputedRef<string>
}

export function useJobRuntimePresentation(options: UseJobRuntimePresentationOptions) {
  const {
    allJobs,
    jobStatuses,
    selectedJobId,
    flashJobId,
    activeTab,
    currentTabJobs,
    selectedJob,
    selectedJobChain,
    cancelLabel,
  } = options

  const { t } = useI18n()
  const {
    getChainStepLabel,
    getChainRoleLabel,
    getChainWaitingLabel,
    getChainPositionLabel,
    getChainStatusSummary,
    getChainFlowLabel,
    getJobChainHint,
    getStatusTone,
    getEffectiveViewState,
    getDisplayPhaseLine,
    getCardView,
    getProgressView,
    getChainProgressView,
    getDescriptionView,
    getDisplayState,
    getJobTypeLabel,
    getJobTypeChipClass,
    getJobDisplayName,
    fallbackStatusLabel,
  } = useJobPresentation(allJobs)

  const showJobTypeChip = computed(() => activeTab.value === 'running')
  const showJobProgressPanel = computed(() => activeTab.value === 'running')
  const showJobSummaryLine = computed(() => activeTab.value === 'running' || activeTab.value === 'failed')
  const showJobMetaLine = computed(() => activeTab.value === 'failed')
  const showJobCompletedAt = computed(() => activeTab.value === 'completed' || activeTab.value === 'failed')

  function getJobById(jobId: string) {
    return allJobs().find(job => job.id === jobId) || null
  }

  function getJobRuntimeSnapshot(job: Job): JobRuntimeSnapshot {
    const runtime = jobStatuses.value[job.id]
    return {
      status: runtime?.status ?? '',
      progress: runtime?.progress ?? job.progress ?? 0,
      phaseKey: runtime?.phaseKey ?? job.phase_key,
      phaseGroup: runtime?.phaseGroup ?? job.phase_group,
      phaseLabel: runtime?.phaseLabel ?? job.phase_label,
      detail: runtime?.detail ?? job.detail,
      phaseProgress: runtime?.phaseProgress ?? job.phase_progress ?? 0,
    }
  }

  function getJobRuntimeBundle(job: Job) {
    const snapshot = getJobRuntimeSnapshot(job)
    return {
      snapshot,
      view: {
        status: snapshot.status,
        phaseKey: snapshot.phaseKey,
        phaseGroup: snapshot.phaseGroup,
        phaseLabel: snapshot.phaseLabel,
        detail: snapshot.detail,
      } satisfies JobRuntimeViewState,
    }
  }

  function getJobDisplayBundle(job: Job) {
    const runtimeBundle = getJobRuntimeBundle(job)
    const progressView = getProgressView.value(job, {
      progress: runtimeBundle.snapshot.progress,
      phaseKey: runtimeBundle.snapshot.phaseKey,
      phaseLabel: runtimeBundle.snapshot.phaseLabel,
      phaseProgress: runtimeBundle.snapshot.phaseProgress,
      detail: runtimeBundle.snapshot.detail,
    })
    const displayState = getDisplayState.value(job, {
      ...runtimeBundle.view,
      progress: runtimeBundle.snapshot.progress,
      phaseProgress: runtimeBundle.snapshot.phaseProgress,
    })
    return {
      runtime: runtimeBundle.snapshot,
      viewState: runtimeBundle.view,
      cardView: getCardView.value(job, runtimeBundle.view),
      progressView,
      displayState,
      descriptionView: {
        ...getDescriptionView.value(job, runtimeBundle.view),
        summaryLine: displayState.summaryLine,
        metaLine: displayState.metaLine,
      },
    }
  }

  function getJobRuntimeViewState(job: Job): JobRuntimeViewState {
    return getJobRuntimeBundle(job).view
  }

  function getJobStatus(jobId: string) {
    const job = getJobById(jobId)
    return job ? getJobRuntimeSnapshot(job).status : ''
  }

  function getChainMemberStatus(member: Job) {
    return getEffectiveViewState.value(member, getJobRuntimeViewState(member)).statusLabel
  }

  function getChainMemberColor(member: Job) {
    return getStatusTone.value(member)
  }

  function getChainMemberPhaseLine(member: Job) {
    return getDisplayPhaseLine.value(member, getJobDisplayBundle(member).viewState)
  }

  function isPrimaryChainJob(job: Job) {
    return getChainRoleLabel.value(job) === t('jobs.chain.rolePrimary')
  }

  function isFollowupChainJob(job: Job) {
    return getChainRoleLabel.value(job) === t('jobs.chain.roleFollowup')
  }

  function getJobCardView(job: Job) {
    return getJobDisplayBundle(job).cardView
  }

  function getJobProgressView(job: Job) {
    return getJobDisplayBundle(job).progressView
  }

  function getJobDescriptionView(job: Job) {
    return getJobDisplayBundle(job).descriptionView
  }

  function getJobCompletedAt(job: Job) {
    if (!job.completed_at) return ''
    return new Date(job.completed_at).toLocaleString()
  }

  function getDiagnosticSummary(job: Job) {
    const diagnostics = job.result_metadata?.recommended_diagnostics as RecommendedDiagnostics | undefined
    if (!diagnostics || (job.job_type !== 'whisper' && job.job_type !== 'whisper_transcribe')) return [] as string[]

    const summary = [
      diagnostics.qwen_retry_segments > 0 ? `${t('jobs.diagnosticsFallback')} ${diagnostics.qwen_retry_segments}` : '',
      diagnostics.stepdown_segments > 0 ? `${t('jobs.diagnosticsStepdown')} ${diagnostics.stepdown_segments}` : '',
      diagnostics.cleanup?.noise_only_segments ? `${t('jobs.diagnosticsNoise')} ${diagnostics.cleanup.noise_only_segments}` : '',
    ].filter(Boolean)

    return summary
  }

  function getJobCardModel(job: Job): JobCardViewModel {
    const cardView = getJobCardView(job)
    const progressView = getJobProgressView(job)
    const descriptionView = getJobDescriptionView(job)
    const waitingLabel = getChainWaitingLabel.value(job)

    return {
      ...cardView,
      selected: selectedJobId.value === job.id,
      flashing: flashJobId.value === job.id,
      showTypeChip: showJobTypeChip.value,
      showProgressPanel: showJobProgressPanel.value,
      showSummaryLine: showJobSummaryLine.value,
      showMetaLine: showJobMetaLine.value,
      showCompletedAt: showJobCompletedAt.value,
      typeChipLabel: getJobTypeLabel.value(job.job_type),
      typeChipClass: getJobTypeChipClass.value(job.job_type),
      phaseLabel: progressView.phaseLabel,
      chainLine: job.chain_id ? getChainFlowLabel.value(job) : '',
      showChainLine: activeTab.value !== 'running' && !!job.chain_id,
      summaryLine: descriptionView.summaryLine,
      metaLine: descriptionView.metaLine,
      completedAt: getJobCompletedAt(job),
      canCancel: job.status === 'running' || job.status === 'queued' || job.status === 'blocked' || job.status === 'pending',
      overallLabel: t('jobs.progress.overall'),
      phaseLabelText: t('jobs.progress.phase'),
      cancelLabel: cancelLabel.value,
      overallProgressValue: progressView.overallValue,
      overallProgressText: progressView.showOverall ? progressView.overallText : '',
      showPhaseProgress: progressView.showPhase,
      phaseProgressValue: progressView.phaseValue,
      phaseProgressText: progressView.phaseText,
      chainStepLabel: job.chain_id ? getChainStepLabel.value(job) : '',
      chainRoleLabel: getChainRoleLabel.value(job),
      chainWaitingLabel: waitingLabel,
      chainHint: waitingLabel ? '' : getJobChainHint.value(job),
      isPrimaryChainJob: isPrimaryChainJob(job),
      isFollowupChainJob: isFollowupChainJob(job),
      diagnosticSummary: getDiagnosticSummary(job),
    }
  }

  const currentTabJobCards = computed(() => currentTabJobs.value.map(job => ({
    job,
    view: getJobCardModel(job),
  })))

  const selectedJobStatusLabel = computed(() => {
    if (!selectedJob.value) return ''
    return getJobStatus(selectedJob.value.id) || fallbackStatusLabel.value(selectedJob.value.status)
  })

  const selectedJobActivityLine = computed(() => {
    if (!selectedJob.value) return ''
    return getJobDisplayBundle(selectedJob.value).descriptionView.summaryLine
  })

  const selectedJobChainFlow = computed(() => selectedJob.value ? getChainFlowLabel.value(selectedJob.value) : '')
  const selectedJobChainSummary = computed(() => selectedJob.value ? getChainStatusSummary.value(selectedJob.value) : '')

  function getChainMemberModel(member: Job): JobChainMemberViewModel {
    return {
      id: member.id,
      active: selectedJobId.value === member.id,
      positionLabel: getChainPositionLabel.value(member),
      stepLabel: getChainStepLabel.value(member),
      roleLabel: getChainRoleLabel.value(member),
      name: getJobDisplayName.value(member),
      phaseLine: getChainWaitingLabel.value(member) || getChainMemberPhaseLine(member),
      progressText: getChainProgressView.value(member, getJobDisplayBundle(member).runtime).text,
      statusLabel: getChainMemberStatus(member),
      statusTone: getChainMemberColor(member),
    }
  }

  const selectedJobChainModels = computed(() => selectedJobChain.value.map(getChainMemberModel))

  return {
    getJobById,
    getJobStatus,
    getJobRuntimeSnapshot,
    getJobRuntimeBundle,
    getJobDisplayBundle,
    currentTabJobCards,
    selectedJobStatusLabel,
    selectedJobActivityLine,
    selectedJobChainFlow,
    selectedJobChainSummary,
    selectedJobChainModels,
  }
}

