from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db
from app.api import jobs, events, settings, subtitles, whisper, system, plugins, search, facefusion, runtime_cleanup
from app.api.endpoints import media_library as media_library_router
from app.api.endpoints import actors as actor_router
from app.knowledge import api as knowledge_api


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.tasks.manager import job_manager
    await job_manager.recover_queued_jobs()
    from app.plugins.runtime import runtime as plugin_runtime
    try:
        await plugin_runtime.start_background_tasks()
    except Exception:
        pass
    try:
        yield
    finally:
        try:
            await plugin_runtime.stop_background_tasks()
        except Exception:
            pass


app = FastAPI(
    title="NOOR",
    description="Local-first AI platform for JAV video processing and media management",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:4173",
        "http://192.168.31.3:4173",
        "http://192.168.31.3:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(events.router)
app.include_router(settings.router)
app.include_router(subtitles.router)
app.include_router(whisper.router)
app.include_router(system.router)
app.include_router(plugins.router)
app.include_router(runtime_cleanup.router)
app.include_router(search.router)
app.include_router(facefusion.router)
app.include_router(knowledge_api.router)
app.include_router(media_library_router.router)
app.include_router(actor_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
