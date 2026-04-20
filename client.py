import socket
import threading

def listen(sock):
    while True:
        try:
            print(sock.recv(1024).decode())
        except:
            break

host = input("host: ")
gid = input("game id: ")
name = input("name: ")

s = socket.socket()
s.connect((host, 9000))

threading.Thread(target=listen, args=(s,), daemon=True).start()

s.sendall(f"JOIN {gid} {name}\n".encode())

while True:
    msg = input("> ")
    s.sendall((msg + "\n").encode())
