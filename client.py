import socket
import sys
import threading


def receiver(sock: socket.socket):
    reader = sock.makefile("r", encoding="utf-8", newline="\n")
    try:
        while True:
            line = reader.readline()
            if not line:
                print("Conexión cerrada por el servidor.")
                break
            print("SERVER>", line.strip())
    finally:
        try:
            reader.close()
        except Exception:
            pass


def main():
    if len(sys.argv) < 4:
        print("Uso: python client.py <host> <game_id> <nombre> [port]")
        return

    host = sys.argv[1]
    game_id = sys.argv[2]
    name = sys.argv[3]
    port = int(sys.argv[4]) if len(sys.argv) >= 5 else 9100

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))

    threading.Thread(target=receiver, args=(sock,), daemon=True).start()

    sock.sendall(f"JOIN {game_id} {name}\n".encode("utf-8"))

    try:
        while True:
            cmd = input("> ").strip()
            if not cmd:
                continue
            sock.sendall((cmd + "\n").encode("utf-8"))
            if cmd.upper() == "QUIT":
                break
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
