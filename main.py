# -*- coding: utf-8 -*-
from flask import Flask, request, Response
import random, json, os, time, datetime

app = Flask(__name__)

# ---------------- CONFIG ----------------
DATA_FILE = "balances.json"
STATS_FILE = "stats.json"
BONUS_FILE = "bonuses.json"
WATCH_FILE = "watchtime.json"

START_BALANCE = 1000
DAILY_BONUS = 500
WATCH_REWARD = 500
WATCH_INTERVAL = 15 * 60  # 15 minutes

# Админы (никнеймы Twitch) — впиши свои ники сюда
ADMINS = ["Gxku999", "*"]

# Эмодзи для цветов
COLOR_EMOJI = {
    "red": "🟥",
    "black": "⬛",
    "green": "🟩"
}
# ----------------------------------------

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

balances = load_json(DATA_FILE)
stats = load_json(STATS_FILE)
bonuses = load_json(BONUS_FILE)
watchtime = load_json(WATCH_FILE)

def text_response(msg: str):
    return Response(msg, content_type="text/plain; charset=utf-8")

def ensure_user(user: str):
    if user not in balances:
        balances[user] = START_BALANCE
    if user not in stats:
        stats[user] = {"wins": 0, "losses": 0}
    # no autosave here; caller decides when to save

def get_balance(user: str):
    ensure_user(user)
    return balances[user]

def reward_watchtime(user: str):
    """Если прошло >= WATCH_INTERVAL с последней награды — начислить WATCH_REWARD"""
    now = time.time()
    last = watchtime.get(user, 0)
    if now - last >= WATCH_INTERVAL:
        ensure_user(user)
        balances[user] = get_balance(user) + WATCH_REWARD
        watchtime[user] = now
        save_json(DATA_FILE, balances)
        save_json(WATCH_FILE, watchtime)
        return f"⏱ {user} получает {WATCH_REWARD} монет за активность на стриме! 🎁 Баланс: {balances[user]}"
    return None

@app.route("/roll")
def roll():
    user = (request.args.get("user") or "").strip()
    color = (request.args.get("color") or "").lower().strip()
    bet_raw = request.args.get("bet") or ""

    # Basic validation
    if not user or not color or not bet_raw:
        return text_response("❌ Использование: !roll [red|black|green] [ставка]")

    # Protect against 'null' / 'None' strings commonly from template engines
    if bet_raw.lower() in ("null", "none", ""):
        return text_response("❌ Ставка должна быть числом! Пример: !roll red 100")

    try:
        bet = int(bet_raw)
    except ValueError:
        return text_response("❌ Ставка должна быть целым числом! Пример: !roll red 100")

    if color not in COLOR_EMOJI:
        return text_response("❌ Цвет должен быть red, black или green!")

    ensure_user(user)
    balance = get_balance(user)
    if bet <= 0:
        return text_response("❌ Ставка должна быть положительным числом!")
    if bet > balance:
        return text_response(f"💸 Недостаточно монет! Баланс: {balance}")

    # попытка начисления за просмотр (если прошло >=15 минут)
    reward_msg = reward_watchtime(user)

    # списываем ставку
    balances[user] = balance - bet

    # Рулетка: вероятность реализована с весами (пример)
    result = random.choices(["red", "black", "green"], weights=[48, 48, 4])[0]
    multiplier = 14 if result == "green" else 2

    if result == color:
        # выигрыш: возвращаем ставку + выигрыш (умножаем на multiplier)
        win_total = bet * multiplier
        balances[user] += win_total
        stats.setdefault(user, {"wins": 0, "losses": 0})
        stats[user]["wins"] += 1
        delta = win_total - bet  # чистый выигрыш
        left_bal = balances[user]
        msg = f"{COLOR_EMOJI[color]} {user} ставит {bet} на {COLOR_EMOJI[color]}! Выпало {COLOR_EMOJI[result]} — 🤑 Победа! +{delta} | Баланс: {left_bal}"
    else:
        stats.setdefault(user, {"wins": 0, "losses": 0})
        stats[user]["losses"] += 1
        left_bal = balances[user]
        msg = f"{COLOR_EMOJI[color]} {user} ставит {bet} на {COLOR_EMOJI[color]}! Выпало {COLOR_EMOJI[result]} — ❌ Проигрыш | Баланс: {left_bal}"

    save_json(DATA_FILE, balances)
    save_json(STATS_FILE, stats)

    if reward_msg:
        msg = msg + "\n" + reward_msg

    return text_response(msg)

