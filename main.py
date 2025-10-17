from flask import Flask, request, jsonify
import random
import json
import os
import time

app = Flask(__name__)

DATA_FILE = "balances.json"
BONUS_INTERVAL = 15 * 60  # 15 минут
DAILY_BONUS = 500
ACTIVE_BONUS = 500
START_BALANCE = 1000

ADMINS = ["gxku999"]  # 👉 твой ник на Twitch

# --- Утилиты ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def color_icon(color):
    return {"red": "🟥", "black": "⬛", "green": "🟩"}.get(color, "❓")

def text_response(message):
    return jsonify({"message": message})

def get_user(user):
    if user not in users:
        users[user] = {
            "balance": START_BALANCE,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0,
            "last_active": 0
        }
    return users[user]

users = load_data()

# --- Роуты ---
@app.route("/")
def home():
    return "🎰 Twitch Casino Bot is running!"

@app.route("/balance")
def balance():
    user = request.args.get("user", "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя!")

    data = get_user(user)
    now = time.time()

    # Автобонус за активность каждые 15 минут
    if now - data["last_active"] >= BONUS_INTERVAL:
        data["balance"] += ACTIVE_BONUS
        data["last_active"] = now
        save_data()
        return text_response(f"💰 Баланс {user}: {data['balance']} монет\n⏱ {user} получает {ACTIVE_BONUS} монет за активность! 🎁")

    return text_response(f"💰 Баланс {user}: {data['balance']} монет")

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя!")

    data = get_user(user)
    now = time.time()

    if now - data["last_bonus"] < 24 * 3600:
        return text_response(f"⏳ {user}, ты уже получал бонус сегодня! Приходи завтра 🎁")

    data["balance"] += DAILY_BONUS
    data["last_bonus"] = now
    save_data()

    return text_response(f"🎁 {user} получает ежедневный бонус {DAILY_BONUS}! Баланс: {data['balance']}")

@app.route("/roll")
def roll():
    user = request.args.get("user", "").strip()
    color = request.args.get("color", "").lower().strip()
    bet = request.args.get("bet", "").strip()

    if not user or not color or not bet:
        return text_response("❌ Использование: !roll <red/black/green> <ставка>")

    try:
        bet = int(bet)
    except ValueError:
        return text_response("❌ Ставка должна быть числом!")

    if color not in ["red", "black", "green"]:
        return text_response("❌ Цвет должен быть red, black или green!")

    data = get_user(user)
    if bet <= 0:
        return text_response("❌ Ставка должна быть больше 0!")

    if data["balance"] < bet:
        return text_response(f"💸 {user}, недостаточно монет! Баланс: {data['balance']}")

    # снимаем ставку
    data["balance"] -= bet

    # рулетка
    result = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]
    multiplier = 14 if result == "green" else 2

    if result == color:
        win_amount = bet * multiplier
        data["balance"] += win_amount
        data["wins"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_icon(color)}! Выпало {color_icon(result)} — ✅ Победа! +{win_amount - bet} | Баланс: {data['balance']}"
    else:
        data["losses"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_icon(color)}! Выпало {color_icon(result)} — ❌ Проигрыш | Баланс: {data['balance']}"

    save_data()
    return text_response(msg)

@app.route("/stats")
def stats():
    user = request.args.get("user", "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя!")

    data = get_user(user)
    total = data["wins"] + data["losses"]
    winrate = (data["wins"] / total * 100) if total > 0 else 0
    return text_response(
        f"📊 Статистика {user}: Победы — {data['wins']}, Поражения — {data['losses']}, WinRate — {winrate:.1f}% | Баланс: {data['balance']}"
    )

@app.route("/top")
def top():
    top_users = sorted(users.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n"
    for i, (name, data) in enumerate(top_users, start=1):
        msg += f"{i}. {name} — {data['balance']} монет\n"
    return text_response(msg.strip())

@app.route("/admin")
def admin():
    user = request.args.get("user", "").strip().lower()
    target = request.args.get("target", "").strip()
    action = request.args.get("action", "").lower()
    amount = request.args.get("amount", "").strip()

    if user not in [a.lower() for a in ADMINS]:
        return text_response("🚫 У тебя нет прав использовать эту команду!")

    if not target or not action or not amount:
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
        return text_response("❌ Действие должно быть 'add' или 'remove'.")

    save_data()
    return text_response(msg)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
