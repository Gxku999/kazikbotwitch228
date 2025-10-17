from flask import Flask, request, jsonify
import json, random, time, os, requests

app = Flask(__name__)

# Настройки
REPO = "Gxku999/kazikbot"   # ⚠️ замени на свой репозиторий
FILE_PATH = "balances.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Кеш балансов
balances = {}

# === GitHub Sync ===
def load_balances():
    global balances
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            content = res.json()
            data = json.loads(requests.utils.unquote(content["content"]))
            balances = data
        else:
            balances = {}
    except Exception as e:
        print(f"Ошибка загрузки балансов: {e}")
        balances = {}

def save_balances():
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha", None) if res.status_code == 200 else None

        data_str = json.dumps(balances, ensure_ascii=False, indent=2)
        content_b64 = data_str.encode("utf-8").decode("utf-8")
        message = "update balances"
        payload = {
            "message": message,
            "content": data_str,
            "sha": sha
        }
        requests.put(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Ошибка сохранения балансов: {e}")

# === Игровая логика ===
def get_balance(user):
    if user not in balances:
        balances[user] = 1500
        save_balances()
    return balances[user]

def set_balance(user, amount):
    balances[user] = amount
    save_balances()

colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

@app.route("/")
def home():
    return "KazikBot Twitch Casino работает 🎰"

@app.route("/roll")
def roll():
    user = request.args.get("user")
    color = request.args.get("color")
    bet = request.args.get("bet")

    if not user or not color or not bet:
        return jsonify({"message": "❌ Используй !roll [red|black|green] [ставка]"})

    color = color.lower()
    if color not in colors:
        return jsonify({"message": "❌ Цвет должен быть red, black или green"})

    try:
        bet = int(bet)
    except:
        return jsonify({"message": "❌ Ставка должна быть числом!"})

    balance = get_balance(user)
    if bet > balance:
        return jsonify({"message": f"❌ Недостаточно монет! Баланс: {balance}"})

    result = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]
    multiplier = 14 if result == "green" else 2 if result == color else 0

    win = bet * (multiplier - 1)
    new_balance = balance + win if multiplier else balance - bet

    set_balance(user, new_balance)

    outcome = "✅ Победа!" if multiplier else "❌ Проигрыш"
    msg = (f"🎰 {user} ставит {bet} на {colors[color]}! "
           f"Выпало {colors[result]} — {outcome} | Баланс: {new_balance}")
    return jsonify({"message": msg})

@app.route("/balance")
def balance():
    user = request.args.get("user")
    bal = get_balance(user)
    return jsonify({"message": f"💰 Баланс {user}: {bal} монет"})

if __name__ == "__main__":
    load_balances()
    app.run(host="0.0.0.0", port=10000)
