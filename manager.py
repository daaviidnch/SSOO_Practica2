import random

games = {}

def create_game():
    while True:
        gid = str(random.randint(1000, 9999))
        if gid not in games:
            from game import Game
            game = Game(gid)
            games[gid] = game
            return game

def get_game(gid):
    return games.get(gid)
