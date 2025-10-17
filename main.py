from flask import Flask, request, Response
import random, json, os, time, base64, requests, threading

app = Flask(__name__)

# === Глобальные переменные ===
balances = {}
active_viewers = {}
BONUS_INTERVAL = 900  # 15 минут
BONUS_AMOUNT = 500
START_BALANCE = 1500

# === GitHub настройки ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/balances.json"


# === Функции для работы с GitHub ===
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
        print("💾 Балансы сохранены:", res.status_code)
    except Exception as e:
        print("Ошибка при сохранении балансов:", e)


# === Автоматический бонус за актив ===
def add_bonus():
    while True:
        time.sleep(BONUS_INTERVAL)
        for user in list(active_viewers.keys()):
            balances[user] = balances.get(user, START_BALANCE) + BONUS_AMOUNT
        save_balances()
        print("🎁 Ежедневный бонус начислен активным зрителям!")


threading.Thread(target=add_bonus, daemon=True).start()


# === Маршруты API ===
@app.route("/")
def index():
    return Response("🎰 Twitch Casino Bot работает!", mimetype="text/plain")


@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return Response("❌ Ошибка: пользователь не указан", mimetype="text/plain")

    balance = balances.get(user, START_BALANCE)
    balances[user] = balance
    active_viewers[user] = time.time()
    save_balances()

    msg = f"💰 Баланс @{user}: {balance} монет"
    return Response(msg, mimetype="text/plain")


@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "0")

    try:
        bet = int(bet)
    except:
        return Response("❌ Ставка должна быть числом!", mimetype="text/plain")

    if bet <= 0:
        return Response("❌ Минимальная ставка — 1 монета!", mimetype="text/plain")

    balances[user] = balances.get(user, START_BALANCE)
    if bet > balances[user]:
        return Response(f"❌ Недостаточно монет! Баланс: {balances[user]}", mimetype="text/plain")

    result = random.choice(["red", "black", "green"])
    colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

    win = 0
    if color == result:
        if result == "green":
            win = bet * 14
        else:
            win = bet * 2
        balances[user] += win - bet
        outcome = f"✅ Победа! | +{win - bet}"
    else:
        balances[user] -= bet
        outcome = "❌ Проигрыш"

    save_balances()
    msg = f"🎰 @{user} ставит {bet} на {colors.get(color, '❓')}! Выпало {colors[result]} — {outcome} | Баланс: {balances[user]}"
    return Response(msg, mimetype="text/plain")


@app.route("/top")
def top():
    if not balances:
        return Response("🏆 Топ пуст!", mimetype="text/plain")

    top10 = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n" + "\n".join([f"{i+1}. {u}: {b}" for i, (u, b) in enumerate(top10)])
    return Response(msg, mimetype="text/plain")


@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    if not user:
        return Response("❌ Ошибка: не указан пользователь", mimetype="text/plain")

    balances[user] = balances.get(user, START_BALANCE) + BONUS_AMOUNT
    save_balances()

    msg = f"🎁 @{user} получает {BONUS_AMOUNT} монет за активность! Новый баланс: {balances[user]}"
    return Response(msg, mimetype="text/plain")


# === Запуск ===
if __name__ == "__main__":
    load_balances()
    app.run(host="0.0.0.0", port=10000)
