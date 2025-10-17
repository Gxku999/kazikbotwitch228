from flask import Flask, request, Response
import random
import json
import time
import os

app = Flask(__name__)

# === Настройки ===
BALANCES_FILE = "balances.json"
ADMINS = ["Gxku999"]  # <-- твой Twitch ник
BONUS_AMOUNT = 500
BONUS_INTERVAL = 60 * 60 * 24  # 24 часа
ACTIVE_REWARD = 500
ACTIVE_INTERVAL = 60 * 15  # 15 минут

# === Загрузка данных ===
if os.path.exists(BALANCES_FILE):
    with open(BALANCES_FILE, "r", encoding="utf-8") as f:
        balances = json.load(f)
else:
    balances = {}

# === Утилиты ===
def save_data():
    with open(BALANCES_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

def text_response(msg: str):
    """Отправляет чистый текст без JSON"""
    return Response(msg, mimetype="text/plain; charset=utf-8")

def get_user(user):
    if user not in balances:
        balances[user] = {
            "balance": 1000,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0,
            "last_active": 0
        }
    return balances[user]

def color_icon(color):
    """Возвращает эмодзи круга по цвету"""
    icons = {"red": "🟥", "black": "⬛", "green": "🟩"}
    return icons.get(color, "❓")

# === Рулетка ===
@app.route("/roulette")
def roulette():
    user = request.args.get("user")
    color = request.args.get("color")
    bet = request.args.get("bet")

    if not user or not color or not bet:
        return text_response("❌ Использование: !roll <red/black/green> <ставка>")

    color = color.lower()
    if color not in ["red", "black", "green"]:
        return text_response("❌ Цвет должен быть red, black или green!")

    try:
        bet = int(bet)
    except ValueError:
        return text_response("❌ Ставка должна быть числом!")

    data = get_user(user)
    if bet <= 0:
        return text_response("❌ Ставка должна быть больше нуля!")

    if data["balance"] < bet:
        return text_response("❌ Недостаточно средств на балансе!")

    result = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]
    multiplier = 14 if result == "green" else 2
    win = bet * multiplier if color == result else 0

    color_icon_bet = color_icon(color)
    color_icon_result = color_icon(result)

    if win > 0:
        data["balance"] += win - bet
        data["wins"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_icon_bet}! Выпало {color_icon_result} — ✅ Победа! | +{win - bet} | Баланс: {data['balance']}"
    else:
        data["balance"] -= bet
        data["losses"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_icon_bet}! Выпало {color_icon_result} — ❌ Проигрыш | Баланс: {data['balance']}"

    save_data()
    return text_response(msg)

# === Баланс (и награда за активность) ===
@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return text_response("❌ Укажи имя пользователя.")

    data = get_user(user)
    now = time.time()
    msg = f"💰 Баланс {user}: {data['balance']} монет"

    if now - data["last_active"] >= ACTIVE_INTERVAL:
        data["balance"] += ACTIVE_REWARD
        data["last_active"] = now
        msg += f"\n⏱ {user} получает {ACTIVE_REWARD} монет за активность на стриме! 🎁"

    save_data()
    return text_response(msg)

# === Ежедневный бонус ===
@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return text_response("❌ Укажи имя пользователя.")

    data = get_user(user)
    now = time.time()
    if now - data["last_bonus"] < BONUS_INTERVAL:
        remaining = int((BONUS_INTERVAL - (now - data["last_bonus"])) / 3600)
        return text_response(f"⏳ {user}, бонус уже получен! Попробуй через {remaining} ч.")
    data["balance"] += BONUS_AMOUNT
    data["last_bonus"] = now
    save_data()
    return text_response(f"🎁 {user} получает ежедневный бонус {BONUS_AMOUNT} монет! Баланс: {data['balance']}")

# === Статистика ===
@app.route("/stats")
def stats():
    user = request.args.get("user")
    if not user:
        return text_response("❌ Укажи имя пользователя.")
    data = get_user(user)
    return text_response(f"📊 {user}: Победы — {data['wins']} | Поражения — {data['losses']}")

# === Топ-10 ===
@app.route("/top")
def top():
    top10 = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n"
    for i, (u, d) in enumerate(top10, start=1):
        msg += f"{i}. {u} — {d['balance']} монет\n"
    return text_response(msg.strip())

# === Админ ===
@app.route("/admin")
def admin():
    user = request.args.get("user")
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
        msg = f"✅ Админ {user} добавил {amount} монет игроку {target}. Баланс: {data['balance']}"
    elif action == "remove":
        data["balance"] = max(0, data["balance"] - amount)
        msg = f"⚠️ Админ {user} забрал {amount} монет у {target}. Баланс: {data['balance']}"
    else:
        return text_response("❌ Неверное действие. Используй add/remove")

    save_data()
    return text_response(msg)

# === Главная страница ===
@app.route("/")
def home():
    return text_response("✅ Twitch Casino Bot активен!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
