from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.session import engine, SessionLocal, Base
from src.db.models import Run

app = FastAPI(title="Wisselijst")


@app.on_event("startup")
def on_startup():
    # Simple dev approach: create tables automatically
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


class RunCreate(BaseModel):
    playlist_name: str
    status: str = "started"


@app.post("/runs")
def create_run(payload: RunCreate, db: Session = Depends(get_db)):
    run = Run(playlist_name=payload.playlist_name, status=payload.status)
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"id": run.id, "playlist_name": run.playlist_name, "status": run.status}


@app.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.id.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "playlist_name": r.playlist_name,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in runs
    ]

