from flask import Flask, request
import json, os, random, time, threading

app = Flask(__name__)

BALANCES_FILE = "balances.json"
BONUS_INTERVAL = 900  # 15 минут (в секундах)
BONUS_AMOUNT = 500
DEFAULT_BALANCE = 1500

balances = {}
last_bonus_time = {}

# === Работа с балансами ===

def load_balances():
    global balances
    if os.path.exists(BALANCES_FILE):
        with open(BALANCES_FILE, "r", encoding="utf-8") as f:
            try:
                balances = json.load(f)
            except json.JSONDecodeError:
                balances = {}
    else:
        balances = {}

def save_balances():
    tmp = BALANCES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)
    os.replace(tmp, BALANCES_FILE)

load_balances()

# === Команды ===

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return "❌ Укажи имя пользователя."

    balance = balances.get(user, DEFAULT_BALANCE)
    balances[user] = balance
    save_balances()

    return f"💰 Баланс {user}: {balance} монет"

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    now = time.time()

    if not user:
        return "❌ Укажи имя пользователя."

    last_time = last_bonus_time.get(user, 0)
    if now - last_time < BONUS_INTERVAL:
        mins = int((BONUS_INTERVAL - (now - last_time)) / 60)
        return f"⏳ {user}, бонус можно получить через {mins} мин."

    balances[user] = balances.get(user, DEFAULT_BALANCE) + BONUS_AMOUNT
    last_bonus_time[user] = now
    save_balances()

    return f"🎁 {user} получает {BONUS_AMOUNT} монет за активность! Баланс: {balances[user]}"

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "")

    if not user or not color or not bet:
        return "❌ Формат: !roll <red|black|green> <ставка>"

    try:
        bet = int(bet)
    except ValueError:
        return "❌ Ставка должна быть числом!"

    balance = balances.get(user, DEFAULT_BALANCE)
    if bet <= 0:
        return "❌ Ставка должна быть больше 0!"
    if bet > balance:
        return f"❌ Недостаточно монет! Баланс: {balance}"

    result = random.choice(["red", "black", "green"])
    color_emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}

    if result == color:
        multiplier = 14 if result == "green" else 2
        win = bet * (multiplier - 1)
        balance += win
        outcome = f"✅ Победа! | +{win}"
    else:
        balance -= bet
        outcome = f"❌ Проигрыш | -{bet}"

    balances[user] = balance
    save_balances()

    return f"🎰 {user} ставит {bet} на {color_emoji.get(color,'❓')}! Выпало {color_emoji[result]} — {outcome} | Баланс: {balance}"

@app.route("/top")
def top():
    if not balances:
        return "🏆 Пока нет игроков."

    sorted_bal = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [f"{i+1}. {u}: {b} монет" for i, (u, b) in enumerate(sorted_bal)]
    return "🏆 Топ 10 игроков:\n" + "\n".join(lines)

@app.route("/stats")
def stats():
    user = request.args.get("user", "").lower()
    if not user:
        return "❌ Укажи имя пользователя."
    bal = balances.get(user, DEFAULT_BALANCE)
    return f"📊 Статистика {user}:\n💰 Баланс: {bal}"

# === Автобонус ===
def auto_bonus():
    while True:
        for user in list(balances.keys()):
            balances[user] += BONUS_AMOUNT
        save_balances()
        print(f"[AUTO BONUS] всем игрокам выдано +{BONUS_AMOUNT}")
        time.sleep(BONUS_INTERVAL)

threading.Thread(target=auto_bonus, daemon=True).start()

# === Запуск ===
@app.route("/")
def index():
    return "✅ Twitch Casino Bot работает!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
