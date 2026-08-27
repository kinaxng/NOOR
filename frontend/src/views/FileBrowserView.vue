<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import api from '../api'
import BaseIcon from '../components/noor/BaseIcon.vue'
import { useConfirm } from '../composables/useConfirm'
import { useToast } from '../composables/useToast'

type Side = 'left' | 'right'
type Entry = {
  name: string
  path: string
  is_dir: boolean
  is_symlink: boolean
  size: number
  modified_at: string
  mode: string
  owner: string
  group: string
  readable: boolean
  writable: boolean
  executable: boolean
  inode: number
  link_count: number
  extension: string
}
type Pane = {
  side: 'source' | 'hardlink'
  path: string
  parent: string | null
  entries: Entry[]
  selected: Set<string>
  loading: boolean
  permissions: Record<string, any>
  roots: { source: string[]; hardlink: string[] }
}

const toast = useToast()
const { confirm } = useConfirm()
const busy = ref(false)
const showHidden = ref(false)
const sortBy = ref<'name' | 'size' | 'modified'>('name')
const panes = reactive<Record<Side, Pane>>({
  left: { side: 'source', path: '', parent: null, entries: [], selected: new Set(), loading: false, permissions: {}, roots: { source: [], hardlink: [] } },
  right: { side: 'hardlink', path: '', parent: null, entries: [], selected: new Set(), loading: false, permissions: {}, roots: { source: [], hardlink: [] } },
})

function errorMessage(error: any) {
  return error?.response?.data?.detail || error?.message || '文件操作失败'
}

function formatSize(value: number) {
  if (!value) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1 }
  return `${size >= 10 || index === 0 ? size.toFixed(0) : size.toFixed(1)} ${units[index]}`
}

function formatDate(value: string) {
  return value ? new Date(value).toLocaleString() : '—'
}

function visibleEntries(side: Side) {
  const entries = panes[side].entries.filter(item => showHidden.value || !item.name.startsWith('.'))
  return [...entries].sort((a, b) => {
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    if (sortBy.value === 'size') return a.size - b.size || a.name.localeCompare(b.name)
    if (sortBy.value === 'modified') return b.modified_at.localeCompare(a.modified_at) || a.name.localeCompare(b.name)
    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' })
  })
}

const leftEntries = computed(() => visibleEntries('left'))
const rightEntries = computed(() => visibleEntries('right'))

async function loadPane(side: Side, path = '') {
  const pane = panes[side]
  pane.loading = true
  try {
    const { data } = await api.get('/media-library/files/browser', { params: { path, side: pane.side } })
    pane.path = data.path
    pane.parent = data.parent
    pane.entries = data.entries || []
    pane.permissions = data.permissions || {}
    pane.roots = data.roots || { source: [], hardlink: [] }
    pane.selected.clear()
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    pane.loading = false
  }
}

function toggleSelection(side: Side, path: string, event: MouseEvent) {
  const selected = panes[side].selected
  if (!event.ctrlKey && !event.metaKey) selected.clear()
  if (selected.has(path)) selected.delete(path)
  else selected.add(path)
}

function openEntry(side: Side, entry: Entry) {
  if (entry.is_dir) loadPane(side, entry.path)
  else window.open(`/api/media-library/files/browser/download?path=${encodeURIComponent(entry.path)}`, '_blank')
}

async function operate(action: string, side: Side, extra: Record<string, any> = {}) {
  const pane = panes[side]
  const paths = [...pane.selected]
  busy.value = true
  try {
    await api.post('/media-library/files/browser/operation', { action, paths, ...extra })
    await Promise.all([loadPane('left', panes.left.path), loadPane('right', panes.right.path)])
    toast.success(action === 'copy' ? '复制完成' : action === 'move' ? '移动完成' : action === 'delete' ? '删除完成' : '操作完成')
  } catch (error) {
    toast.error(errorMessage(error))
  } finally {
    busy.value = false
  }
}

function transfer(action: 'copy' | 'move', from: Side) {
  const to: Side = from === 'left' ? 'right' : 'left'
  if (!panes[from].selected.size) return toast.warning('请先选择文件或文件夹')
  operate(action, from, { target_dir: panes[to].path })
}

async function rename(side: Side) {
  const pane = panes[side]
  if (pane.selected.size !== 1) return toast.warning('请选择一个文件或文件夹')
  const path = [...pane.selected][0]
  const oldName = pane.entries.find(item => item.path === path)?.name || ''
  const newName = window.prompt('输入新名称', oldName)?.trim()
  if (newName && newName !== oldName) await operate('rename', side, { new_name: newName })
}

async function mkdir(side: Side) {
  const name = window.prompt('输入新文件夹名称')?.trim()
  if (name) await operate('mkdir', side, { target_dir: panes[side].path, new_name: name })
}

