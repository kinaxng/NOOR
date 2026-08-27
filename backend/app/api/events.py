from __future__ import annotations
import asyncio,json
from fastapi import APIRouter,HTTPException
from sse_starlette.sse import EventSourceResponse
from app.tasks.manager import job_manager
router=APIRouter(prefix='/api')
@router.get('/jobs/{job_id}/events')
async def job_events(job_id:str):
 job=await job_manager.get_job(job_id)
 if not job:raise HTTPException(404,'Job not found')
 async def event_generator():
  event_queue=job_manager.get_event_queue(job_id)
  yield {'event':'connected','data':json.dumps({'job_id':job_id})}
  while True:
   try:
    msg=await asyncio.wait_for(event_queue.get(),timeout=60.0);kind=msg.get('type')
    if kind=='progress':
     yield {'event':'progress','data':json.dumps({'type':'progress','job_id':msg.get('job_id') or job_id,'progress':msg['progress'],'phase_key':msg.get('phase_key'),'phase_group':msg.get('phase_group'),'phase_label':msg.get('phase_label'),'phase_progress':msg.get('phase_progress'),'detail':msg.get('detail')})}
    elif kind=='log':
     yield {'event':'log','data':json.dumps({'type':'log','job_id':msg.get('job_id') or job_id,'line':msg['line']})}
    elif kind in {'queued','blocked'}:
     yield {'event':kind,'data':json.dumps({'type':kind,'job_id':msg.get('job_id') or job_id,'phase_key':msg.get('phase_key'),'phase_group':msg.get('phase_group'),'phase_label':msg.get('phase_label'),'phase_progress':msg.get('phase_progress'),'detail':msg.get('detail')})}
    elif kind in {'completed','failed','cancelled','skipped'}:
     yield {'event':'done','data':json.dumps({'type':kind,'job_id':msg.get('job_id') or job_id,'success':msg.get('success',False),'progress':msg.get('progress'),'phase_key':msg.get('phase_key'),'phase_group':msg.get('phase_group'),'phase_label':msg.get('phase_label'),'phase_progress':msg.get('phase_progress'),'detail':msg.get('detail'),'error':msg.get('error')})}
     await job_manager.remove_event_queue(job_id);return
   except asyncio.TimeoutError:
    yield {'event':'keepalive','data':json.dumps({'time':asyncio.get_event_loop().time()})}
 return EventSourceResponse(event_generator())
