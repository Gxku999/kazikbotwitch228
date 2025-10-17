from flask import Flask, request, jsonify
import json, os, random, threading, time, base64, requests

app = Flask(__name__)

BALANCES_FILE = "balances.json"
LOCK = threading.Lock()
START_BALANCE = 1500
BONUS_AMOUNT = 500
BONUS_INTERVAL = 15 * 60  # 15 минут

# === GitHub Настройки ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_PATH = os.getenv("GITHUB_PATH", "balances.json")
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"

balances = {}
last_bonus_time = {}

# === GITHUB: загрузка и сохранение ===
def load_from_github():
    global balances
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("[WARN] GitHub sync отключён.")
        return
    try:
        res = requests.get(GITHUB_API, headers={"Authorization": f"token {GITHUB_TOKEN}"})
        if res.status_code == 200:
            data = res.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            balances = json.loads(content)
            print("[SYNC] Балансы загружены из GitHub ✅")
        else:
            print("[WARN] balances.json не найден на GitHub (создастся при первом сохранении)")
    except Exception as e:
        print("[ERROR] load_from_github:", e)

def save_to_github():
    if not GITHUB_TOKEN or not GITHUB_REPO:
        return
    try:
        content = json.dumps(balances, ensure_ascii=False, indent=2)
        b64 = base64.b64encode(content.encode()).decode()
        res = requests.get(GITHUB_API, headers={"Authorization": f"token {GITHUB_TOKEN}"})
        sha = res.json().get("sha") if res.status_code == 200 else None

        data = {
            "message": "Auto-sync balances",
            "content": b64,
        }
        if sha:
            data["sha"] = sha

        requests.put(GITHUB_API, headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Content-Type": "application/json"
        }, data=json.dumps(data))
        print(f"[SYNC] balances.json обновлён на GitHub ✅")
    except Exception as e:
        print("[ERROR] save_to_github:", e)

# === АВТО-СИНХРОНИЗАЦИЯ ===
def auto_sync():
    while True:
        time.sleep(300)  # каждые 5 минут
        with LOCK:
            save_to_github()

threading.Thread(target=auto_sync, daemon=True).start()

# === ЛОКАЛЬНОЕ СОХРАНЕНИЕ ===
def save_local():
    with LOCK:
        with open(BALANCES_FILE, "w", encoding="utf-8") as f:
            json.dump(balances, f, ensure_ascii=False, indent=2)

# === ЗАГРУЗКА ===
def load_balances():
    if os.path.exists(BALANCES_FILE):
        try:
            with open(BALANCES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

# === ИНИЦИАЛИЗАЦИЯ ===
load_from_github()
balances.update(load_balances())

def get_balance(user):
    user = user.lower()
    if user not in balances:
        balances[user] = START_BALANCE
        save_local()
    return balances[user]

def update_balance(user, delta):
    user = user.lower()
    if user not in balances:
        balances[user] = START_BALANCE
    balances[user] = max(0, balances[user] + delta)
    save_local()
    save_to_github()

COLORS = {"red": "🟥", "black": "⬛", "green": "🟩"}

@app.route("/")
def home():
    return "✅ Twitch Casino Bot is running with GitHub Sync!"

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return jsonify({"message": "❌ Ошибка: не указан пользователь"})
    return jsonify({"message": f"💰 Баланс {user}: {get_balance(user)} монет"})

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "0")

    if not user or not color or not bet.isdigit():
        return jsonify({"message": "❌ Используй: !roll <color> <ставка>"})

    bet = int(bet)
    if bet <= 0:
        return jsonify({"message": "❌ Ставка должна быть > 0"})

    bal = get_balance(user)
    if bet > bal:
        return jsonify({"message": f"❌ Недостаточно монет! Баланс: {bal}"})

    rolled = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]

    win = 0
    if rolled == color:
        win = bet * (14 if color == "green" else 2)

    delta = win - bet
    update_balance(user, delta)

    return jsonify({
        "message": f"🎰 {user} ставит {bet} на {COLORS.get(color, color)}! "
                   f"Выпало {COLORS.get(rolled, rolled)} — "
                   f"{'✅ Победа! +' + str(win - bet) if win else '❌ Проигрыш -' + str(bet)} | "
                   f"Баланс: {get_balance(user)}"
    })

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    now = time.time()
    last = last_bonus_time.get(user, 0)

    if now - last < BONUS_INTERVAL:
        remain = int(BONUS_INTERVAL - (now - last))
        return jsonify({"message": f"⏳ Подожди {remain//60}м {remain%60}с до следующего бонуса"})

    update_balance(user, BONUS_AMOUNT)
    last_bonus_time[user] = now
    return jsonify({"message": f"🎁 {user} получил {BONUS_AMOUNT} монет! Баланс: {get_balance(user)}"})

@app.route("/top")
def top():
    top10 = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    msg = "\n".join([f"{i+1}. {u}: {b}" for i, (u, b) in enumerate(top10)])
    return jsonify({"message": "🏆 ТОП 10 игроков:\n" + msg})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
