# -*- coding: utf-8 -*-
from flask import Flask, request, Response
import random, json, time, os

app = Flask(__name__)

BALANCES_FILE = "balances.json"
ADMINS = ["gxku999"]  # 👈 Твой ник (стример)
BONUS_AMOUNT = 500
BONUS_INTERVAL = 60 * 60 * 24      # 24 часа
ACTIVE_REWARD = 500
ACTIVE_INTERVAL = 60 * 15          # 15 минут
START_BALANCE = 1000

# === загрузка данных ===
if os.path.exists(BALANCES_FILE):
    with open(BALANCES_FILE, "r", encoding="utf-8") as f:
        try:
            balances = json.load(f)
        except:
            balances = {}
else:
    balances = {}

def save_data():
    with open(BALANCES_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

def text_response(msg):
    return Response(msg, mimetype="text/plain; charset=utf-8")

def color_icon(color):
    return {"red": "🟥", "black": "⬛", "green": "🟩"}.get(color, "❓")

def get_user(name):
    name = name.strip().lower()
    if name not in balances:
        balances[name] = {
            "balance": START_BALANCE,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0,
            "last_active": 0
        }
    return balances[name]

# 🎰 Основная команда рулетки
@app.route("/roulette")
def roulette():
    # Параметры запроса
    user = (request.args.get("user") or "").strip()
    color = (request.args.get("color") or "").strip().lower()
    bet = request.args.get("bet")

    colors = ["red", "black", "green"]

    # 🧠 ChatElements иногда путает местами аргументы (user и color)
    if user.lower() in colors:
        # Меняем местами
        color = user.lower()
        user = (request.args.get("color") or "UnknownUser").strip()

    if not user or not color or not bet:
        return text_response("❌ Использование: !roll <red/black/green> <ставка>")

    try:
        bet = int(bet)
    except ValueError:
        return text_response("❌ Ставка должна быть числом!")

    if color not in colors:
        return text_response("❌ Цвет должен быть red, black или green!")

    data = get_user(user)

    if bet <= 0:
        return text_response("❌ Ставка должна быть больше нуля!")

    if data["balance"] < bet:
        return text_response(f"💸 {user}, недостаточно монет! Баланс: {data['balance']}")

    # 💸 Снимаем ставку
    data["balance"] -= bet

    # 🎡 Крутим рулетку
    result = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]
    multiplier = 14 if result == "green" else 2

    if result == color:
        win_amount = bet * multiplier
        data["balance"] += win_amount
        data["wins"] += 1
        msg = (
            f"🎰 {user} ставит {bet} на {color_icon(color)}! "
            f"Выпало {color_icon(result)} — ✅ Победа! "
            f"| +{win_amount - bet} | Баланс: {data['balance']}"
        )
    else:
        data["losses"] += 1
        msg = (
            f"🎰 {user} ставит {bet} на {color_icon(color)}! "
            f"Выпало {color_icon(result)} — ❌ Проигрыш | Баланс: {data['balance']}"
        )

    save_data()
    return text_response(msg)

# 💰 Проверка баланса + активность
@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return text_response("❌ Укажи ник пользователя.")
    data = get_user(user)
    now = time.time()

    msg = f"💰 Баланс {user}: {data['balance']} монет"

    if now - data["last_active"] >= ACTIVE_INTERVAL:
        data["balance"] += ACTIVE_REWARD
        data["last_active"] = now
        msg += f"\n⏱ {user} получает {ACTIVE_REWARD} монет за активность! 🎁"

    save_data()
    return text_response(msg)

# 🎁 Ежедневный бонус
@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return text_response("❌ Укажи ник.")
    data = get_user(user)
    now = time.time()

    if now - data["last_bonus"] < BONUS_INTERVAL:
        remaining = int((BONUS_INTERVAL - (now - data["last_bonus"])) / 3600)
        return text_response(f"⏳ {user}, бонус уже получен! Попробуй через {remaining} ч.")

    data["balance"] += BONUS_AMOUNT
    data["last_bonus"] = now
    save_data()
    return text_response(f"🎁 {user} получает ежедневный бонус {BONUS_AMOUNT}! Баланс: {data['balance']}")

# 🏆 Топ 10 игроков
@app.route("/top")
def top():
    if not balances:
        return text_response("Пока нет игроков 😴")
    top10 = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n"
    for i, (u, d) in enumerate(top10, 1):
        msg += f"{i}. {u} — {d['balance']} монет\n"
    return text_response(msg.strip())

# 👑 Админ: добавить или убрать монеты
@app.route("/admin")
def admin():
    user = (request.args.get("user") or "").lower()
    target = request.args.get("target")
    action = request.args.get("action")
    amount = request.args.get("amount")

    if user not in ADMINS:
        return text_response("⛔ Нет доступа.")

    if not all([target, action, amount]):
        return text_response("❌ Использование: !admin <ник> <add/remove> <сумма>")

    try:
        amount = int(amount)
    except ValueError:
        return text_response("❌ Сумма должна быть числом!")

    data = get_user(target)
    if action == "add":
        data["balance"] += amount
        msg = f"✅ {user} добавил {amount} монет игроку {target}. Баланс: {data['balance']}"
    elif action == "remove":
        data["balance"] = max(0, data["balance"] - amount)
        msg = f"⚠️ {user} забрал {amount} монет у {target}. Баланс: {data['balance']}"
    else:
        return text_response("❌ Действие должно быть add или remove")

    save_data()
    return text_response(msg)

@app.route("/")
def home():
    return text_response("✅ Twitch Casino Bot работает!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
