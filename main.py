from flask import Flask, request, Response
import json, random, os, threading, time

app = Flask(__name__)
BALANCE_FILE = "balances.json"
START_BALANCE = 1500
LOCK = threading.Lock()

# === Вспомогательные функции ===

def load_balances():
    """Загружает балансы из файла."""
    if not os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)
    with open(BALANCE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_balances(balances):
    """Сохраняет балансы в файл."""
    with open(BALANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

def get_balance(user):
    balances = load_balances()
    return balances.get(user.lower(), START_BALANCE)

def update_balance(user, amount):
    with LOCK:
        balances = load_balances()
        user = user.lower()
        balances[user] = balances.get(user, START_BALANCE) + amount
        if balances[user] < 0:
            balances[user] = 0
        save_balances(balances)
        return balances[user]

# === Маршруты ===

@app.route("/")
def index():
    return Response("✅ Twitch Casino Bot запущен!", mimetype="text/plain; charset=utf-8")

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    bal = get_balance(user)
    return Response(f"💰 Баланс @{user}: {bal} монет", mimetype="text/plain; charset=utf-8")

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet_str = request.args.get("bet", "0")

    try:
        bet = int(bet_str)
    except ValueError:
        return Response("❌ Ставка должна быть числом!", mimetype="text/plain; charset=utf-8")

    if bet <= 0:
        return Response("❌ Ставка должна быть положительным числом!", mimetype="text/plain; charset=utf-8")

    balance_now = get_balance(user)
    if bet > balance_now:
        return Response(f"❌ Недостаточно монет! Баланс: {balance_now}", mimetype="text/plain; charset=utf-8")

    result = random.choice(["red", "black", "green"])
    colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

    if color not in colors:
        return Response("❌ Укажи цвет: red, black или green", mimetype="text/plain; charset=utf-8")

    # Определяем выигрыш
    if color == result:
        multiplier = 14 if result == "green" else 2
        win = bet * (multiplier - 1)
        new_balance = update_balance(user, win)
        outcome = f"✅ Победа! | +{win}"
    else:
        new_balance = update_balance(user, -bet)
        outcome = f"❌ Проигрыш | -{bet}"

    text = (
        f"🎰 @{user} ставит {bet} на {colors[color]}! "
        f"Выпало {colors[result]} — {outcome} | Баланс: {new_balance}"
    )

    return Response(text, mimetype="text/plain; charset=utf-8")

# === Автобэкап каждые 5 минут (на всякий случай) ===
def autosave_loop():
    while True:
        with LOCK:
            balances = load_balances()
            save_balances(balances)
        time.sleep(300)

threading.Thread(target=autosave_loop, daemon=True).start()

# === Запуск ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
