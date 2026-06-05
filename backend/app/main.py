from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import create_tables
from app.api import claims

app = FastAPI(title="Plum OPD Adjudication - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://plum-wine.vercel.app",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Ensure DB tables exist
    create_tables()


@app.get("/api/health")
def health():
    return {"status": "healthy"}


# include routers
app.include_router(
    claims.router,
    prefix="/api",
    tags=["claims"],
)
