from fastapi import FastAPI

app = FastAPI(title="Wisselijst")

@app.get("/health")
def health():
    return {"status": "ok"}

