from flask import Flask, request, Response
import json, os, random, time, base64, requests

app = Flask(__name__)

BONUS_INTERVAL = 900  # 15 минут
BONUS_AMOUNT = 500
START_BALANCE = 1500

# === GitHub Config ===
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")
GITHUB_FILE = os.getenv("GITHUB_FILE", "balances.json")

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

def github_api(path):
    return f"https://api.github.com/repos/{GITHUB_REPO}/{path}"

# === JSON Response с нормальной кодировкой ===
def text_response(msg):
    return Response(json.dumps({"message": msg}, ensure_ascii=False),
                    mimetype="application/json; charset=utf-8")

# === Работа с GitHub ===
def load_balances():
    try:
        r = requests.get(github_api(f"contents/{GITHUB_FILE}"), headers=HEADERS)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            return json.loads(content), r.json()["sha"]
        else:
            print("GitHub load:", r.text)
            return {}, None
    except Exception as e:
        print("Ошибка load_balances:", e)
        return {}, None

def save_balances(data, sha=None):
    try:
        message = "update balances"
        content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": content}
        if sha:
            payload["sha"] = sha
        r = requests.put(github_api(f"contents/{GITHUB_FILE}"), headers=HEADERS, json=payload)
        if r.status_code not in [200, 201]:
            print("GitHub save error:", r.text)
    except Exception as e:
        print("Ошибка save_balances:", e)

# === Балансы ===
def get_balance(user):
    data, sha = load_balances()
    user = user.lower()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "last_bonus": 0}
        save_balances(data, sha)
    return data[user]["balance"], sha

def set_balance(user, new_balance, sha=None):
    data, sha2 = load_balances()
    if not sha:
        sha = sha2
    user = user.lower()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "last_bonus": 0}
    data[user]["balance"] = max(0, int(new_balance))
    save_balances(data, sha)

# === Проверка бонуса ===
def check_bonus(user):
    data, sha = load_balances()
    user = user.lower()
    now = time.time()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "last_bonus": now}
    if now - data[user]["last_bonus"] >= BONUS_INTERVAL:
        data[user]["balance"] += BONUS_AMOUNT
        data[user]["last_bonus"] = now
        save_balances(data, sha)
        return f"⏱ {user} получает {BONUS_AMOUNT} монет за активность на стриме! 🎁"
    return None

# === Рулетка ===
@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    bet = request.args.get("bet", "0")

    emojis = {"red": "🟥", "black": "⬛", "green": "🟩"}
    multipliers = {"red": 2, "black": 2, "green": 14}

    if color not in emojis:
        return text_response("❌ Укажи цвет: red, black или green.")
    try:
        bet = int(bet)
    except:
        return text_response("❌ Ставка должна быть числом.")
    if bet <= 0:
        return text_response("❌ Ставка должна быть больше нуля.")

    balance, sha = get_balance(user)
    if bet > balance:
        return text_response(f"💸 Недостаточно средств! Баланс: {balance}")

    outcome = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]

    if outcome == color:
        win = bet * (multipliers[color] - 1)
        new_balance = balance + win
        result = f"✅ Победа! +{win} | Баланс: {new_balance}"
    else:
        new_balance = balance - bet
        result = f"❌ Проигрыш | Баланс: {new_balance}"

    set_balance(user, new_balance, sha)
    msg = f"🎰 {user} ставит {bet} на {emojis[color]}! Выпало {emojis[outcome]} — {result}"
    return text_response(msg)

# === Баланс ===
@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    bonus_msg = check_bonus(user)
    balance, _ = get_balance(user)
    msg = f"💰 Баланс {user}: {balance} монет"
    if bonus_msg:
        msg += f"\n{bonus_msg}"
    return text_response(msg)

# === Топ 10 ===
@app.route("/top")
def top():
    data, _ = load_balances()
    top_users = sorted(data.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 Топ 10 игроков:\n"
    for i, (user, info) in enumerate(top_users, 1):
        msg += f"{i}. {user} — {info['balance']} монет\n"
    return text_response(msg)

# === Ручной бонус ===
@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    msg = check_bonus(user)
    if not msg:
        msg = f"⏳ {user}, бонус уже получен недавно!"
    return text_response(msg)

@app.route("/")
def home():
    return "✅ Twitch Casino Bot успешно работает и синхронизируется с GitHub!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
