from fastapi import FastAPI, HTTPException, Query

from config import DEFAULT_CATEGORIES
from manager import create_game, get_game
from socket_server import socket_server

app = FastAPI()


@app.on_event("startup")
def startup_event():
    socket_server.start()


@app.on_event("shutdown")
def shutdown_event():
    socket_server.stop()


def _parse_categories(raw: str | None):
    if not raw:
        return DEFAULT_CATEGORIES.copy()

    categories = []
    for part in raw.split(","):
        value = part.strip().lower().replace(" ", "_")
        if value:
            categories.append(value)

    return categories or DEFAULT_CATEGORIES.copy()


@app.get("/")
def root():
    return {"ok": True, "message": "STOP server running"}
@app.get("/new")
@app.get("/stop/new")
def new_game(
    categories: str | None = Query(default=None),
    duration: int = Query(default=60),
    lock_seconds: int = Query(default=5),
):
    game = create_game(
        categories=_parse_categories(categories),
        duration_seconds=duration,
        lock_seconds=lock_seconds,
    )

    return {
        "id": game.id,
        "game_id": game.id,
        "join_url": f"/{game.id}",
        "message": "Partida creada",
        "socket_host": "TU_IP_PUBLICA_O_DOMINIO",
        "socket_port": 9100,
        "instructions": f"Conéctate por socket y envía: JOIN {game.id} TU_NOMBRE",
    }


@app.get("/{game_id}")
@app.get("/stop/{game_id}")
def join_game(game_id: str):
    game = get_game(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="La partida no existe")

    return {
        "id": game.id,
        "game_id": game.id,
        "state": game.snapshot(),
        "socket_host": "TU_IP_PUBLICA_O_DOMINIO",
        "socket_port": 9100,
        "instructions": f"Conéctate por socket y envía: JOIN {game.id} TU_NOMBRE",
    }
