# Source Generated with Decompyle++
# File: job_phases.pyc (Python 3.13)

from __future__ import annotations
from typing import Any
PHASE_PREPARE = 'prepare'
PHASE_ANALYZE = 'analyze'
PHASE_TRANSCRIBE = 'transcribe'
PHASE_RETRY = 'retry'
PHASE_ALIGN = 'align'
PHASE_TRANSLATE = 'translate'
PHASE_PROCESS = 'process'
PHASE_ENCODE = 'encode'
PHASE_OUTPUT = 'output'
PHASE_LABELS = {
    PHASE_OUTPUT: '整理输出',
    PHASE_ENCODE: '编码输出文件',
    PHASE_PROCESS: '处理中',
    PHASE_TRANSLATE: '字幕翻译',
    PHASE_ALIGN: '对齐时间轴',
    PHASE_RETRY: '补救识别',
    PHASE_TRANSCRIBE: '生成字幕',
    PHASE_ANALYZE: '分析内容',
    PHASE_PREPARE: '准备任务' }
TERMINAL_STATUS_LABELS = {
    'completed': '已完成',
    'failed': '失败',
    'cancelled': '已取消',
    'skipped': '已跳过' }
TERMINAL_STATUS_DETAILS = {
    'lada': {
        'completed': '视频修复完成',
        'failed': '视频修复失败',
        'cancelled': '视频修复已取消',
        'skipped': '视频修复已跳过' },
    'lada_restore': {
        'completed': '视频修复完成',
        'failed': '视频修复失败',
        'cancelled': '视频修复已取消',
        'skipped': '视频修复已跳过' },
    'whisper': {
        'completed': '字幕生成完成',
        'failed': '字幕生成失败',
        'cancelled': '字幕生成已取消',
        'skipped': '字幕生成已跳过' },
    'whisper_transcribe': {
        'completed': '字幕生成完成',
        'failed': '字幕生成失败',
        'cancelled': '字幕生成已取消',
        'skipped': '字幕生成已跳过' },
    'translate-srt': {
        'completed': '字幕翻译完成',
        'failed': '字幕翻译失败',
        'cancelled': '字幕翻译已取消',
        'skipped': '字幕翻译已跳过' } }
FOLLOWUP_STATUS_DETAILS = {
    'blocked': '等待主任务完成后自动开始',
    'queued': '主任务已完成，准备开始后续任务' }
FOLLOWUP_DETAIL_VALUES = None(FOLLOWUP_STATUS_DETAILS.values())
JOB_TYPE_PHASE_DEFAULTS: 'dict[str, dict[str, Any]]' = {
    'lada': {
        'phase_key': PHASE_PREPARE,
        'phase_label': PHASE_LABELS[PHASE_PREPARE] },
    'lada_restore': {
        'phase_key': PHASE_PREPARE,
        'phase_label': PHASE_LABELS[PHASE_PREPARE] },
    'whisper': {
        'phase_key': PHASE_PREPARE,
        'phase_label': PHASE_LABELS[PHASE_PREPARE] },
    'whisper_transcribe': {
        'phase_key': PHASE_PREPARE,
        'phase_label': PHASE_LABELS[PHASE_PREPARE] },
    'translate-srt': {
        'phase_key': PHASE_TRANSLATE,
        'phase_label': PHASE_LABELS[PHASE_TRANSLATE] } }
# WARNING: Decompyle incomplete
