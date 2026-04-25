import random
import threading

from config import (
    DEFAULT_CATEGORIES,
    DEFAULT_GAME_DURATION_SECONDS,
    DEFAULT_LOCK_SECONDS,
)
from game import Game

_games = {}
_lock = threading.Lock()


def create_game(categories=None, duration_seconds=None, lock_seconds=None) -> Game:
    if categories is None:
        categories = DEFAULT_CATEGORIES
    if duration_seconds is None:
        duration_seconds = DEFAULT_GAME_DURATION_SECONDS
    if lock_seconds is None:
        lock_seconds = DEFAULT_LOCK_SECONDS

    with _lock:
        while True:
            gid = str(random.randint(1000, 9999))
            if gid not in _games:
                game = Game(gid, categories, duration_seconds, lock_seconds)
                _games[gid] = game
                return game


def get_game(gid: str):
    with _lock:
        return _games.get(gid)
