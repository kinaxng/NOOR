import { ref } from 'vue'
import api from '../api'
import { useToast } from './useToast'

export interface Subtitle {
  filename: string
  path: string
  size: number
  ext: string
}

export interface OnlineSubtitle {
  name: string
  url: string
  ext: string
  language: string
  source: string
}

export function useSubtitles() {
  const toast = useToast()

  const subtitles = ref<Subtitle[]>([])
  const onlineSubtitles = ref<OnlineSubtitle[]>([])
  const loadingSubtitles = ref(false)
  const searchingOnline = ref(false)
  const subtitleError = ref<string | null>(null)
  const videoCodeForSearch = ref('')
  const subtitlePreviewContent = ref('')
  const subtitlePreviewFilename = ref('')
  const loadingSubtitlePreview = ref(false)

  async function fetchSubtitles(videoPath: string) {
    loadingSubtitles.value = true
    subtitleError.value = null
    try {
      const resp = await api.get('/subtitles', {
        params: { video_path: videoPath }
      })
      subtitles.value = resp.data.subtitles || []
    } catch (e: any) {
      console.error('Failed to load subtitles:', e)
      subtitleError.value = e?.response?.data?.detail || '加载字幕列表失败'
    } finally {
      loadingSubtitles.value = false
    }
  }

  async function searchOnlineSubtitles(videoPath: string) {
    searchingOnline.value = true
    onlineSubtitles.value = []
    subtitleError.value = null

    try {
      const resp = await api.get('/subtitles/search', {
        params: { video_path: videoPath }
      })
      onlineSubtitles.value = resp.data.results || []
      videoCodeForSearch.value = resp.data.video_name || ''
      if (onlineSubtitles.value.length === 0) {
        subtitleError.value = '未找到字幕'
      }
    } catch (e: any) {
      console.error('Failed to search subtitles:', e)
      subtitleError.value = e?.response?.data?.detail || '搜索字幕失败'
    } finally {
      searchingOnline.value = false
    }
  }

  async function downloadOnlineSubtitle(url: string, videoPath: string) {
    try {
      const resp = await api.get('/subtitles/download', {
        params: { url, video_path: videoPath }
      })
      toast.success(`字幕 "${resp.data.filename}" 已下载到: ${resp.data.path}`)
      await fetchSubtitles(videoPath)
      return true
    } catch (e: any) {
      console.error('Failed to download subtitle:', e)
      toast.error(e?.response?.data?.detail || '下载失败')
      return false
    }
  }

  async function previewOnlineSubtitle(url: string, filename: string) {
    loadingSubtitlePreview.value = true
    subtitlePreviewContent.value = ''
    subtitlePreviewFilename.value = filename

    try {
      const resp = await api.get('/subtitles/fetch', {
        params: { url }
      })
      subtitlePreviewContent.value = resp.data.content
    } catch (e: any) {
      console.error('Failed to preview subtitle:', e)
      subtitlePreviewContent.value = '加载字幕失败，请检查网络或尝试下载后查看'
    } finally {
      loadingSubtitlePreview.value = false
    }
  }

  async function previewLocalSubtitle(path: string, filename: string) {
    loadingSubtitlePreview.value = true
    subtitlePreviewContent.value = ''
    subtitlePreviewFilename.value = filename

    try {
      const resp = await api.get('/subtitles/content', {
        params: { path }
      })
      subtitlePreviewContent.value = resp.data.content
    } catch (e: any) {
      console.error('Failed to load subtitle:', e)
      subtitlePreviewContent.value = '加载字幕失败'
    } finally {
      loadingSubtitlePreview.value = false
    }
  }

  async function deleteSubtitle(path: string, filename: string) {
    if (!confirm(`确定删除字幕文件 "${filename}" 吗？`)) return false

    try {
      await api.delete('/subtitles', {
        params: { path }
      })
      subtitles.value = subtitles.value.filter(s => s.path !== path)
      toast.success('字幕文件已删除')
      return true
    } catch (e: any) {
      console.error('Failed to delete subtitle:', e)
      toast.error(e?.response?.data?.detail || '删除失败')
      return false
    }
  }

  function closeSubtitlePreview() {
    subtitlePreviewContent.value = ''
    subtitlePreviewFilename.value = ''
    loadingSubtitlePreview.value = false
  }

  function clearSubtitles() {
    subtitles.value = []
    onlineSubtitles.value = []
    videoCodeForSearch.value = ''
    subtitleError.value = null
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return {
    subtitles,
    onlineSubtitles,
    loadingSubtitles,
    searchingOnline,
    subtitleError,
    videoCodeForSearch,
    subtitlePreviewContent,
    subtitlePreviewFilename,
    loadingSubtitlePreview,
    fetchSubtitles,
    searchOnlineSubtitles,
    downloadOnlineSubtitle,
    previewOnlineSubtitle,
    previewLocalSubtitle,
    deleteSubtitle,
    closeSubtitlePreview,
    clearSubtitles,
    formatFileSize,
  }
}