async function remove(side: Side) {
  const pane = panes[side]
  if (!pane.selected.size) return toast.warning('请选择要删除的文件或文件夹')
  const ok = await confirm({
    title: '删除文件',
    message: `确定永久删除选中的 ${pane.selected.size} 项吗？目录内的内容也会一并删除。`,
    confirmText: '永久删除',
    danger: true,
  })
  if (ok) await operate('delete', side)
}

function rootOptions(side: Side) {
  const roots = panes[side].roots
  return [...roots.source.map(path => ({ path, label: `源 · ${path}` })), ...roots.hardlink.map(path => ({ path, label: `硬链接 · ${path}` }))]
}

onMounted(() => Promise.all([loadPane('left'), loadPane('right')]))
</script>

<template>
  <section class="file-browser">
    <header class="browser-overview-row">
      <div>
        <h1 class="page-title">文件浏览</h1>
        <p class="page-subtitle">双窗格浏览与管理媒体文件，操作范围受媒体扫描目录保护。</p>
      </div>
      <div class="overview-controls">
        <label><input v-model="showHidden" type="checkbox"> 显示隐藏项</label>
        <select v-model="sortBy" class="sort-select" aria-label="排序">
          <option value="name">按名称</option><option value="size">按大小</option><option value="modified">按修改时间</option>
        </select>
      </div>
    </header>

    <div class="dual-pane">
      <article v-for="side in (['left', 'right'] as Side[])" :key="side" class="browser-pane">
        <header class="pane-header">
          <div class="pane-heading">
            <span class="pane-role">{{ side === 'left' ? '源文件' : '硬链接' }}</span>
            <span class="permission-chip" :class="{ writable: panes[side].permissions.writable }">{{ panes[side].permissions.mode || '---------' }}</span>
            <span class="owner-chip">{{ panes[side].permissions.owner || '—' }}:{{ panes[side].permissions.group || '—' }}</span>
          </div>
          <div class="pane-nav">
            <button class="icon-button" :disabled="!panes[side].parent" title="上级目录" @click="panes[side].parent && loadPane(side, panes[side].parent)"><BaseIcon name="arrowUp" /></button>
            <select class="root-select" :value="panes[side].path" title="媒体根目录" @change="loadPane(side, ($event.target as HTMLSelectElement).value)">
              <option :value="panes[side].path">{{ panes[side].path }}</option>
              <option v-for="root in rootOptions(side)" :key="root.path" :value="root.path">{{ root.label }}</option>
            </select>
            <button class="icon-button" title="刷新" @click="loadPane(side, panes[side].path)"><BaseIcon name="refresh" /></button>
          </div>
          <div class="pane-actions">
            <button @click="mkdir(side)"><BaseIcon name="plus" /> 新建</button>
            <button :disabled="panes[side].selected.size !== 1" @click="rename(side)"><BaseIcon name="edit" /> 重命名</button>
            <button :disabled="!panes[side].selected.size" @click="transfer('copy', side)"><BaseIcon name="copy" /> 复制到{{ side === 'left' ? '右侧' : '左侧' }}</button>
            <button :disabled="!panes[side].selected.size" @click="transfer('move', side)"><BaseIcon name="chevronRight" /> 移动到{{ side === 'left' ? '右侧' : '左侧' }}</button>
            <button class="danger" :disabled="!panes[side].selected.size" @click="remove(side)"><BaseIcon name="trash" /> 删除</button>
          </div>
        </header>

        <div class="file-table" :class="{ loading: panes[side].loading || busy }">
          <div class="file-row table-head"><span>名称</span><span>大小</span><span>修改时间</span><span>权限</span></div>
          <button
            v-for="entry in side === 'left' ? leftEntries : rightEntries"
            :key="entry.path"
            class="file-row"
            :class="{ selected: panes[side].selected.has(entry.path) }"
            @click="toggleSelection(side, entry.path, $event)"
            @dblclick="openEntry(side, entry)"
          >
            <span class="file-name"><BaseIcon :name="entry.is_dir ? 'folder' : 'file'" /><span><strong>{{ entry.name }}</strong><small v-if="entry.is_symlink">符号链接</small><small v-else-if="entry.link_count > 1">{{ entry.link_count }} links · inode {{ entry.inode }}</small></span></span>
            <span class="file-size">{{ entry.is_dir ? '文件夹' : formatSize(entry.size) }}</span>
            <span>{{ formatDate(entry.modified_at) }}</span>
            <span class="mode" :title="`${entry.owner}:${entry.group}`">{{ entry.mode }}</span>
          </button>
          <div v-if="!panes[side].loading && !(side === 'left' ? leftEntries : rightEntries).length" class="empty-pane"><BaseIcon name="folderOpen" />此目录为空</div>
          <div v-if="panes[side].loading" class="loading-pane"><BaseIcon name="loading" />正在读取目录</div>
        </div>
        <footer class="pane-status"><span>{{ (side === 'left' ? leftEntries : rightEntries).length }} 项 · 已选 {{ panes[side].selected.size }}</span><span>{{ panes[side].permissions.writable ? '可写' : '只读' }}</span></footer>
      </article>
    </div>
  </section>
