from flask import Flask, request, Response
import random
import json
import os
import time

app = Flask(__name__)

# ====== НАСТРОЙКИ ======
BALANCE_FILE = "balances.json"
BONUS_AMOUNT = 500
BONUS_INTERVAL = 15 * 60  # 15 минут
ADMINS = ["gxku999"]  # <-- Твой ник на Twitch
START_BALANCE = 1000

# ====== ХРАНЕНИЕ ДАННЫХ ======
if not os.path.exists(BALANCE_FILE):
    with open(BALANCE_FILE, "w") as f:
        json.dump({}, f)

def load_balances():
    with open(BALANCE_FILE, "r") as f:
        return json.load(f)

def save_balances(data):
    with open(BALANCE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def text_response(msg: str):
    return Response(msg, mimetype="text/plain; charset=utf-8")

# ====== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ======
def get_balance(user):
    data = load_balances()
    user = user.lower()
    if user not in data:
        data[user] = {
            "balance": START_BALANCE,
            "last_bonus": 0,
            "wins": 0,
            "losses": 0
        }
        save_balances(data)
    return data[user]["balance"]

def update_balance(user, amount):
    data = load_balances()
    user = user.lower()
    if user not in data:
        get_balance(user)
        data = load_balances()
    data[user]["balance"] += amount
    if data[user]["balance"] < 0:
        data[user]["balance"] = 0
    save_balances(data)

def can_get_bonus(user):
    data = load_balances()
    user = user.lower()
    now = time.time()
    last = data[user].get("last_bonus", 0)
    if now - last >= BONUS_INTERVAL:
        data[user]["last_bonus"] = now
        data[user]["balance"] += BONUS_AMOUNT
        save_balances(data)
        return True
    return False

# ====== КОМАНДЫ ======

@app.route("/")
def home():
    return text_response("✅ Казино бот работает! Команды: !roll, !balance, !bonus, !top, !stats")

@app.route("/roll")
def roll():
    user = request.args.get("user")
    color = request.args.get("color")
    bet = request.args.get("bet")

    if not user or not color or not bet:
        return text_response("⚠ Использование: !roll <red|black|green> <ставка>")

    color = color.lower()
    if color not in ["red", "black", "green"]:
        return text_response("❌ Цвет должен быть red, black или green!")

    try:
        bet = int(bet)
    except ValueError:
        return text_response("❌ Ставка должна быть числом!")

    balance = get_balance(user)
    if bet <= 0:
        return text_response("❌ Ставка должна быть положительной!")
    if bet > balance:
        return text_response(f"❌ Недостаточно монет! Баланс: {balance}")

    # Рулетка
    result = random.choices(
        ["red", "black", "green"],
        weights=[47, 47, 6],
        k=1
    )[0]

    emojis = {"red": "🟥", "black": "⬛", "green": "🟩"}

    data = load_balances()
    user_data = data[user.lower()]

    if color == result:
        multiplier = 14 if result == "green" else 2
        win = bet * multiplier
        update_balance(user, win)
        user_data["wins"] += 1
        outcome = f"✅ Победа! | +{win} | Баланс: {get_balance(user)}"
    else:
        update_balance(user, -bet)
        user_data["losses"] += 1
        outcome = f"❌ Проигрыш | Баланс: {get_balance(user)}"

    save_balances(data)

    msg = f"🎰 {user} ставит {bet} на {emojis[color]}! Выпало {emojis[result]} — {outcome}"
    return text_response(msg)

@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return text_response("⚠ Укажите имя: !balance")

    balance = get_balance(user)
    bonus_msg = ""
    if can_get_bonus(user):
        bonus_msg = f"\n⏱ {user} получает {BONUS_AMOUNT} монет за активность на стриме! 🎁"

    return text_response(f"💰 Баланс {user}: {balance} монет{bonus_msg}")

@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return text_response("⚠ Укажите имя: !bonus")

    if can_get_bonus(user):
        return text_response(f"🎁 {user} получил бонус {BONUS_AMOUNT} монет! Баланс: {get_balance(user)}")
    else:
        return text_response(f"⏱ {user}, бонус можно получить только раз в 15 минут!")

@app.route("/top")
def top():
    data = load_balances()
    top10 = sorted(data.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    lines = [f"{i+1}. {name} — {info['balance']} монет" for i, (name, info) in enumerate(top10)]
    return text_response("🏆 Топ 10 игроков:\n" + "\n".join(lines))

@app.route("/stats")
def stats():
    user = request.args.get("user")
    if not user:
        return text_response("⚠ Укажите имя: !stats")

    data = load_balances()
    user = user.lower()
    if user not in data:
        get_balance(user)
        data = load_balances()

    wins = data[user]["wins"]
    losses = data[user]["losses"]
    total = wins + losses
    winrate = (wins / total * 100) if total > 0 else 0
    return text_response(f"📊 Статистика {user}:\n✅ Побед: {wins}\n❌ Поражений: {losses}\n📈 Винрейт: {winrate:.1f}%")

@app.route("/admin")
def admin():
    user = request.args.get("user")
    target = request.args.get("target")
    action = request.args.get("action")
    amount = request.args.get("amount")

    if user.lower() not in [a.lower() for a in ADMINS]:
        return text_response("⛔ У вас нет прав администратора!")

    if not (target and action and amount):
        return text_response("⚙ Использование: !admin <ник> <add|remove> <сумма>")

    try:
        amount = int(amount)
    except ValueError:
        return text_response("❌ Сумма должна быть числом!")

    if action == "add":
        update_balance(target, amount)
        return text_response(f"✅ {user} добавил {amount} монет игроку {target}. Баланс: {get_balance(target)}")
    elif action == "remove":
        update_balance(target, -amount)
        return text_response(f"⚠️ {user} забрал {amount} монет у {target}. Баланс: {get_balance(target)}")
    else:
        return text_response("⚙ Неверное действие! Используй add или remove.")

# ====== СТАРТ ======
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
