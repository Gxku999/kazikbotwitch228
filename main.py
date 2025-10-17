from flask import Flask, request
import random
import json
import time
import os

app = Flask(__name__)

DATA_FILE = "balances.json"

# Загрузка балансов из файла
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        balances = json.load(f)
else:
    balances = {}

# Сохранение данных
def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

# Инициализация пользователя
def init_user(user):
    if user not in balances:
        balances[user] = {
            "balance": 1000,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0
        }

@app.route("/")
def home():
    return "Twitch Casino Bot работает!"

@app.route("/roll")
def roll():
    user = request.args.get("user")
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "")

    if not user:
        return "Ошибка: не указано имя пользователя."
    if not bet.isdigit():
        return "Ставка должна быть числом!"

    bet = int(bet)
    init_user(user)

    balance = balances[user]["balance"]
    if bet > balance:
        return f"{user}, у тебя недостаточно монет! Баланс: {balance}"

    if color not in ["red", "black", "green"]:
        return "Можно ставить только на red, black или green."

    # Выпадающий цвет
    result = random.choices(["red", "black", "green"], weights=[48, 48, 4])[0]

    if color == result:
        multiplier = 14 if result == "green" else 2
        win = bet * (multiplier - 1)
        balances[user]["balance"] += win
        balances[user]["wins"] += 1
        msg = f"{user} ставит {bet} на {color}... Выпало {result}! Победа +{win}! Баланс: {balances[user]['balance']}"
    else:
        balances[user]["balance"] -= bet
        balances[user]["losses"] += 1
        msg = f"{user} ставит {bet} на {color}... Выпало {result}! Проигрыш -{bet}. Баланс: {balances[user]['balance']}"

    save_data()
    return msg

@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return "Ошибка: не указано имя пользователя."

    init_user(user)
    data = balances[user]
    return f"{user}, баланс: {data['balance']}. Побед: {data['wins']}, поражений: {data['losses']}."

@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return "Ошибка: не указано имя пользователя."

    init_user(user)
    now = time.time()
    last = balances[user]["last_bonus"]

    if now - last < 86400:  # 24 часа
        remaining = int((86400 - (now - last)) / 3600)
        return f"{user}, ты уже получал бонус сегодня! Попробуй снова через {remaining} ч."
    else:
        balances[user]["balance"] += 500
        balances[user]["last_bonus"] = now
        save_data()
        return f"{user}, ты получил ежедневный бонус +500 монет! Баланс: {balances[user]['balance']}."

@app.route("/top")
def top():
    if not balances:
        return "Пока нет игроков."

    top_players = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:5]
    msg = "🏆 Топ игроков:\n"
    for i, (name, data) in enumerate(top_players, start=1):
        msg += f"{i}. {name} — {data['balance']}\n"
    return msg.strip()

@app.route("/stats")
def stats():
    user = request.args.get("user")
    if not user:
        return "Ошибка: не указано имя пользователя."

    init_user(user)
    w = balances[user]["wins"]
    l = balances[user]["losses"]
    total = w + l
    winrate = 0 if total == 0 else round((w / total) * 100, 1)
    return f"{user}: побед — {w}, поражений — {l} (винрейт {winrate}%)."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