@app.route("/balance")
def balance():
    user = (request.args.get("user") or "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя! Пример: /balance?user=Nickname")
    reward_msg = reward_watchtime(user)
    ensure_user(user)
    bal = balances[user]
    msg = f"💰 Баланс {user}: {bal} монет"
    if reward_msg:
        msg = msg + "\n" + reward_msg
    return text_response(msg)

@app.route("/bonus")
def bonus():
    user = (request.args.get("user") or "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя! Пример: /bonus?user=Nickname")

    today = datetime.date.today().isoformat()
    last = bonuses.get(user)
    if last == today:
        return text_response("🎁 Бонус уже получен сегодня! Возвращайся завтра.")
    ensure_user(user)
    balances[user] = get_balance(user) + DAILY_BONUS
    bonuses[user] = today
    save_json(BONUS_FILE, bonuses)
    save_json(DATA_FILE, balances)
    return text_response(f"🎁 {user} получает ежедневный бонус {DAILY_BONUS} монет! Баланс: {balances[user]}")

@app.route("/top")
def top():
    if not balances:
        return text_response("😴 Ещё никто не играл!")
    top_players = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:5]
    lines = [f"🏆 Топ игроков:"]
    for i, (name, bal) in enumerate(top_players, start=1):
        lines.append(f"{i}. {name} — {bal}")
    return text_response("\n".join(lines))

@app.route("/stats")
def stats_route():
    user = (request.args.get("user") or "").strip()
    if not user:
        return text_response("❌ Укажи имя пользователя! Пример: /stats?user=Nickname")
    reward_msg = reward_watchtime(user)
    s = stats.get(user, {"wins": 0, "losses": 0})
    total = s["wins"] + s["losses"]
    winrate = (s["wins"] / total * 100) if total > 0 else 0.0
    msg = f"📊 Статистика {user}: Побед — {s['wins']}, Поражений — {s['losses']} (WinRate: {winrate:.1f}%)"
    if reward_msg:
        msg = msg + "\n" + reward_msg
    return text_response(msg)

@app.route("/admin")
def admin():
    """
    Пример вызова (через StreamElements admin команду):
    /admin?user=AdminNick&target=TargetNick&amount=1000
    Только ники из ADMINS могут использовать эндпоинт.
    Этот эндпоинт ТОЛЬКО ДОБАВЛЯЕТ (накручивает) баланс.
    """
    user = (request.args.get("user") or "").strip()     # кто вызывает (должен быть в ADMINS)
    target = (request.args.get("target") or "").strip() # кому добавляем
    amount_raw = request.args.get("amount") or ""

    if not user or not target or not amount_raw:
        return text_response("❌ Использование: /admin?user=YourAdminNick&target=Nick&amount=1000")

    # проверка прав
    if user not in ADMINS:
        return text_response("🚫 У тебя нет прав администратора!")

    # проверка суммы
    try:
        amount = int(amount_raw)
    except ValueError:
        return text_response("❌ Сумма должна быть целым числом!")

    if amount <= 0:
        return text_response("❌ Сумма должна быть больше нуля!")

    ensure_user(target)
    balances[target] = get_balance(target) + amount
    save_json(DATA_FILE, balances)

    return text_response(f"✅ Админ {user} добавил {amount} монет игроку {target}. Новый баланс: {balances[target]}")

@app.route("/")
def home():
    return text_response("🎰 Casino API работает!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
