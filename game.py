import json
import random
import string
import threading
import time
from typing import Optional


class Game:
    def __init__(self, gid: str, categories: list[str], duration_seconds: int, lock_seconds: int):
        self.id = gid
        self.categories = categories
        self.duration_seconds = duration_seconds
        self.lock_seconds = lock_seconds

        self.state = "waiting"  # waiting | playing | finished
        self.letter: Optional[str] = None
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None
        self.finish_reason: Optional[str] = None

        self.players = {}  # player_id -> {"name": str, "conn": socket.socket}
        self.next_player_number = 1

        self.board = {
            c: {
                "value": None,
                "locked_by": None,
                "lock_expires_at": None,
                "lock_timer": None,
            }
            for c in self.categories
        }

        self.lock = threading.RLock()
        self.send_lock = threading.Lock()

        self.monitor_thread = threading.Thread(target=self._monitor_game, daemon=True)
        self.monitor_thread.start()

    def _monitor_game(self):
        while True:
            time.sleep(1)
            with self.lock:
                if self.state == "finished":
                    return
                if self.state != "playing" or self.started_at is None:
                    continue

                if time.time() - self.started_at >= self.duration_seconds:
                    self._finish_game_locked("timeout")
                    return

    def _snapshot_locked(self):
        now = time.time()
        elapsed = None
        if self.started_at is not None:
            elapsed = int(now - self.started_at)

        return {
            "game_id": self.id,
            "state": self.state,
            "letter": self.letter,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "finish_reason": self.finish_reason,
            "duration_seconds": self.duration_seconds,
            "lock_seconds": self.lock_seconds,
            "elapsed_seconds": elapsed,
            "categories": self.categories,
            "players": [
                {"player_id": pid, "name": pdata["name"]}
                for pid, pdata in self.players.items()
            ],
            "board": {
                c: {
                    "value": entry["value"],
                    "locked_by": entry["locked_by"],
                    "lock_remaining": (
                        max(0, int(entry["lock_expires_at"] - now))
                        if entry["lock_expires_at"] is not None
                        else None
                    ),
                }
                for c, entry in self.board.items()
            },
        }

    def snapshot(self):
        with self.lock:
            return self._snapshot_locked()

    def _send_json(self, conn, payload: dict):
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with self.send_lock:
            conn.sendall(data)

    def broadcast(self, payload: dict):
        with self.lock:
            sockets = [pdata["conn"] for pdata in self.players.values()]

        for conn in sockets:
            try:
                self._send_json(conn, payload)
            except Exception:
                pass

    def add_player(self, name: str, conn):
        with self.lock:
            if self.state != "waiting":
                raise ValueError("La partida ya ha comenzado o ha terminado.")

            player_id = f"P{self.next_player_number}"
            self.next_player_number += 1

            self.players[player_id] = {
                "name": name,
                "conn": conn,
            }

            return player_id, self._snapshot_locked()

    def remove_player(self, player_id: str):
        should_finish = False

        with self.lock:
            if player_id not in self.players:
                return

            self.players.pop(player_id, None)

            for category, entry in self.board.items():
                if entry["locked_by"] == player_id and entry["value"] is None:
                    self._unlock_category_locked(category)

            if self.state == "playing" and len(self.players) == 0:
                should_finish = True

        if should_finish:
            self.finish_game("all_players_left")

    def start_game(self):
        with self.lock:
            if self.state != "waiting":
                return False, "La partida ya estaba iniciada o terminada."

            if len(self.players) == 0:
                return False, "No hay jugadores conectados."

            self.state = "playing"
            self.letter = random.choice(string.ascii_uppercase)
            self.started_at = time.time()
            snapshot = self._snapshot_locked()

        self.broadcast({
            "type": "game_started",
            "letter": self.letter,
            "state": snapshot,
        })
        return True, "Partida iniciada."

    def _unlock_after(self, category: str, player_id: str, expires_at: float):
        time.sleep(self.lock_seconds)

        with self.lock:
            if self.state != "playing":
                return

            entry = self.board.get(category)
            if not entry:
                return

            if entry["locked_by"] != player_id:
                return

            if entry["value"] is not None:
                return

            if entry.get("lock_expires_at") != expires_at:
                return

            self._unlock_category_locked(category)
            snapshot = self._snapshot_locked()

        self.broadcast({
            "type": "category_unlocked",
            "category": category,
            "state": snapshot,
        })

    def _unlock_category_locked(self, category: str):
        entry = self.board[category]
        timer = entry.get("lock_timer")

        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass

        entry["locked_by"] = None
        entry["lock_timer"] = None
        entry["lock_expires_at"] = None

    def lock_category(self, player_id: str, category: str):
        category = category.strip().lower()

        with self.lock:
            if self.state != "playing":
                return False, "La partida no está en juego."

            if category not in self.board:
                return False, "Categoría no válida."

            entry = self.board[category]
            if entry["value"] is not None:
                return False, "Esa categoría ya está completada."

            if entry["locked_by"] is not None:
                return False, "Esa categoría ya está bloqueada."

            expires_at = time.time() + self.lock_seconds
            entry["locked_by"] = player_id
            entry["lock_expires_at"] = expires_at

            timer = threading.Timer(
                self.lock_seconds,
                self._unlock_after,
                args=(category, player_id, expires_at),
            )
            entry["lock_timer"] = timer
            timer.daemon = True
            timer.start()

            snapshot = self._snapshot_locked()

        self.broadcast({
            "type": "category_locked",
            "category": category,
            "locked_by": player_id,
            "state": snapshot,
        })
        return True, "Categoría bloqueada."

    def set_category(self, player_id: str, category: str, value: str):
        category = category.strip().lower()
        value = value.strip()

        with self.lock:
            if self.state != "playing":
                return False, "La partida no está en juego."

            if category not in self.board:
                return False, "Categoría no válida."

            if self.letter is None:
                return False, "Todavía no se ha generado la letra."

            if not value:
                return False, "La palabra no puede estar vacía."

            if not value.upper().startswith(self.letter.upper()):
                return False, f"La palabra debe empezar por {self.letter}."

            entry = self.board[category]
            if entry["locked_by"] != player_id:
                return False, "No eres el dueño de esa categoría."

            entry["value"] = value
            self._unlock_category_locked(category)

            snapshot = self._snapshot_locked()
            completed = all(self.board[c]["value"] is not None for c in self.categories)

        self.broadcast({
            "type": "board_updated",
            "category": category,
            "value": value,
            "state": snapshot,
        })

        if completed:
            self.finish_game("completed")

        return True, "Categoría actualizada."

    def _finish_game_locked(self, reason: str):
        if self.state == "finished":
            return

        self.state = "finished"
        self.finished_at = time.time()
        self.finish_reason = reason

        for category in list(self.board.keys()):
            self._unlock_category_locked(category)

        snapshot = self._snapshot_locked()
        sockets = [pdata["conn"] for pdata in self.players.values()]

        payload = {
            "type": "game_over",
            "reason": reason,
            "state": snapshot,
        }

        for conn in sockets:
            try:
                self._send_json(conn, payload)
            except Exception:
                pass

            try:
                conn.shutdown(2)
            except Exception:
                pass

            try:
                conn.close()
            except Exception:
                pass

        self.players.clear()

    def finish_game(self, reason: str):
        with self.lock:
            self._finish_game_locked(reason)
