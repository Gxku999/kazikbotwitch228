# main.py
from flask import Flask, request, Response
import threading, json, os, time, random, traceback

app = Flask(__name__)

# Путь к файлу с балансами — можно задать в Render как переменную окружения BALANCE_FILE
BALANCE_FILE = os.environ.get("BALANCE_FILE", "balances.json")
LOCK = threading.Lock()
START_BALANCE = 1500

def log(s):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {s}", flush=True)

def abs_path(p):
    return os.path.abspath(p)

def load_balances():
    path = abs_path(BALANCE_FILE)
    try:
        if not os.path.exists(path):
            log(f"balances file not found, creating: {path}")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                log("balances.json is not an object — resetting")
                return {}
            return data
    except Exception as e:
        log("ERROR load_balances: " + str(e))
        log(traceback.format_exc())
        return {}

def save_balances_atomic(data):
    """Atomic write: write to temp file then replace"""
    path = abs_path(BALANCE_FILE)
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic on Unix
        log(f"Saved balances to {path} (size {os.path.getsize(path)} bytes)")
        return True
    except Exception as e:
        log("ERROR save_balances_atomic: " + str(e))
        log(traceback.format_exc())
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except:
            pass
        return False

def text(msg):
    return Response(msg, mimetype="text/plain; charset=utf-8")

@app.route("/")
def home():
    return text("✅ Casino bot running")

@app.route("/debug")
def debug():
    """Возвращает содержимое файла и время последнего изменения — для диагностики."""
    path = abs_path(BALANCE_FILE)
    data = load_balances()
    mtime = None
    try:
        mtime = time.ctime(os.path.getmtime(path))
    except:
        mtime = "no-file"
    info = f"balances_path: {path}\nlast_modified: {mtime}\n\ncontents:\n{json.dumps(data, ensure_ascii=False, indent=2)}"
    return text(info)

@app.route("/balance")
def balance():
    user = (request.args.get("user") or "").strip()
    if not user:
        return text("❌ Укажи ник: !balance")
    user_key = user.lower()

    with LOCK:
        balances = load_balances()
        bal = balances.get(user_key, START_BALANCE)
        # Ensure entry exists and saved immediately
        balances[user_key] = bal
        saved = save_balances_atomic(balances)
    if not saved:
        return text(f"💰 Баланс {user}: {bal} монет (WARNING: could not save to disk)")
    return text(f"💰 Баланс {user}: {bal} монет")

@app.route("/roll")
def roll():
    user = (request.args.get("user") or "").strip()
    color = (request.args.get("color") or "").strip().lower()
    bet_raw = (request.args.get("bet") or "").strip()

    if not user:
        return text("❌ Укажи ник: !roll <color> <amount>")
    if color not in ("red", "black", "green"):
        return text("❌ Цвет должен быть red, black или green!")
    try:
        bet = int(bet_raw)
    except:
        return text("❌ Ставка должна быть числом!")

    user_key = user.lower()

    with LOCK:
        balances = load_balances()
        current = balances.get(user_key, START_BALANCE)
        if bet <= 0:
            return text("❌ Ставка должна быть больше 0!")
        if bet > current:
            return text(f"❌ Недостаточно монет! Баланс: {current}")

        # Снимаем ставку сразу
        current -= bet

        # Рулетка
        result = random.choices(["red", "black", "green"], weights=[48,48,4], k=1)[0]

        if result == color:
            multiplier = 14 if color == "green" else 2
            payout = bet * multiplier
            # игрок уже потерял ставку, добавляем payout
            current += payout
            net = payout - bet
            outcome = f"✅ Победа! | +{net}"
        else:
            outcome = f"❌ Проигрыш | -{bet}"

        balances[user_key] = current
        ok = save_balances_atomic(balances)

    if not ok:
        return text(f"🎰 {user} ставит {bet} на {color}! Выпало {result} — {outcome} | Баланс: {current} (WARNING: save failed)")

    return text(f"🎰 {user} ставит {bet} на {color} ({'🟥' if color=='red' else '⬛' if color=='black' else '🟩'})! Выпало {'🟥' if result=='red' else '⬛' if result=='black' else '🟩'} — {outcome} | Баланс: {current}")

@app.route("/top")
def top():
    with LOCK:
        balances = load_balances()
    if not balances:
        return text("🏆 Топ пуст")
    top10 = sorted(balances.items(), key=lambda x: x[1], reverse=True)[:10]
    lines = [f"{i+1}. {u} — {b}" for i,(u,b) in enumerate(top10, start=1)]
    return text("🏆 Топ:\n" + "\n".join(lines))

# Admin endpoint for manual change (use only if you trust caller)
@app.route("/admin")
def admin():
    caller = (request.args.get("user") or "").strip().lower()
    # set ADMIN list via env ADMINS="nick1,nick2"
    allowed = [x.strip().lower() for x in os.environ.get("ADMINS","gxku999").split(",") if x.strip()]
    if caller not in allowed:
        return text("⛔ Нет доступа.")
    target = (request.args.get("target") or "").strip().lower()
    action = (request.args.get("action") or "").strip().lower()
    amount_raw = (request.args.get("amount") or "").strip()
    try:
        amount = int(amount_raw)
    except:
        return text("❌ Сумма должна быть числом!")
    if not target:
        return text("❌ Укажи цель.")
    with LOCK:
        balances = load_balances()
        balances[target] = balances.get(target, START_BALANCE)
        if action == "add":
            balances[target] += amount
        elif action == "remove":
            balances[target] = max(0, balances[target] - amount)
        else:
            return text("❌ Action must be add/remove")
        ok = save_balances_atomic(balances)
    if not ok:
        return text(f"⚠️ Изменено локально, но не сохранено. {target}: {balances[target]}")
    return text(f"✅ {target} баланс: {balances[target]}")

if __name__ == "__main__":
    # старт: убедимся, что файл есть
    load_balances()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
