# -*- coding: utf-8 -*-
from flask import Flask, request
import os, random, json

app = Flask(__name__)

DB_FILE = "balances.json"
START_BALANCE = 1000


def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f)


def get_balance(user):
    db = load_db()
    return db.get(user, START_BALANCE)


def update_balance(user, balance):
    db = load_db()
    db[user] = balance
    save_db(db)


@app.route("/")
def home():
    return "Twitch Casino Bot работает!"


@app.route("/roulette")
def roulette():
    user = request.args.get("user")
    color = request.args.get("color")
    bet = request.args.get("bet")

    if not user or not color or not bet:
        return "Использование: !roulette color bet"

    try:
        bet = int(bet)
    except ValueError:
        return "Ставка должна быть числом!"

    color = color.lower()
    if color not in ["red", "black", "green"]:
        return "Цвет должен быть red, black или green!"

    balance = get_balance(user)
    if balance <= 0:
        return f"{user}, у тебя 0 баланса. Жди восстановления!"

    if bet > balance:
        return f"{user}, ставка превышает баланс ({balance})."

    roll = random.randint(0, 36)
    result = "green" if roll == 0 else ("red" if roll % 2 == 0 else "black")

    if color == result:
        multiplier = 14 if result == "green" else 2
        win = bet * (multiplier - 1)
        balance += win
        msg = f"{user}, выпало {result} ({roll}). Ты выиграл {win}! Баланс: {balance}"
    else:
        balance -= bet
        msg = f"{user}, выпало {result} ({roll}). Ты проиграл {bet}. Баланс: {balance}"

    update_balance(user, balance)
    return msg


@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return "Укажи ?user=твой_ник"
    balance = get_balance(user)
    return f"{user}, твой баланс: {balance}."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
