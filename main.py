from flask import Flask, request, jsonify
import json, random, time, os

app = Flask(__name__)

DATA_FILE = "balances.json"
STATS_FILE = "stats.json"
WATCHTIME_FILE = "watchtime.json"
BONUS_FILE = "bonuses.json"

START_BALANCE = 1000
WATCH_REWARD = 500
WATCH_INTERVAL = 15 * 60  # 15 минут
DAILY_BONUS = 500

ADMINS = ["gxku999"]  # твой ник админа в нижнем регистре

# =============== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===============

def load_json(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def norm(user: str):
    return (user or "").strip().lower()

balances = load_json(DATA_FILE)
stats = load_json(STATS_FILE)
watchtime = load_json(WATCHTIME_FILE)
bonuses = load_json(BONUS_FILE)

def ensure_user(user: str):
    u = norm(user)
    if u == "":
        return u
    if u not in balances:
        balances[u] = START_BALANCE
    if u not in stats:
        stats[u] = {"wins": 0, "losses": 0}
    save_json(DATA_FILE, balances)
    save_json(STATS_FILE, stats)
    return u

def get_balance(user: str):
    u = norm(user)
    if u not in balances:
        balances[u] = START_BALANCE
        save_json(DATA_FILE, balances)
    return balances[u]

def set_balance(user: str, amount: int):
    u = ensure_user(user)
    balances[u] = max(0, int(amount))
    save_json(DATA_FILE, balances)
    return balances[u]

def add_balance(user: str, amount: int):
    u = ensure_user(user)
    balances[u] = balances.get(u, START_BALANCE) + int(amount)
    save_json(DATA_FILE, balances)
    return balances[u]

def reward_watchtime(user: str):
    """Выдает награду за активность каждые 15 минут"""
    u = ensure_user(user)
    now = time.time()
    last_time = watchtime.get(u, 0)
    if now - last_time >= WATCH_INTERVAL:
        watchtime[u] = now
        save_json(WATCHTIME_FILE, watchtime)
        add_balance(u, WATCH_REWARD)
        return f"⏱ {user} получает {WATCH_REWARD} монет за активность на стриме! 🎁"
    return ""

def reward_on_command(user_raw):
    """Автонаграда при любой активности"""
    reward_msg = reward_watchtime(user_raw)
    return reward_msg

def text_response(msg):
    return jsonify({"message": msg})

# =============== РУЛЕТКА 🎰 ===============

@app.route("/roulette")
def roulette():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)

    color = (request.args.get("color") or "").lower()
    bet_raw = request.args.get("bet") or ""
    user = ensure_user(user_raw)

    try:
        bet = int(bet_raw)
    except:
        return text_response("❌ Ставка должна быть числом!")

    if bet <= 0:
        return text_response("❌ Ставка должна быть положительной!")
    if bet > get_balance(user):
        return text_response("❌ Недостаточно монет!")

    result = random.choices(["red", "black", "green"], weights=[48, 48, 4])[0]

    color_emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}
    result_emoji = color_emoji.get(result, result)
    color_emoji_str = color_emoji.get(color, color)

    if result == color:
        multiplier = 14 if result == "green" else 2
        win = bet * multiplier
        add_balance(user, win - bet)
        stats[user]["wins"] += 1
        save_json(STATS_FILE, stats)
        msg = f"🎰 {user_raw} ставит {bet} на {color_emoji_str}! Выпало {result_emoji} — 🤑 Победа! +{win - bet} монет | Баланс: {get_balance(user)}"
    else:
        add_balance(user, -bet)
        stats[user]["losses"] += 1
        save_json(STATS_FILE, stats)
        msg = f"🎰 {user_raw} ставит {bet} на {color_emoji_str}! Выпало {result_emoji} — ❌ Проигрыш | Баланс: {get_balance(user)}"

    if reward_msg:
        msg += f"\n{reward_msg}"

    return text_response(msg)

# =============== БАЛАНС 💰 ===============

@app.route("/balance")
def balance():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)
    user = ensure_user(user_raw)
    bal = get_balance(user)
    msg = f"💰 Баланс {user_raw}: {bal} монет"
    if reward_msg:
        msg += f"\n{reward_msg}"
    return text_response(msg)

# =============== БОНУС 🎁 ===============

@app.route("/bonus")
def bonus():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)
    user = ensure_user(user_raw)
    now = time.time()
    last_bonus = bonuses.get(user, 0)
    if now - last_bonus >= 24 * 3600:
        bonuses[user] = now
        save_json(BONUS_FILE, bonuses)
        add_balance(user, DAILY_BONUS)
        msg = f"🎁 {user_raw} получил ежедневный бонус {DAILY_BONUS} монет! Баланс: {get_balance(user)}"
    else:
        hours = int((24 * 3600 - (now - last_bonus)) / 3600)
        msg = f"⏳ {user_raw}, бонус будет доступен через {hours} ч."
    if reward_msg:
        msg += f"\n{reward_msg}"
    return text_response(msg)

# =============== СТАТИСТИКА 📊 ===============

@app.route("/stats")
def stats_route():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)
    user = ensure_user(user_raw)
    s = stats.get(user, {"wins": 0, "losses": 0})
    msg = f"📊 Статистика {user_raw}: Победы — {s['wins']}, Поражения — {s['losses']}"
    if reward_msg:
        msg += f"\n{reward_msg}"
    return text_response(msg)

# =============== ТОП 10 💎 ===============

@app.route("/top")
def top():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)

    if not balances:
        return text_response("📉 Пока никто не играет!")
    sorted_players = sorted(balances.items(), key=lambda x: x[1], reverse=True)
    top10 = sorted_players[:10]
    lines = []
    for i, (name, bal) in enumerate(top10, start=1):
        lines.append(f"{i}. {name} — {bal}")
    msg = "🏆 Топ 10 игроков:\n" + "\n".join(lines)
    if reward_msg:
        msg += f"\n{reward_msg}"
    return text_response(msg)

# =============== АДМИН-КОМАНДЫ 👑 ===============

@app.route("/admin")
def admin():
    user_raw = request.args.get("user") or ""
    reward_msg = reward_on_command(user_raw)

    target_raw = request.args.get("target") or ""
    action = (request.args.get("action") or "add").lower()
    amount_raw = request.args.get("amount") or ""

    user = norm(user_raw)
    target = norm(target_raw)

    if not user or not target or not amount_raw:
        return text_response("❌ Использование: /admin?user=AdminNick&target=Nick&action=add|remove&amount=1000")

    if user not in [a.lower() for a in ADMINS]:
        return text_response("🚫 У тебя нет прав администратора!")

    try:
        amount = int(amount_raw)
    except ValueError:
        return text_response("❌ Сумма должна быть числом!")

    ensure_user(target)

    if action == "add":
        new_balance = add_balance(target, amount)
        msg = f"✅ {user_raw} добавил {amount} монет игроку {target_raw}. Баланс: {new_balance}"
    elif action == "remove":
        new_balance = add_balance(target, -amount)
        msg = f"✅ {user_raw} отнял {amount} монет у {target_raw}. Баланс: {new_balance}"
    else:
        return text_response("❌ Действие должно быть add или remove")

    if reward_msg:
        msg += f"\n{reward_msg}"
    return text_response(msg)

# =============== ГЛАВНАЯ ===============

@app.route("/")
def home():
    return "🎰 Twitch Casino Bot работает!"

# ==========================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
