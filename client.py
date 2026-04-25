import json
import select
import socket
import sys
import threading
from typing import Any, Dict


STOP_EVENT = threading.Event()


def pretty_board(state: Dict[str, Any]) -> None:
    print("\n📋 TABLERO")
    board = state.get("board", {})
    for category, entry in board.items():
        value = entry.get("value")
        locked_by = entry.get("locked_by")
        lock_remaining = entry.get("lock_remaining")

        status = "✅" if value else "⬜"
        extra = ""
        if value:
            extra = f" → {value}"
        elif locked_by:
            extra = f" 🔒 por {locked_by}"
            if lock_remaining is not None:
                extra += f" ({lock_remaining}s)"
        print(f"  {status} {category}{extra}")


def pretty_state(state: Dict[str, Any]) -> None:
    print("\n🎮 ESTADO DE LA PARTIDA")
    print(f"  ID: {state.get('game_id')}")
    print(f"  Estado: {state.get('state')}")
    print(f"  Letra: {state.get('letter')}")
    print(f"  Tiempo: {state.get('elapsed_seconds')} / {state.get('duration_seconds')}s")

    players = state.get("players", [])
    print("\n👥 JUGADORES")
    if not players:
        print("  - Ninguno")
    else:
        for p in players:
            print(f"  - {p['player_id']}: {p['name']}")

    pretty_board(state)
    print()


def handle_message(raw: str) -> None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print(f"SERVER> {raw}")
        return

    msg_type = data.get("type")

    if msg_type == "welcome":
        print("👋 Conectado al servidor")
        print(data.get("message", ""))

    elif msg_type == "joined":
        print(f"✅ Unido a la partida {data.get('game_id')} como {data.get('player_id')}")
        pretty_state(data["state"])

    elif msg_type == "player_joined":
        print(f"👤 Nuevo jugador: {data.get('name')}")
        pretty_state(data["state"])

    elif msg_type == "game_started":
        print(f"\n🚀 ¡Empieza la partida! Letra: {data.get('letter')}")
        pretty_state(data["state"])

    elif msg_type == "category_locked":
        print(f"🔒 Categoría bloqueada: {data.get('category')} por {data.get('locked_by')}")
        pretty_state(data["state"])

    elif msg_type == "category_unlocked":
        print(f"🔓 Categoría desbloqueada: {data.get('category')}")
        pretty_state(data["state"])

    elif msg_type == "board_updated":
        print(f"✏️ Categoría actualizada: {data.get('category')} = {data.get('value')}")
        pretty_state(data["state"])

    elif msg_type == "game_over":
        print("\n🏁 FIN DE PARTIDA")
        print(f"Motivo: {data.get('reason')}")
        pretty_state(data["state"])
        STOP_EVENT.set()

    elif msg_type == "error":
        print(f"❌ Error: {data.get('message')}")

    else:
        print("SERVER>", data)


def receiver(sock: socket.socket) -> None:
    reader = sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        while not STOP_EVENT.is_set():
            line = reader.readline()
            if not line:
                print("\n🔌 Conexión cerrada por el servidor.")
                STOP_EVENT.set()
                break
            handle_message(line.strip())
    finally:
        try:
            reader.close()
        except Exception:
            pass


def main() -> None:
    if len(sys.argv) < 4:
        print("Uso: python3 client.py <host> <game_id> <nombre> [port]")
        return

    host = sys.argv[1]
    game_id = sys.argv[2]
    name = sys.argv[3]
    port = int(sys.argv[4]) if len(sys.argv) >= 5 else 9100

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    threading.Thread(target=receiver, args=(sock,), daemon=True).start()

    sock.sendall(f"JOIN {game_id} {name}\n".encode("utf-8"))

    print("\nEscribe comandos: GO!, LOCK <categoria>, SET <categoria> <palabra>, BOARD, QUIT\n")

    try:
        while not STOP_EVENT.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not ready:
                continue

            cmd = sys.stdin.readline()
            if not cmd:
                continue

            cmd = cmd.strip()
            if not cmd:
                continue

            if STOP_EVENT.is_set():
                break

            sock.sendall((cmd + "\n").encode("utf-8"))

            if cmd.upper() == "QUIT":
                STOP_EVENT.set()
                break

    except KeyboardInterrupt:
        STOP_EVENT.set()
    finally:
        try:
            sock.close()
        except Exception:
            pass
        print("\n👋 Cliente cerrado.")


if __name__ == "__main__":
    main()
