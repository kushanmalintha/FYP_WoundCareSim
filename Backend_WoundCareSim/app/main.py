from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.session_routes import router as session_router
from app.api.scenario_routes import router as scenario_router
from app.api.audio_routes import router as audio_router
from app.api.websocket_routes import router as websocket_router

app = FastAPI(
    title="VR Nursing Education System Backend",
    version="Week-9"
)

# CORS Configuration for Test UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing; restrict in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(session_router)
app.include_router(scenario_router)
app.include_router(audio_router)

app.include_router(websocket_router)
