from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class WhisperCancellationRequested(Exception): pass
class WhisperModel(str,Enum):
 ANIME='anime-whisper'; KOTOBA_V2='kotoba-whisper-v2.0-faster'; REAZON_NEMO_V2='reazonspeech-nemo-v2'; TINY='tiny'; BASE='base'; SMALL='small'; MEDIUM='medium'; LARGE_V3='large-v3'; LARGE_V3_TURBO='large-v3-turbo'
class PipelineMode(str,Enum):
 SINGLE='single'; ENSEMBLE='ensemble'; FASTER='faster'; BALANCED='balanced'; ANIME='anime'; TRANSFORMERS='transformers'; QWEN='qwen'; CUSTOM='custom'; COLI='coli'; REAZON='reazon'
class VADMethod(str,Enum): NONE='none'; SILERO='silero'; AUDITOK='auditok'; SEMANTIC='semantic'; TEN='ten'
class SpeechEnhancer(str,Enum): NONE='none'; CLEARVOICE='clearvoice'; FFMPEG_DSP='ffmpeg-dsp'; SILERO_VAD='silero-vad'; DEMUCS='demucs'
class MergeStrategy(str,Enum): SMART='smart_merge'; FULL_MERGE='full_merge'; PASS1_PRIMARY='pass1_primary'; PASS2_PRIMARY='pass2_primary'; LONGEST='longest'; PASS1_OVERLAP='pass1_overlap'; PASS2_OVERLAP='pass2_overlap'
class Sensitivity(str,Enum): CONSERVATIVE='conservative'; BALANCED='balanced'; AGGRESSIVE='aggressive'
class TranslateProvider(str,Enum): OLLAMA='ollama'; OPENAI='openai'
@dataclass
class WhisperConfig:
 strategy:str='recommended';executor_key:str='recommended';model:WhisperModel=WhisperModel.ANIME;device:str='auto';compute_type:str='default';pipeline_mode:PipelineMode=PipelineMode.ENSEMBLE;merge_strategy:MergeStrategy=MergeStrategy.SMART;vad_method:VADMethod=VADMethod.SEMANTIC;vad_filter:bool=True;vad_min_silence_ms:int=1500;vad_min_speech_ms:int=100;enhancers:list[str]=field(default_factory=list);audio_preprocess_mode:str='none';audio_preprocess_model:str='vocal_balanced';timestamp_mode:str='aligner_interpolation';aligner_backend:str='qwen3';framer_backend:str='vad-grouped';pass1_model:WhisperModel=WhisperModel.ANIME;pass1_pipeline:Optional[PipelineMode]=None;pass2_model:WhisperModel=WhisperModel.LARGE_V3;pass2_pipeline:Optional[PipelineMode]=None;language:str='ja';sensitivity:Sensitivity=Sensitivity.BALANCED;beam_size:int=2;best_of:int=2;translate_to:Optional[str]=None;translate_base_url:str='https://api.openai.com/v1';translate_api_key:str='';translate_model:str='llama3.2';translate_style:str='adult_explicit';output_dir:Optional[str]=None
@dataclass
class SubtitleSegment: index:int;start_time:float;end_time:float;text:str;words:list=field(default_factory=list)
@dataclass
class TranscriptionResult: segments:list[SubtitleSegment];language:str;duration:float;source:str;metadata:dict=field(default_factory=dict)
@dataclass
class WhisperTask: id:str;video_path:str;config:WhisperConfig;status:str='pending';progress:float=0.0;current_pass:str='';log_lines:list[str]=field(default_factory=list);result:Optional[TranscriptionResult]=None;error:Optional[str]=None
