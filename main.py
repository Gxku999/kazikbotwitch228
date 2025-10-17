from flask import Flask, request, Response
import json, os, random

app = Flask(__name__)

BALANCES_FILE = "balances.json"
START_BALANCE = 1500

# Загружаем баланс из файла
if os.path.exists(BALANCES_FILE):
    with open(BALANCES_FILE, "r", encoding="utf-8") as f:
        balances = json.load(f)
else:
    balances = {}

def save_balances():
    with open(BALANCES_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

@app.route("/")
def home():
    return Response("🎰 Casino bot is running", mimetype="text/plain; charset=utf-8")

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    if not user:
        return Response("❌ Не указан пользователь.", mimetype="text/plain; charset=utf-8")

    bal = balances.get(user, START_BALANCE)
    balances[user] = bal
    save_balances()

    return Response(f"💰 Баланс @{user}: {bal} монет", mimetype="text/plain; charset=utf-8")

@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    try:
        bet = int(request.args.get("bet", "0"))
    except ValueError:
        return Response("❌ Ставка должна быть числом!", mimetype="text/plain; charset=utf-8")

    if not user:
        return Response("❌ Не указан пользователь.", mimetype="text/plain; charset=utf-8")

    balances[user] = balances.get(user, START_BALANCE)

    if bet <= 0:
        return Response("❌ Минимальная ставка — 1 монета!", mimetype="text/plain; charset=utf-8")
    if bet > balances[user]:
        return Response(f"❌ Недостаточно монет! Баланс: {balances[user]}", mimetype="text/plain; charset=utf-8")

    result = random.choice(["red", "black", "green"])
    colors = {"red": "🟥", "black": "⬛", "green": "🟩"}

    if color not in colors:
        return Response("❌ Укажи цвет: red / black / green", mimetype="text/plain; charset=utf-8")

    if color == result:
        win = bet * (14 if result == "green" else 2) - bet
        balances[user] += win
        outcome = f"✅ Победа! +{win}"
    else:
        balances[user] -= bet
        outcome = "❌ Проигрыш"

    save_balances()

    text = f"🎰 @{user} ставит {bet} на {colors[color]}! Выпало {colors[result]} — {outcome} | Баланс: {balances[user]}"
    return Response(text, mimetype="text/plain; charset=utf-8")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
