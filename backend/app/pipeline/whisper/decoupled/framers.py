from __future__ import annotations
def apply_framer_backend(segments:list[tuple[str,float,float]],*,backend:str)->list[tuple[str,float,float]]:
 normalized=(backend or 'vad-grouped').strip().lower()
 if normalized in {'vad-grouped','default','vad_grouped'}:return list(segments)
 if normalized in {'full-scene','full_scene'}:
  if not segments:return []
  return [(segments[0][0],min(start for _,start,_ in segments),max(end for _,_,end in segments))]
 return list(segments)
