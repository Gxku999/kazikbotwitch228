# -*- coding: utf-8 -*-
from flask import Flask, request
import os, random, json, time

app = Flask(__name__)

DB_FILE = "balances.json"
START_BALANCE = 1000
DAILY_BONUS = 500
BONUS_COOLDOWN = 24 * 60 * 60  # 24 часа


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


def ensure_user(user):
    db = load_db()
    if user not in db:
        db[user] = {
            "balance": START_BALANCE,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0
        }
        save_db(db)
    return db


def get_balance(user):
    db = load_db()
    ensure_user(user)
    return db[user]["balance"]


def update_balance(user, balance):
    db = load_db()
    ensure_user(user)
    db[user]["balance"] = balance
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

    db = load_db()
    ensure_user(user)
    balance = db[user]["balance"]

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
        db[user]["wins"] += 1
        msg = f"{user}, выпало {result} ({roll}). Ты выиграл {win}! Баланс: {balance}"
    else:
        balance -= bet
        db[user]["losses"] += 1
        msg = f"{user}, выпало {result} ({roll}). Ты проиграл {bet}. Баланс: {balance}"

    db[user]["balance"] = balance
    save_db(db)
    return msg


@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return "Укажи ?user=твой_ник"
    db = load_db()
    ensure_user(user)
    bal = db[user]["balance"]
    wins = db[user]["wins"]
    losses = db[user]["losses"]
    return f"{user}, баланс: {bal}. Побед: {wins}, поражений: {losses}."


@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return "Укажи ?user=твой_ник"
    db = load_db()
    ensure_user(user)

    now = int(time.time())
    last = db[user].get("last_bonus", 0)
    if now - last < BONUS_COOLDOWN:
        remaining = int((BONUS_COOLDOWN - (now - last)) / 3600)
        return f"{user}, бонус уже получен. Следующий через ~{remaining}ч."

    db[user]["balance"] += DAILY_BONUS
    db[user]["last_bonus"] = now
    save_db(db)
    return f"{user}, ты получил ежедневный бонус {DAILY_BONUS}! Баланс: {db[user]['balance']}"


@app.route("/top")
def top():
    db = load_db()
    if not db:
        return "Пока нет игроков."
    leaders = sorted(db.items(), key=lambda x: x[1]["balance"], reverse=True)[:5]
    text = "💎 ТОП игроков:\n"
    for i, (u, data) in enumerate(leaders, start=1):
        text += f"{i}. {u}: {data['balance']}\n"
    return text.strip()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
