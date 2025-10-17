# main.py
from flask import Flask, request, Response
import json, os, time, random, threading

app = Flask(__name__)

# ------------- CONFIG -------------
BALANCES_FILE = os.environ.get("BALANCES_FILE", "balances.json")
LOCK = threading.Lock()
START_BALANCE = 1500
BONUS_AMOUNT = 500
BONUS_INTERVAL = 15 * 60  # 15 minutes in seconds
TOP_N = 10

# ------------- Utilities -------------
def log(s):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {s}", flush=True)

def abs_path(p):
    return os.path.abspath(p)

def load_file():
    path = abs_path(BALANCES_FILE)
    if not os.path.exists(path):
        # create empty file
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            log(f"Created balances file at {path}")
        except Exception as e:
            log(f"Error creating balances file {path}: {e}")
            return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception as e:
        log(f"Error reading balances file {path}: {e}")
        return {}

def save_file_atomic(data):
    path = abs_path(BALANCES_FILE)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        log(f"Saved balances to {path} (size {os.path.getsize(path)} bytes)")
        return True
    except Exception as e:
        log(f"Error saving balances: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except:
            pass
        return False

def text(msg):
    # plain text UTF-8 so StreamElements prints it directly
    return Response(msg, mimetype="text/plain; charset=utf-8")

# ------------- Core operations (thread-safe) -------------
def get_balances_locked():
    # always read fresh copy from disk
    return load_file()

def get_balance(user):
    u = (user or "").strip().lower()
    data = load_file()
    if u == "":
        return None
    if u not in data:
        data[u] = {"balance": START_BALANCE, "wins": 0, "losses": 0, "last_bonus": 0}
        save_file_atomic(data)
    return data[u]["balance"]

def update_balance(user, delta):
    u = (user or "").strip().lower()
    with LOCK:
        data = load_file()
        if u == "":
            return None
        if u not in data:
            data[u] = {"balance": START_BALANCE, "wins": 0, "losses": 0, "last_bonus": 0}
        data[u]["balance"] = max(0, int(data[u].get("balance", START_BALANCE)) + int(delta))
        save_file_atomic(data)
        return data[u]["balance"]

def set_balance(user, new_value):
    u = (user or "").strip().lower()
    with LOCK:
        data = load_file()
        if u == "":
            return None
        data[u] = data.get(u, {"balance": START_BALANCE, "wins":0, "losses":0, "last_bonus":0})
        data[u]["balance"] = max(0, int(new_value))
        save_file_atomic(data)
        return data[u]["balance"]

def add_win(user):
    u = (user or "").strip().lower()
    with LOCK:
        data = load_file()
        data[u] = data.get(u, {"balance": START_BALANCE, "wins":0, "losses":0, "last_bonus":0})
        data[u]["wins"] = data[u].get("wins",0) + 1
        save_file_atomic(data)

def add_loss(user):
    u = (user or "").strip().lower()
    with LOCK:
        data = load_file()
        data[u] = data.get(u, {"balance": START_BALANCE, "wins":0, "losses":0, "last_bonus":0})
        data[u]["losses"] = data[u].get("losses",0) + 1
        save_file_atomic(data)

def try_grant_activity_bonus(user):
    u = (user or "").strip().lower()
    now = int(time.time())
    with LOCK:
        data = load_file()
        data[u] = data.get(u, {"balance": START_BALANCE, "wins":0, "losses":0, "last_bonus":0})
        last = int(data[u].get("last_bonus", 0))
        if now - last >= BONUS_INTERVAL:
            data[u]["balance"] = data[u].get("balance", START_BALANCE) + BONUS_AMOUNT
            data[u]["last_bonus"] = now
            save_file_atomic(data)
            return True, data[u]["balance"]
        else:
            return False, (BONUS_INTERVAL - (now - last))

# ------------- Routes -------------
@app.route("/")
def home():
    return text("✅ Casino bot running")

@app.route("/debug")
def debug():
    path = abs_path(BALANCES_FILE)
    data = load_file()
    try:
        mtime = time.ctime(os.path.getmtime(path))
    except:
        mtime = "no-file"
    s = f"balances_path: {path}\nlast_modified: {mtime}\n\ncontents:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    return text(s)

@app.route("/balance")
def route_balance():
    user_raw = request.args.get("user", "").strip()
    if not user_raw:
        return text("❌ Укажи ник: !balance")
    user = user_raw.lower()
    # grant activity-bonus when checking balance (optional)
    got, info = try_grant_activity_bonus(user)
    bal = get_balance(user)
    if got:
        return text(f"💰 Баланс {user_raw}: {bal} монет\n⏱ {user_raw} получает {BONUS_AMOUNT} монет за активность!")
    return text(f"💰 Баланс {user_raw}: {bal} монет")

@app.route("/roll")
def route_roll():
    user_raw = request.args.get("user", "").strip()
    color = (request.args.get("color") or "").strip().lower()
    bet_raw = (request.args.get("bet") or "").strip()

    if not user_raw:
        return text("❌ Укажи ник: !roll <color> <amount>")
    if color not in ("red","black","green"):
        return text("❌ Цвет должен быть red, black или green")
    try:
        bet = int(bet_raw)
    except:
        return text("❌ Ставка должна быть целым числом!")

    user = user_raw.lower()
    balance_now = get_balance(user)
    if bet <= 0:
        return text("❌ Ставка должна быть > 0")
    if bet > balance_now:
        return text(f"💸 {user_raw}, недостаточно монет! Баланс: {balance_now}")

    # Снимаем ставку сразу
    new_bal = update_balance(user, -bet)

    # Рулетка
    result = random.choices(["red","black","green"], weights=[48,48,4], k=1)[0]

    if result == color:
        multiplier = 14 if color == "green" else 2
        payout = bet * multiplier
        # добавляем выплату (ставка уже снята)
        new_bal = update_balance(user, payout)
        add_win(user)
        net = payout - bet
        outcome_text = f"✅ Победа! | +{net}"
    else:
        add_loss(user)
        outcome_text = f"❌ Проигрыш | -{bet}"

    # emojis
    emojis = {"red":"🟥","black":"⬛","green":"🟩"}
    return text(f"🎰 {user_raw} ставит {bet} на {emojis[color]}! Выпало {emojis[result]} — {outcome_text} | Баланс: {new_bal}")

@app.route("/bonus")
def route_bonus():
    user_raw = request.args.get("user", "").strip()
    if not user_raw:
        return text("❌ Укажи ник: !bonus")
    user = user_raw.lower()
    ok, info = try_grant_activity_bonus(user)
    if ok:
        return text(f"🎁 {user_raw} получил {BONUS_AMOUNT} монет! Баланс: {info}")
    else:
        remain = int(info)
        mins = remain // 60
        secs = remain % 60
        return text(f"⏳ {user_raw}, бонус можно получить через {mins} мин {secs} сек")

@app.route("/top")
def route_top():
    data = load_file()
    if not data:
        return text("🏆 Топ пуст")
    ranked = sorted(data.items(), key=lambda x: x[1].get("balance",0), reverse=True)[:TOP_N]
    lines = [f"{i+1}. {name} — {info.get('balance',0)}" for i,(name,info) in enumerate(ranked, start=1)]
    return text("🏆 Топ игроков:\n" + "\n".join(lines))

@app.route("/stats")
def route_stats():
    user_raw = request.args.get("user", "").strip()
    if not user_raw:
        return text("❌ Укажи ник: !stats")
    user = user_raw.lower()
    data = load_file()
    if user not in data:
        return text(f"❌ Нет данных о {user_raw}")
    info = data[user]
    wins = info.get("wins",0)
    losses = info.get("losses",0)
    bal = info.get("balance", START_BALANCE)
    return text(f"📊 Статистика {user_raw}: Победы — {wins}, Поражения — {losses}, Баланс — {bal}")

# admin endpoint: /admin?user=<caller>&target=<nick>&action=add/remove/set&amount=123
@app.route("/admin")
def route_admin():
    caller = (request.args.get("user") or "").strip().lower()
    allowed = [x.strip().lower() for x in os.environ.get("ADMINS","gxku999").split(",") if x.strip()]
    if caller not in allowed:
        return text("⛔ У вас нет прав администратора")
    target_raw = (request.args.get("target") or "").strip()
    action = (request.args.get("action") or "").strip().lower()
    amount_raw = (request.args.get("amount") or "").strip()
    if not target_raw or not action or not amount_raw:
        return text("❌ Использование: /admin?user=<you>&target=<nick>&action=add|remove|set&amount=<num>")
    try:
        amount = int(amount_raw)
    except:
        return text("❌ Сумма должна быть целым числом!")
    target = target_raw.lower()
    if action == "add":
        new = update_balance(target, amount)
        return text(f"✅ Добавлено {amount} монет {target_raw}. Новый баланс: {new}")
    elif action == "remove":
        new = update_balance(target, -amount)
        return text(f"✅ Списано {amount} монет у {target_raw}. Новый баланс: {new}")
    elif action == "set":
        new = set_balance(target, amount)
        return text(f"✅ Баланс {target_raw} установлен: {new}")
    else:
        return text("❌ Действие должно быть add/remove/set")

# ------------- Run -------------
if __name__ == "__main__":
    # ensure file exists
    load_file()
    log(f"Service started. balances_file={abs_path(BALANCES_FILE)}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
