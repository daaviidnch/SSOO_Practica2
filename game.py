import threading
import time
import random
import string
import json

class Game:
    def __init__(self, gid):
        self.id = gid
        self.players = {}  # id -> socket
        self.state = "waiting"
        self.letter = None

        self.categories = ["animal", "pais", "color"]
        self.board = {c: None for c in self.categories}
        self.locked = {c: None for c in self.categories}

        self.lock = threading.Lock()

    def broadcast(self, msg):
        data = (json.dumps(msg) + "\n").encode()
        for s in list(self.players.values()):
            try:
                s.sendall(data)
            except:
                pass

    def add_player(self, pid, sock):
        self.players[pid] = sock

    def start(self):
        with self.lock:
            if self.state != "waiting":
                return False
            self.state = "playing"
            self.letter = random.choice(string.ascii_uppercase)

        self.broadcast({"type": "start", "letter": self.letter})
        threading.Thread(target=self.timer, daemon=True).start()
        return True

    def timer(self):
        time.sleep(60)
        self.end("timeout")

    def lock_cat(self, pid, cat):
        with self.lock:
            if self.locked[cat] is None:
                self.locked[cat] = pid
                threading.Thread(target=self.unlock, args=(cat,), daemon=True).start()
                self.broadcast({"type": "lock", "cat": cat, "by": pid})

    def unlock(self, cat):
        time.sleep(5)
        with self.lock:
            if self.board[cat] is None:
                self.locked[cat] = None
                self.broadcast({"type": "unlock", "cat": cat})

    def set_value(self, pid, cat, val):
        with self.lock:
            if self.locked[cat] != pid:
                return
            if not val.upper().startswith(self.letter):
                return

            self.board[cat] = val
            self.locked[cat] = None

            self.broadcast({"type": "set", "cat": cat, "val": val})

            if all(self.board[c] for c in self.categories):
                self.end("completed")

    def end(self, reason):
        if self.state == "finished":
            return
        self.state = "finished"
        self.broadcast({"type": "end", "reason": reason})
