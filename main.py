from flask import Flask, request, jsonify
import random
import json
import os
import time
import requests
import base64

app = Flask(__name__)

# === GitHub конфигурация ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_FILE = "balances.json"

def github_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def load_balances():
    """Загрузка balances.json из GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}?ref={GITHUB_BRANCH}"
    r = requests.get(url, headers=github_headers())
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode("utf-8")
        return json.loads(content)
    else:
        print("⚠️ balances.json не найден, создаем новый...")
        return {}

def save_balances(data):
    """Сохранение balances.json обратно в GitHub"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    r = requests.get(url, headers=github_headers())
    sha = r.json().get("sha") if r.status_code == 200 else None

    content = json.dumps(data, indent=4, ensure_ascii=False)
    encoded = base64.b64encode(content.encode()).decode()
    message = "update balances.json"

    payload = {
        "message": message,
        "content": encoded,
        "branch": GITHUB_BRANCH
    }
    if sha:
        payload["sha"] = sha

    resp = requests.put(url, headers=github_headers(), json=payload)
    if resp.status_code not in (200, 201):
        print("❌ Ошибка GitHub сохранения:", resp.text)

# === Локальный кэш ===
balances = load_balances()

# === Иконки цветов ===
COLORS = {
    "red": "🟥",
    "black": "⬛",
    "green": "🟩"
}

# === Константы ===
BONUS_COINS = 500
BONUS_INTERVAL = 15 * 60  # 15 минут в секундах

# === Маршруты ===

@app.route("/")
def home():
    return "🎰 Twitch Casino Bot is running!"

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return jsonify({"message": "Укажи ник!"})
    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}
        save_balances(balances)
    bal = balances[user]["balance"]
    return jsonify({"message": f"💰 Баланс {user}: {bal} монет"})

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    now = int(time.time())

    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}

    last_bonus = balances[user].get("last_bonus", 0)
    if now - last_bonus >= BONUS_INTERVAL:
        balances[user]["balance"] += BONUS_COINS
        balances[user]["last_bonus"] = now
        save_balances(balances)
        return jsonify({"message": f"🎁 {user} получил {BONUS_COINS} монет за активность! Баланс: {balances[user]['balance']}"})
    else:
        left = BONUS_INTERVAL - (now - last_bonus)
        mins = left // 60
        return jsonify({"message": f"⏳ Бонус можно получить через {mins} минут"})

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "0")

    if not user or not color or not bet.isdigit():
        return jsonify({"message": "❌ Неверная команда! Пример: !roll red 100"})

    bet = int(bet)
    if color not in COLORS:
        return jsonify({"message": "❌ Цвет должен быть red, black или green!"})

    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}

    if balances[user]["balance"] < bet:
        return jsonify({"message": f"💸 Недостаточно монет, {user}!"})

    result = random.choices(["red", "black", "green"], [48, 48, 4])[0]
    emoji_result = COLORS[result]
    win = 0

    if result == color:
        multiplier = 14 if color == "green" else 2
        win = bet * multiplier
        balances[user]["balance"] += win
        balances[user]["wins"] += 1
        outcome = f"✅ Победа! | +{win} | Баланс: {balances[user]['balance']}"
    else:
        balances[user]["balance"] -= bet
        balances[user]["losses"] += 1
        outcome = f"❌ Проигрыш | Баланс: {balances[user]['balance']}"

    save_balances(balances)
    return jsonify({"message": f"🎰 {user} ставит {bet} на {COLORS[color]}! Выпало {emoji_result} — {outcome}"})

@app.route("/top")
def top():
    top_players = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 ТОП 10 игроков:\n"
    for i, (user, data) in enumerate(top_players, 1):
        msg += f"{i}. {user}: {data['balance']} монет\n"
    return jsonify({"message": msg.strip()})

@app.route("/stats")
def stats():
    user = request.args.get("user", "").lower()
    if user not in balances:
        return jsonify({"message": "❌ Нет данных об этом пользователе!"})
    wins = balances[user]["wins"]
    losses = balances[user]["losses"]
    return jsonify({"message": f"📊 Статистика {user}: Победы — {wins}, Поражения — {losses}"})

# === Автоматическое начисление за активность ===
@app.route("/activity")
def activity():
    user = request.args.get("user", "").lower()
    now = int(time.time())
    if not user:
        return jsonify({"message": "Укажи ник!"})

    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}

    if now - balances[user]["last_bonus"] >= BONUS_INTERVAL:
        balances[user]["balance"] += BONUS_COINS
        balances[user]["last_bonus"] = now
        save_balances(balances)
        return jsonify({"message": f"⏱ {user} получает {BONUS_COINS} монет за 15 минут активности! Баланс: {balances[user]['balance']}"})
    return jsonify({"message": ""})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
