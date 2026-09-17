from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.supabase_client import supabase
from app.routers import ocr, analyze

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router)
app.include_router(analyze.router)

@app.get("/")
def root():
    return {"message": "K-Food Backend API is running!"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/profiles/test")
def test_profiles():
    response = supabase.table("profiles").select("*").execute()
    return response.data