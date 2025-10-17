from flask import Flask, request, jsonify
import json, random, os, requests, base64

app = Flask(__name__)

# === Настройки ===
REPO = "Gxku999/kazikbot"  # ⚠️ замени на свой репозиторий
FILE_PATH = "balances.json"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

balances = {}

# === GitHub: загрузка и сохранение ===
def load_balances():
    global balances
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers)

        if res.status_code == 200:
            content = res.json()["content"]
            data = base64.b64decode(content).decode("utf-8")
            balances = json.loads(data)
            print("[✅] Балансы успешно загружены с GitHub.")
        else:
            print(f"[⚠️] balances.json не найден ({res.status_code}). Создаю новый файл.")
            balances = {}
            save_balances()
    except Exception as e:
        print(f"[❌] Ошибка при загрузке балансов: {e}")
        balances = {}

def save_balances():
    try:
        url = f"https://api.github.com/repos/{REPO}/contents/{FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers)
        sha = res.json().get("sha", None) if res.status_code == 200 else None

        data_str = json.dumps(balances, ensure_ascii=False, indent=2)
        content_b64 = base64.b64encode(data_str.encode()).decode()

        payload = {
            "message": "update balances",
            "content": content_b64,
            "sha": sha
        }

        put_res = requests.put(url, headers=headers, json=payload)
        if put_res.status_code in [200, 201]:
            print("[💾] Балансы успешно сохранены на GitHub.")
        else:
            print(f"[⚠️] Ошибка сохранения на GitHub: {put_res.status_code} — {put_res.text}")
    except Exception as e:
        print(f"[❌] Ошибка сохранения балансов: {e}")

# === Игровая логика ===
def get_balance(user):
    if user not in balances:
        balances[user] = 1500
        save_balances()
    return balances[user]

def set_balance(user, amount):
    balances[user] = max(0, amount)
    save_balances()

colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

@app.route("/")
def home():
    return "🎰 Twitch Casino Bot Online"

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

    if multiplier:
        balance += bet * (multiplier - 1)
        outcome = f"✅ Победа! | +{bet * (multiplier - 1)}"
    else:
        balance -= bet
        outcome = "❌ Проигрыш"

    set_balance(user, balance)

    msg = (f"🎰 {user} ставит {bet} на {colors[color]}! "
           f"Выпало {colors[result]} — {outcome} | Баланс: {balance}")
    return jsonify({"message": msg})

@app.route("/balance")
def balance():
    user = request.args.get("user")
    bal = get_balance(user)
    return jsonify({"message": f"💰 Баланс {user}: {bal} монет"})

if __name__ == "__main__":
    load_balances()
    app.run(host="0.0.0.0", port=10000)