</template>

<style scoped>
.file-browser{display:flex;flex-direction:column;gap:1rem;min-width:0}.browser-overview-row{display:flex;align-items:flex-end;justify-content:space-between;gap:1rem}.page-title{margin:0;font:600 1.5rem/1.2 var(--font-display);letter-spacing:-.02em}.page-subtitle{margin:.35rem 0 0;color:var(--text-muted);font-size:.875rem}.overview-controls{display:flex;align-items:center;gap:.75rem;color:var(--text-secondary);font-size:.8125rem}.sort-select,.root-select{color:var(--text-primary);background:rgba(255,255,255,.045);border:1px solid var(--border-subtle);border-radius:10px;padding:.48rem .65rem}.dual-pane{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:.75rem;min-height:610px}.browser-pane{display:flex;flex-direction:column;min-width:0;overflow:hidden;background:rgba(12,17,28,.72);border:1px solid var(--border-subtle);border-radius:var(--radius-xl);box-shadow:0 18px 50px rgba(0,0,0,.16)}.pane-header{padding:.85rem;border-bottom:1px solid var(--border-subtle);display:flex;flex-direction:column;gap:.7rem}.pane-heading,.pane-nav,.pane-actions{display:flex;align-items:center;gap:.45rem}.pane-role{font:600 .9375rem/1 var(--font-display);margin-right:auto}.permission-chip,.owner-chip{font:500 .6875rem/1 var(--font-mono);padding:.3rem .48rem;border:1px solid rgba(255,255,255,.08);border-radius:999px;color:var(--text-muted)}.permission-chip.writable{color:#69dca2;background:rgba(45,190,120,.08)}.root-select{flex:1;min-width:0;font-family:var(--font-mono);font-size:.75rem}.icon-button,.pane-actions button{display:inline-flex;align-items:center;gap:.35rem;border:1px solid var(--border-subtle);color:var(--text-secondary);background:rgba(255,255,255,.035);border-radius:9px;cursor:pointer}.icon-button{width:32px;height:32px;justify-content:center}.icon-button :deep(svg),.pane-actions :deep(svg){width:15px;height:15px}.pane-actions{overflow-x:auto;padding-bottom:1px}.pane-actions button{padding:.42rem .58rem;white-space:nowrap;font:500 .75rem/1 var(--font-display)}button:hover:not(:disabled){color:var(--text-primary);border-color:rgba(0,117,255,.42);background:rgba(0,117,255,.08)}button:disabled{opacity:.35;cursor:not-allowed}.pane-actions .danger:hover:not(:disabled){color:#ff8f9a;border-color:rgba(255,75,90,.4);background:rgba(255,75,90,.08)}.file-table{position:relative;flex:1;min-height:0;overflow:auto}.file-row{width:100%;display:grid;grid-template-columns:minmax(180px,1fr) 82px 132px 84px;align-items:center;gap:.5rem;padding:.58rem .75rem;color:var(--text-secondary);background:transparent;border:0;border-bottom:1px solid rgba(255,255,255,.035);text-align:left;font:400 .75rem/1.25 var(--font-display);cursor:default}.file-row:not(.table-head):hover{background:rgba(255,255,255,.035)}.file-row.selected{background:rgba(0,117,255,.14);box-shadow:inset 2px 0 #0075ff}.table-head{position:sticky;top:0;z-index:2;color:var(--text-muted);background:rgba(12,17,28,.96);font-size:.6875rem;text-transform:uppercase;letter-spacing:.05em}.file-name{display:flex;align-items:center;gap:.55rem;min-width:0}.file-name :deep(svg){width:17px;height:17px;color:#6ea9ff;flex:none}.file-name>span{display:flex;flex-direction:column;min-width:0}.file-name strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);font-weight:500}.file-name small{color:var(--text-muted);font:400 .625rem/1.2 var(--font-mono)}.file-size{font-family:var(--font-mono);font-size:.6875rem}.mode{font-family:var(--font-mono);font-size:.6875rem}.empty-pane,.loading-pane{height:100%;min-height:300px;display:flex;align-items:center;justify-content:center;gap:.6rem;color:var(--text-muted);font-size:.8125rem}.empty-pane :deep(svg),.loading-pane :deep(svg){width:22px;height:22px}.pane-status{display:flex;justify-content:space-between;padding:.55rem .8rem;border-top:1px solid var(--border-subtle);color:var(--text-muted);font-size:.6875rem}.loading{opacity:.62;pointer-events:none}@media(max-width:1100px){.dual-pane{grid-template-columns:1fr;min-height:0}.browser-pane{min-height:520px}}@media(max-width:720px){.browser-overview-row{align-items:flex-start;flex-direction:column}.file-row{grid-template-columns:minmax(150px,1fr) 70px}.file-row>span:nth-child(3),.file-row>span:nth-child(4){display:none}}
</style>
