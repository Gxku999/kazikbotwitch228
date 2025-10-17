from flask import Flask, request, jsonify
import random, json, os, time, base64, requests, threading

app = Flask(__name__)

# ======== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ========
balances = {}
stats = {}
active_viewers = {}
BONUS_INTERVAL = 900  # 15 минут = 900 секунд
BONUS_AMOUNT = 500
START_BALANCE = 1500

# ======== GITHUB ========
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/balances.json"

# ======== ФУНКЦИИ ========
def load_balances():
    global balances
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(GITHUB_API, headers=headers)
        if r.status_code == 200:
            data = r.json()
            content = base64.b64decode(data["content"]).decode()
            balances = json.loads(content)
            print("✅ Балансы загружены из GitHub.")
        else:
            print("⚠️ Не удалось загрузить балансы:", r.status_code, r.text)
    except Exception as e:
        print("Ошибка при загрузке балансов:", e)

def save_balances():
    try:
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        r = requests.get(GITHUB_API, headers=headers)
        sha = None
        if r.status_code == 200:
            sha = r.json().get("sha")

        content = base64.b64encode(json.dumps(balances, indent=2).encode()).decode()
        data = {
            "message": "update balances.json",
            "content": content,
            "sha": sha
        }
        res = requests.put(GITHUB_API, headers=headers, data=json.dumps(data))
        print("💾 Балансы сохранены в GitHub:", res.status_code)
    except Exception as e:
        print("Ошибка при сохранении балансов:", e)

def add_bonus():
    while True:
        time.sleep(BONUS_INTERVAL)
        for user in list(active_viewers.keys()):
            balances[user] = balances.get(user, START_BALANCE) + BONUS_AMOUNT
        save_balances()
        print("🎁 Бонус за актив начислен всем зрителям!")

# Запускаем поток с бонусами
threading.Thread(target=add_bonus, daemon=True).start()

# ======== API ========
@app.route("/")
def index():
    return "🎰 Twitch Casino Bot работает!"

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return jsonify({"message": "Ошибка: пользователь не указан"})
    balance = balances.get(user, START_BALANCE)
    active_viewers[user] = time.time()
    save_balances()
    return jsonify({"message": f"💰 Баланс {user}: {balance} монет"})

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "0")

    try:
        bet = int(bet)
    except:
        return jsonify({"message": "❌ Ставка должна быть числом!"})

    if bet <= 0:
        return jsonify({"message": "❌ Минимальная ставка — 1 монета!"})

    balances[user] = balances.get(user, START_BALANCE)
    if bet > balances[user]:
        return jsonify({"message": f"❌ Недостаточно монет! Баланс: {balances[user]}"})

    result = random.choice(["red", "black", "green"])
    colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

    multiplier = 2 if color == result else 0
    if result == "green":
        multiplier = 14

    win = bet * (multiplier - (1 if multiplier == 0 else 0))
    balances[user] += win - bet
    save_balances()

    outcome = "✅ Победа!" if win > 0 else "❌ Проигрыш"
    msg = f"🎰 {user} ставит {bet} на {colors.get(color, '❓')}! Выпало {colors[result]} — {outcome} | Баланс: {balances[user]}"
    return jsonify({"message": msg})

@app.route("/top")
def top():
    if not balances:
        return jsonify({"message": "Топ пуст!"})
    top10 = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n" + "\n".join([f"{i+1}. {u}: {b}" for i, (u, b) in enumerate(top10)])
    return jsonify({"message": msg})

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    if not user:
        return jsonify({"message": "Ошибка: не указан пользователь"})
    balances[user] = balances.get(user, START_BALANCE) + BONUS_AMOUNT
    save_balances()
    return jsonify({"message": f"🎁 {user} получает бонус {BONUS_AMOUNT} монет! Баланс: {balances[user]}"})

# ======== СТАРТ ========
if __name__ == "__main__":
    load_balances()
    app.run(host="0.0.0.0", port=10000)
