from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from routers import auth, search

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Shopping Assistant API")

# Configure CORS for the extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the extension ID
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)

@app.get("/")
def read_root():
    return {"message": "Welcome to Shopping Assistant API"}
