from __future__ import annotations
import re
from dataclasses import dataclass
from app.tasks.job_phases import PHASE_LABELS, PHASE_NORMALIZATION, get_phase_label, normalize_phase_key
@dataclass
class ProgressPhase: key:str;label:str;start_pct:int;end_pct:int;description:str=''
PHASES={'prepare':ProgressPhase('prepare','准备任务',0,3,'读取配置和准备运行环境'),'extract_audio':ProgressPhase('extract_audio','提取音频',3,10,'从视频提取音频流'),'segment':ProgressPhase('segment','音频分段',10,20,'场景检测与片段准备'),'transcribe_primary':ProgressPhase('transcribe_primary','主转写',20,52,'Anime-Whisper 主转写'),'retry':ProgressPhase('retry','补救识别',52,68,'Qwen3-ASR 对污染段补救识别'),'align':ProgressPhase('align','Qwen3 对齐',68,85,'Qwen3 ForcedAligner 对齐时间轴'),'postprocess':ProgressPhase('postprocess','后处理',85,95,'日语后处理与清洗'),'write_output':ProgressPhase('write_output','写出字幕',95,100,'输出字幕文件')}
WHISPER_PROGRESS_PHASE_ORDER=tuple(PHASES)
@dataclass
class ProgressUpdate: phase_key:str;phase_label:str;phase_progress:float;overall_progress:int;detail:str;line:str=''
class AsyncProgressReporter:
 PHASE_PATTERNS=[('开始 Whisper 字幕生成|Whisper 架构','prepare'),('音频提取|extract','extract_audio'),('场景检测|检测到\\s*\\d+\\s*个场景段落|准备段落|Framer:','segment'),('链路段落|Anime 转写|Pass 1|Anime-Whisper','transcribe_primary'),('Qwen3 ForcedAligner|Qwen3 对齐|Anime\\+Qwen3 链路完成|对齐中','align'),('补救识别|Qwen3-ASR 二次识别|fallback','retry'),('日语后处理|后处理策略|recommended-cleanup|后处理完成|hardening','postprocess'),('生成 SRT|SRT 已保存|字幕已保存|原始字幕已保存','write_output')]
 def __init__(self,job_id:str,event_queue,audio_duration:float=0.0):self.job_id=job_id;self.event_queue=event_queue;self.audio_duration=audio_duration;self.current_phase_key='prepare'
 def _update_phase(self,line:str)->None:
  for pattern,key in self.PHASE_PATTERNS:
   if re.search(pattern,line,re.I):self.current_phase_key=key;return
 def parse_line(self,line:str)->ProgressUpdate|None:self._update_phase(line);return self._build_update(line)
 def _build_update(self,line:str)->ProgressUpdate|None:
  phase=PHASES.get(self.current_phase_key)
  if not phase:return None
  progress=self._infer_phase_progress(phase.key,line);overall=min(100,max(phase.start_pct,int(phase.start_pct+(phase.end_pct-phase.start_pct)*progress)))
  if phase.key=='write_output' and progress>=1:overall=100
  return ProgressUpdate(phase_key=normalize_phase_key(phase.key) or phase.key,phase_label=get_phase_label(phase.key,phase.label) or phase.label,phase_progress=progress,overall_progress=overall,detail=self._infer_detail(phase.key,line,progress),line=line)
 def _infer_phase_progress(self,phase_key:str,line:str)->float:
  if phase_key in {'retry','align','segment','transcribe_primary'}:
   m=re.search(r'(\\d+)\\s*/\\s*(\\d+)',line)
   if m:return min(1.0,max(0.0,int(m.group(1))/max(1,int(m.group(2)))))
  lower=line.lower()
  if phase_key=='write_output' and re.search(r'已保存|字幕已保存|SRT 已保存',line):return 1.0
  if phase_key=='postprocess' and '后处理完成' in line:return 1.0
  if phase_key=='extract_audio' and ('失败' in line or '音频' in lower or 'extract' in lower):return .5
  return 0.0
 def _infer_detail(self,phase_key:str,line:str,phase_progress:float)->str:
  m=re.search(r'(\\d+)\\s*/\\s*(\\d+)',line)
  if m and phase_key=='segment':return f'已准备 {m.group(1)} / {m.group(2)} 段'
  if m and phase_key=='transcribe_primary':return f'已转写 {m.group(1)} / {m.group(2)} 段'
  if m and phase_key=='retry':return f'已补救 {m.group(1)} / {m.group(2)} 段'
  if m and phase_key=='align':return f'已对齐 {m.group(1)} / {m.group(2)} 段'
  return {'retry':'Qwen3-ASR 处理污染或低信息片段','postprocess':'整理日语片段与格式','write_output':'写出 ja.srt 文件','extract_audio':'提取视频音频流','prepare':'初始化字幕任务'}.get(phase_key, f'{int(phase_progress*100)}%')
