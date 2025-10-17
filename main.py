from flask import Flask, request
import random, json, os, datetime, time

app = Flask(__name__)

DATA_FILE = "balances.json"
STATS_FILE = "stats.json"
BONUS_FILE = "bonuses.json"
WATCH_FILE = "watchtime.json"

START_BALANCE = 1000
DAILY_BONUS = 500
WATCH_REWARD = 500
WATCH_INTERVAL = 15 * 60  # 15 минут в секундах

def load_json(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

balances = load_json(DATA_FILE)
stats = load_json(STATS_FILE)
bonuses = load_json(BONUS_FILE)
watchtime = load_json(WATCH_FILE)

def get_balance(user):
    if user not in balances:
        balances[user] = START_BALANCE
        save_json(DATA_FILE, balances)
    return balances[user]

def reward_watchtime(user):
    now = time.time()
    last_time = watchtime.get(user, 0)
    if now - last_time >= WATCH_INTERVAL:
        balances[user] = get_balance(user) + WATCH_REWARD
        watchtime[user] = now
        save_json(DATA_FILE, balances)
        save_json(WATCH_FILE, watchtime)
        return f"⏱ {user} получает {WATCH_REWARD} монет за активность на стриме! 🎁 Баланс: {balances[user]}"
    return None

@app.route("/roll")
def roll():
    user = request.args.get("user")
    color = (request.args.get("color") or "").lower()
    bet = request.args.get("bet")

    if not user or not color or not bet:
        return "❌ Используй: !roll [red/black/green] [ставка]"

    try:
        bet = int(bet)
    except ValueError:
        return "❌ Ставка должна быть числом!"

    balance = get_balance(user)
    if bet > balance:
        return f"💸 Недостаточно монет! Баланс: {balance}"

    reward_msg = reward_watchtime(user)

    balances[user] -= bet

    result = random.choices(["red", "black", "green"], weights=[48, 48, 4])[0]
    multiplier = 14 if result == "green" else 2

    if result == color:
        win = bet * multiplier
        balances[user] += win
        stats.setdefault(user, {"wins": 0, "losses": 0})
        stats[user]["wins"] += 1
        msg = f"🎰 {user} ставит {bet} на {color}! Выпало {result} — 🤑 Победа! +{win - bet} монет | Баланс: {balances[user]}"
    else:
        stats.setdefault(user, {"wins": 0, "losses": 0})
        stats[user]["losses"] += 1
        msg = f"🎰 {user} ставит {bet} на {color}! Выпало {result} — ❌ Проигрыш | Баланс: {balances[user]}"

    save_json(DATA_FILE, balances)
    save_json(STATS_FILE, stats)

    if reward_msg:
        msg += f"\n{reward_msg}"

    return msg


@app.route("/balance")
def balance():
    user = request.args.get("user")
    if not user:
        return "❌ Укажи имя пользователя!"

    reward_msg = reward_watchtime(user)
    bal = get_balance(user)
    msg = f"💰 Баланс {user}: {bal} монет"
    if reward_msg:
        msg += f"\n{reward_msg}"
    return msg


@app.route("/bonus")
def bonus():
    user = request.args.get("user")
    if not user:
        return "❌ Укажи имя пользователя!"

    today = datetime.date.today().isoformat()
    last_claim = bonuses.get(user)

    if last_claim == today:
        return "🎁 Ты уже получал бонус сегодня! Возвращайся завтра!"

    bonuses[user] = today
    balances[user] = get_balance(user) + DAILY_BONUS

    save_json(BONUS_FILE, bonuses)
    save_json(DATA_FILE, balances)

    return f"🎁 {user} получает ежедневный бонус {DAILY_BONUS} монет! Баланс: {balances[user]}"


@app.route("/top")
def top():
    if not balances:
        return "😴 Ещё никто не играл!"

    top_players = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "🏆 Топ игроков:\n" + "\n".join([f"{i+1}. {u} — {b} монет" for i, (u, b) in enumerate(top_players)])
    return msg


@app.route("/stats")
def user_stats():
    user = request.args.get("user")
    if not user:
        return "❌ Укажи имя пользователя!"

    reward_msg = reward_watchtime(user)
    s = stats.get(user, {"wins": 0, "losses": 0})
    total = s["wins"] + s["losses"]
    winrate = (s["wins"] / total * 100) if total > 0 else 0
    msg = f"📊 Статистика {user}: Побед — {s['wins']}, Поражений — {s['losses']} (WinRate: {winrate:.1f}%)"
    if reward_msg:
        msg += f"\n{reward_msg}"
    return msg


@app.route("/")
def home():
    return "🎰 Twitch Casino Bot — активность, бонусы и рулетка работают!"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
