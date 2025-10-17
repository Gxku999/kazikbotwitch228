# -*- coding: utf-8 -*-
from flask import Flask, request, Response
import requests, base64, json, os, time, random, traceback

app = Flask(__name__)

# --- CONFIG: установи в Render environment variables ---
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")        # ghp_xxx
GITHUB_REPO  = os.getenv("GITHUB_REPO")         # "username/repo"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
GITHUB_FILE = "balances.json"

# поведение
START_BALANCE = 1500
BONUS_COINS = 500
BONUS_INTERVAL = 15 * 60   # 15 минут

COLORS = {"red": "🟥", "black": "⬛", "green": "🟩"}

# ---------------- GitHub helpers ----------------
def gh_headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }

def load_balances():
    """Скачивает balances.json из GitHub и парсит. Всегда возвращает dict."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}?ref={GITHUB_BRANCH}"
        r = requests.get(url, headers=gh_headers(), timeout=15)
        if r.status_code == 200:
            payload = r.json()
            content = base64.b64decode(payload["content"]).decode("utf-8")
            return json.loads(content)
        else:
            # Если файла нет или другая ошибка — возвращаем пустой словарь
            print("GH load_balances status:", r.status_code, r.text)
            return {}
    except Exception:
        print("Exception in load_balances:", traceback.format_exc())
        return {}

def save_balances(data):
    """Заливка/обновление balances.json в GitHub (PUT)."""
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        r = requests.get(url, headers=gh_headers(), timeout=15)
        sha = None
        if r.status_code == 200:
            sha = r.json().get("sha")

        content = json.dumps(data, ensure_ascii=False, indent=4)
        encoded = base64.b64encode(content.encode()).decode()

        payload = {
            "message": "update balances.json",
            "content": encoded,
            "branch": GITHUB_BRANCH
        }
        if sha:
            payload["sha"] = sha

        resp = requests.put(url, headers=gh_headers(), json=payload, timeout=15)
        if resp.status_code not in (200,201):
            print("GH save error:", resp.status_code, resp.text)
            # не выбрасываем исключение — чтобы сервис не упал, логим и продолжаем
        return True
    except Exception:
        print("Exception in save_balances:", traceback.format_exc())
        return False

# ---------------- utilities ----------------
def text_response(msg: str):
    """Возвращаем plain text (чтобы StreamElements показывал текст, а не JSON)."""
    return Response(msg, mimetype="text/plain; charset=utf-8")

def norm_user(u: str) -> str:
    return (u or "").strip().lower()

# ---------------- route handlers ----------------

@app.route("/")
def home():
    return text_response("🎰 Casino bot (GitHub-backed) is running")

@app.route("/balance")
def balance_route():
    user_raw = request.args.get("user") or ""
    user = norm_user(user_raw)
    if not user:
        return text_response("❌ Укажи ник: !balance")

    data = load_balances()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "wins": 0, "losses": 0, "last_active": 0}
        save_balances(data)

    bal = data[user]["balance"]
    return text_response(f"💰 Баланс {user_raw}: {bal} монет")

@app.route("/bonus")
def bonus_route():
    user_raw = request.args.get("user") or ""
    user = norm_user(user_raw)
    if not user:
        return text_response("❌ Укажи ник: !bonus")

    data = load_balances()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "wins": 0, "losses": 0, "last_active": 0, "last_bonus": 0}

    now = int(time.time())
    last = int(data[user].get("last_bonus", 0))
    if now - last >= BONUS_INTERVAL:
        data[user]["balance"] = data[user].get("balance", START_BALANCE) + BONUS_COINS
        data[user]["last_bonus"] = now
        save_balances(data)
        return text_response(f"🎁 {user_raw} получил бонус {BONUS_COINS} монет! Баланс: {data[user]['balance']}")
    else:
        remain = BONUS_INTERVAL - (now - last)
        mins = remain // 60
        return text_response(f"⏳ {user_raw}, бонус можно получить через {mins} минут")

@app.route("/roll")
def roll_route():
    # используем параметры, которые StreamElements должен подставлять:
    # user (ник) - мы рекомендуем ${sender} в шаблоне
    user_raw = request.args.get("user") or ""
    color_in = request.args.get("color") or ""
    bet_raw = request.args.get("bet") or ""

    # Нормализуем
    user = norm_user(user_raw)
    color = (color_in or "").strip().lower()
    try:
        bet = int(bet_raw)
    except:
        return text_response("❌ Ставка должна быть целым числом! Пример: !roll red 100")

    if not user:
        return text_response("❌ Укажи ник! Пример: !roll red 100")
    if color not in COLORS:
        return text_response("❌ Цвет должен быть red, black или green!")
    if bet <= 0:
        return text_response("❌ Ставка должна быть положительной!")

    # Загружаем актуальные данные
    data = load_balances()
    if user not in data:
        data[user] = {"balance": START_BALANCE, "wins": 0, "losses": 0, "last_active": 0, "last_bonus": 0}

    # Проверяем баланс
    if data[user]["balance"] < bet:
        return text_response(f"💸 {user_raw}, недостаточно монет! Баланс: {data[user]['balance']}")

    # Снимаем ставку сразу
    data[user]["balance"] -= bet

    # Определяем результат
    result = random.choices(["red", "black", "green"], weights=[48,48,4], k=1)[0]

    # Если игрок угадал — выплатa = bet * multiplier
    if result == color:
        multiplier = 14 if color == "green" else 2
        payout = bet * multiplier
        # добавляем payout (ставка уже снята)
        data[user]["balance"] += payout
        data[user]["wins"] = data[user].get("wins",0) + 1
        net = payout - bet  # чистая прибыль
        outcome = f"✅ Победа! | +{net} | Баланс: {data[user]['balance']}"
    else:
        data[user]["losses"] = data[user].get("losses",0) + 1
        outcome = f"❌ Проигрыш | Баланс: {data[user]['balance']}"

    # Сохраняем изменения в GitHub (и локально в памяти переменной balances не используем)
    save_balances(data)

    # Формируем сообщение (используем оригинальный регистр ника user_raw для вывода)
    msg = f"🎰 {user_raw} ставит {bet} на {COLORS[color]}! Выпало {COLORS[result]} — {outcome}"
    return text_response(msg)

@app.route("/top")
def top_route():
    data = load_balances()
    if not data:
        return text_response("🏆 Пока нет игроков")
    sorted_players = sorted(data.items(), key=lambda x: x[1].get("balance",0), reverse=True)[:10]
    lines = [f"🏆 ТОП 10 игроков:"]
    for i,(name,info) in enumerate(sorted_players, start=1):
        lines.append(f"{i}. {name} — {info.get('balance',0)}")
    return text_response("\n".join(lines))

@app.route("/stats")
def stats_route():
    user_raw = request.args.get("user") or ""
    user = norm_user(user_raw)
    if not user:
        return text_response("❌ Укажи ник: !stats")
    data = load_balances()
    if user not in data:
        return text_response("❌ Нет данных об этом пользователе.")
    wins = data[user].get("wins",0)
    losses = data[user].get("losses",0)
    total = wins + losses
    wr = f"{(wins/total*100):.1f}%" if total>0 else "0%"
    return text_response(f"📊 Статистика {user_raw}: Победы — {wins}, Поражения — {losses}, WinRate — {wr}")

# ---- admin endpoint (only checks caller param; make sure in StreamElements user=${sender}) ----
@app.route("/admin")
def admin_route():
    caller = (request.args.get("user") or "").strip().lower()
    target_raw = request.args.get("target") or ""
    action = (request.args.get("action") or "").strip().lower()
    amount_raw = request.args.get("amount") or ""

    if caller not in [a.lower() for a in (os.getenv("ADMINS","gxku999").split(",") if os.getenv("ADMINS") else ["gxku999"])]:
        return text_response("🚫 У тебя нет прав администратора!")

    if not target_raw or not action or not amount_raw:
        return text_response("❌ Использование: !admin <ник> <add|remove> <сумма>")

    target = norm_user(target_raw)
    try:
        amount = int(amount_raw)
    except:
        return text_response("❌ Сумма должна быть числом!")

    data = load_balances()
    if target not in data:
        data[target] = {"balance": START_BALANCE, "wins":0, "losses":0, "last_active":0, "last_bonus":0}

    if action == "add":
        data[target]["balance"] = data[target].get("balance",START_BALANCE) + amount
        save_balances(data)
        return text_response(f"✅ Админ {caller} добавил {amount} монет игроку {target_raw}. Баланс: {data[target]['balance']}")
    elif action in ("remove","sub","take"):
        data[target]["balance"] = max(0, data[target].get("balance",START_BALANCE) - amount)
        save_balances(data)
        return text_response(f"✅ Админ {caller} снял {amount} монет с игрока {target_raw}. Баланс: {data[target]['balance']}")
    else:
        return text_response("❌ Действие должно быть add или remove")

# ---------------- Run ----------------
if __name__ == "__main__":
    # quick check: env
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("WARNING: GITHUB_TOKEN or GITHUB_REPO not set. GitHub sync will fail.")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "10000")))
