# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import ocr, analyze

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