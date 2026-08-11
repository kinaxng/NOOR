import { useRouter } from 'vue-router'

export function useJobNavigation() {
  const router = useRouter()

  async function openJobsFocus(target: { jobId?: string; chainId?: string }) {
    const query: Record<string, string> = {}
    if (target.jobId) query.job = target.jobId
    if (target.chainId) query.chain = target.chainId
    await router.push({ name: 'jobs', query })
  }

  return { openJobsFocus }
}
