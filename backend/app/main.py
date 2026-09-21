from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import (
    admin, auth, customers, funding, merchant, performance, pipeline, realization,
    reports, rmft, target, upload, wa,
)

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # MVP schema bootstrap. For a production rollout, replace with Alembic
    # migrations so schema changes are versioned (see README "Next steps").
    Base.metadata.create_all(bind=engine)


app.include_router(auth.router)
app.include_router(rmft.router)
app.include_router(upload.router)
app.include_router(funding.router)
app.include_router(customers.router)
app.include_router(pipeline.router)
app.include_router(realization.router)
app.include_router(performance.router)
app.include_router(wa.router)
app.include_router(target.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(merchant.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
