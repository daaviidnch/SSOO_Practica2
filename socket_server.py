import json
import socket
import threading

from config import SOCKET_HOST, SOCKET_PORT
from manager import get_game


class GameSocketServer:
    def __init__(self, host=SOCKET_HOST, port=SOCKET_PORT):
        self.host = host
        self.port = port
        self.running = False
        self.server_socket = None
        self.accept_thread = None

    def start(self):
        if self.running:
            return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(50)
        self.server_socket.settimeout(0.5)

        self.running = True
        self.accept_thread = threading.Thread(target=self._accept_loop, daemon=True)
        self.accept_thread.start()

    def stop(self):
        self.running = False
        if self.server_socket is not None:
            try:
                self.server_socket.close()
            except Exception:
                pass

    def _send_json(self, conn, payload: dict):
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        conn.sendall(data)

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn, addr):
        reader = conn.makefile("r", encoding="utf-8", newline="\n")
        game = None
        player_id = None

        try:
            self._send_json(conn, {
                "type": "welcome",
                "message": "Primero envía: JOIN <game_id> <nombre>",
            })

            first = reader.readline()
            if not first:
                return

            first = first.strip()
            parts = first.split(" ", 2)

            if len(parts) < 3 or parts[0].upper() != "JOIN":
                self._send_json(conn, {
                    "type": "error",
                    "message": "Formato correcto: JOIN <game_id> <nombre>",
                })
                return

            game_id = parts[1].strip()
            name = parts[2].strip()

            game = get_game(game_id)
            if game is None:
                self._send_json(conn, {
                    "type": "error",
                    "message": f"No existe la partida {game_id}",
                })
                return

            try:
                player_id, snapshot = game.add_player(name, conn)
            except ValueError as exc:
                self._send_json(conn, {
                    "type": "error",
                    "message": str(exc),
                })
                return

            self._send_json(conn, {
                "type": "joined",
                "game_id": game_id,
                "player_id": player_id,
                "state": snapshot,
            })

            game.broadcast({
                "type": "player_joined",
                "game_id": game_id,
                "player_id": player_id,
                "name": name,
                "state": game.snapshot(),
            })

            while True:
                line = reader.readline()
                if not line:
                    break

                command = line.strip()
                if not command:
                    continue

                upper = command.upper()

                if upper == "GO!":
                    ok, message = game.start_game()
                    if not ok:
                        self._send_json(conn, {"type": "error", "message": message})

                elif upper == "BOARD":
                    self._send_json(conn, {
                        "type": "board",
                        "state": game.snapshot(),
                    })

                elif upper.startswith("LOCK "):
                    category = command[5:].strip()
                    ok, message = game.lock_category(player_id, category)
                    if not ok:
                        self._send_json(conn, {"type": "error", "message": message})

                elif upper.startswith("SET "):
                    rest = command[4:].strip()
                    if " " not in rest:
                        self._send_json(conn, {
                            "type": "error",
                            "message": "Formato correcto: SET <categoria> <palabra>",
                        })
                        continue

                    category, value = rest.split(" ", 1)
                    ok, message = game.set_category(player_id, category, value)
                    if not ok:
                        self._send_json(conn, {"type": "error", "message": message})

                elif upper == "QUIT":
                    break

                else:
                    self._send_json(conn, {
                        "type": "error",
                        "message": "Comando no reconocido",
                    })

        except Exception:
            pass
        finally:
            if game is not None and player_id is not None:
                game.remove_player(player_id)

            try:
                reader.close()
            except Exception:
                pass

            try:
                conn.close()
            except Exception:
                pass


socket_server = GameSocketServer()
