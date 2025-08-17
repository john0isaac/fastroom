from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fast_room_api.api.dependencies import lifespan
from fast_room_api.api.routers import auth, rooms, users, ws
from fast_room_api.logging_config import setup_logging

setup_logging()

app = FastAPI(
    title="FastRoom API",
    summary="FastRoom WebSocket API",
    description="A WebSocket API for real-time communication in FastRoom applications.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development; adjust in production
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(ws.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fast_room_api.api.main:app", host="0.0.0.0", port=8000, reload=True)
