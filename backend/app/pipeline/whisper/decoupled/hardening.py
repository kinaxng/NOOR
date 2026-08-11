from __future__ import annotations
from ..types import SubtitleSegment, TranscriptionResult

def harden_transcription_result(result:TranscriptionResult)->TranscriptionResult:
 segments=[SubtitleSegment(index=seg.index,start_time=float(seg.start_time),end_time=float(seg.end_time),text=(seg.text or '').strip(),words=list(seg.words)) for seg in result.segments if (seg.text or '').strip()]
 if not segments:return result
 segments.sort(key=lambda seg:(seg.start_time,seg.end_time,seg.index))
 _interpolate_invalid_segments(segments,result.duration);_clamp_and_monotonicize(segments,result.duration)
 for idx,seg in enumerate(segments,start=1):seg.index=idx
 metadata=dict(result.metadata);metadata['hardening_applied']=True;metadata.setdefault('chain_name','anime_qwen3_chain');metadata['chain_stage']='hardened'
 return TranscriptionResult(segments=segments,language=result.language,duration=result.duration,source=result.source,metadata=metadata)

def _valid(seg):return seg.end_time>seg.start_time>=0
def _interpolate_invalid_segments(segments:list[SubtitleSegment],total_duration:float)->None:
 valid=[i for i,seg in enumerate(segments) if _valid(seg)]
 if not valid:
  per=max(total_duration/max(len(segments),1),.8);cur=0.0
  for seg in segments:
   seg.start_time=cur;seg.end_time=min(total_duration,cur+per);cur=seg.end_time
  return
 n=len(segments)
 for idx,seg in enumerate(segments):
  if _valid(seg):continue
  previous=next((i for i in range(idx-1,-1,-1) if _valid(segments[i])),None)
  following=next((i for i in range(idx+1,n) if _valid(segments[i])),None)
  start_anchor=segments[previous].end_time if previous is not None else 0.0
  end_anchor=segments[following].start_time if following is not None else total_duration
  span=max(end_anchor-start_anchor,.6)
  seg_count=following-previous-1 if previous is not None and following is not None else 1
  slot=max(span/max(seg_count,1),.6)
  offset=0 if previous is None else idx-previous-1
  seg.start_time=start_anchor+offset*slot;seg.end_time=min(total_duration,seg.start_time+slot)

def _clamp_and_monotonicize(segments:list[SubtitleSegment],total_duration:float)->None:
 previous_end=0.0
 for seg in segments:
  seg.start_time=min(max(seg.start_time,0.0),total_duration);seg.end_time=min(max(seg.end_time,0.0),total_duration)
  if seg.start_time<previous_end:seg.start_time=previous_end
  if seg.end_time<=seg.start_time:seg.end_time=min(total_duration,seg.start_time+.8)
  previous_end=seg.end_time
