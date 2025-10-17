from flask import Flask, request, Response
import requests, json, os, time, random

app = Flask(__name__)

# === CONFIG ===
REPO = os.getenv("GITHUB_REPO")
TOKEN = os.getenv("GITHUB_TOKEN")
FILE_PATH = "balances.json"
BRANCH = "main"

# === HELPER FUNCTIONS ===
def text_response(msg: str):
    return Response(json.dumps({"message": msg}, ensure_ascii=False),
                    mimetype="application/json; charset=utf-8")

def load_balances():
    """Загрузка балансов из GitHub"""
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = json.loads(res.json()["content"].encode())
        data = json.loads(base64.b64decode(res.json()["content"]).decode())
        return data
    else:
        return {}

def save_balances(data):
    """Сохранение балансов в GitHub"""
    url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {TOKEN}"}
    get_res = requests.get(url, headers=headers)
    sha = get_res.json().get("sha", None)

    encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
    payload = {
        "message": "update balances.json",
        "content": encoded,
        "branch": BRANCH,
        "sha": sha
    }
    requests.put(url, headers=headers, json=payload)

# === ROUTES ===
@app.route("/")
def home():
    return text_response("✅ Twitch Casino Bot работает!")

@app.route("/balance")
def balance():
    user = request.args.get("user")
    balances = load_balances()
    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}
        save_balances(balances)
    bal = balances[user]["balance"]
    return text_response(f"💰 Баланс {user}: {bal} монет")

@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    balances = load_balances()
    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}

    now = time.time()
    last_bonus = balances[user].get("last_bonus", 0)
    if now - last_bonus < 900:  # 15 минут
        remain = int(900 - (now - last_bonus)) // 60
        return text_response(f"⏳ Бонус можно получить через {remain} мин.")
    
    balances[user]["balance"] += 500
    balances[user]["last_bonus"] = now
    save_balances(balances)
    return text_response(f"🎁 {user} получил 500 монет за активность! Баланс: {balances[user]['balance']}")

@app.route("/roll")
def roll():
    user = request.args.get("user")
    color = request.args.get("color")
    bet = request.args.get("bet")

    if not color or not bet:
        return text_response("❌ Использование: !roll [red/black/green] [ставка]")

    balances = load_balances()
    if user not in balances:
        balances[user] = {"balance": 1500, "wins": 0, "losses": 0, "last_bonus": 0}

    try:
        bet = int(bet)
    except:
        return text_response("❌ Ставка должна быть числом!")

    if bet <= 0:
        return text_response("❌ Ставка должна быть больше 0!")

    if balances[user]["balance"] < bet:
        return text_response("💸 Недостаточно монет на балансе!")

    # списываем ставку
    balances[user]["balance"] -= bet

    # рулетка
    result = random.choices(["red", "black", "green"], weights=[48, 48, 4])[0]
    color_emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}

    if result == color:
        multiplier = 14 if color == "green" else 2
        win = bet * multiplier
        balances[user]["balance"] += win
        balances[user]["wins"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_emoji[color]}! Выпало {color_emoji[result]} — ✅ Победа! | +{win} | Баланс: {balances[user]['balance']}"
    else:
        balances[user]["losses"] += 1
        msg = f"🎰 {user} ставит {bet} на {color_emoji[color]}! Выпало {color_emoji[result]} — ❌ Проигрыш | Баланс: {balances[user]['balance']}"

    save_balances(balances)
    return text_response(msg)

@app.route("/top")
def top():
    balances = load_balances()
    top_users = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 ТОП 10 игроков:\n"
    for i, (user, data) in enumerate(top_users, 1):
        msg += f"{i}. {user}: {data['balance']} монет\n"
    return text_response(msg.strip())

@app.route("/stats")
def stats():
    user = request.args.get("user")
    balances = load_balances()
    if user not in balances:
        return text_response(f"📊 Нет данных о {user}.")
    stats = balances[user]
    msg = f"📊 Статистика {user}: Победы — {stats['wins']} | Поражения — {stats['losses']}"
    return text_response(msg)

# === MAIN ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
