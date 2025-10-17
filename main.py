import json
import random
import time
import os
import subprocess
from flask import Flask, request, Response

app = Flask(__name__)

# === Настройки ===
LOCAL_FILE = "balances.json"
DEFAULT_BALANCE = 1500
BONUS_AMOUNT = 500
BONUS_INTERVAL = 15 * 60  # 15 минут

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # пример: gxku999/kazikbot
GITHUB_USER = os.getenv("GITHUB_USER")

LAST_PUSH = 0
PUSH_INTERVAL = 300  # 5 минут

def save_balances():
    global LAST_PUSH
    try:
        with open(LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(balances, f, ensure_ascii=False, indent=2)
        log(f"💾 Сохранено {LOCAL_FILE}")

        now = time.time()
        if now - LAST_PUSH >= PUSH_INTERVAL:
            subprocess.run(["git", "add", LOCAL_FILE])
            subprocess.run(["git", "commit", "-m", "update balances.json"], check=False)
            subprocess.run([
                "git", "push",
                f"https://{os.getenv('GITHUB_USER')}:{os.getenv('GITHUB_TOKEN')}@github.com/{os.getenv('GITHUB_REPO')}.git",
                "HEAD:main"
            ], check=False)
            LAST_PUSH = now
            log("✅ balances.json синхронизирован с GitHub.")
        else:
            log("⏳ Пропуск пуша (слишком рано).")

    except Exception as e:
        log(f"⚠️ Ошибка сохранения файла: {e}")



# === Вспомогательные функции ===
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def text_response(message):
    return Response(message, content_type="text/plain; charset=utf-8")

def load_balances():
    if os.path.exists(LOCAL_FILE):
        try:
            with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"⚠ Ошибка чтения {LOCAL_FILE}: {e}")
    return {}

def save_balances():
    try:
        with open(LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(balances, f, ensure_ascii=False, indent=2)
        log(f"💾 balances.json сохранён локально.")
        push_to_github()
    except Exception as e:
        log(f"⚠ Ошибка при сохранении: {e}")

def push_to_github():
    if not (GITHUB_TOKEN and GITHUB_REPO and GITHUB_USER):
        log("⚠ Нет данных GitHub, пропуск синхронизации.")
        return
    try:
        repo_url = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"
        subprocess.run(["git", "config", "--global", "user.email", "bot@render.local"])
        subprocess.run(["git", "config", "--global", "user.name", "Render Bot"])
        subprocess.run(["git", "add", LOCAL_FILE])
        subprocess.run(["git", "commit", "-m", f"update balances.json {time.strftime('%H:%M:%S')}"], check=False)
        subprocess.run(["git", "push", repo_url, "HEAD:main"], check=False)
        log("✅ balances.json синхронизирован с GitHub.")
    except Exception as e:
        log(f"⚠ Ошибка при push в GitHub: {e}")

# === Загрузка ===
balances = load_balances()
log("✅ Бот запущен, баланс загружен.")

# === Логика ===
def ensure_user(user):
    user = user.lower()
    if user not in balances:
        balances[user] = {"balance": DEFAULT_BALANCE, "last_bonus": 0}
        save_balances()
    return user

@app.route("/")
def home():
    return text_response("✅ Twitch Casino Bot работает!")

@app.route("/balance")
def balance():
    user = request.args.get("user", "").strip().lower()
    if not user:
        return text_response("❌ Укажи имя пользователя (?user=...)")
    u = ensure_user(user)
    bal = balances[u]["balance"]
    return text_response(f"💰 Баланс {user}: {bal} монет")

@app.route("/roll")
def roll():
    user = request.args.get("user", "").strip().lower()
    color = request.args.get("color", "").strip().lower()
    bet_str = request.args.get("bet", "").strip()
    if not user or not color or not bet_str:
        return text_response("❌ Формат: /roll?user=ник&color=red|black|green&bet=100")

    try:
        bet = int(bet_str)
    except:
        return text_response("❌ Ставка должна быть числом")

    if bet <= 0:
        return text_response("❌ Минимальная ставка — 1 монета")

    u = ensure_user(user)
    bal = balances[u]["balance"]
    if bal < bet:
        return text_response(f"❌ Недостаточно средств! Баланс: {bal}")

    outcome = random.choices(["red", "black", "green"], weights=[47, 47, 6])[0]
    emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}[outcome]
    bet_emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}.get(color, "❓")

    if color == outcome:
        win = bet * (14 if color == "green" else 2)
        balances[u]["balance"] += win
        result = f"✅ Победа! +{win - bet} монет"
    else:
        balances[u]["balance"] -= bet
        result = f"❌ Проигрыш -{bet} монет"

    save_balances()
    return text_response(f"🎰 {user} ставит {bet} на {bet_emoji}! Выпало {emoji} — {result} | Баланс: {balances[u]['balance']}")

@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").strip().lower()
    if not user:
        return text_response("❌ Укажи имя пользователя (?user=...)")

    u = ensure_user(user)
    now = time.time()
    last = balances[u].get("last_bonus", 0)

    if now - last >= BONUS_INTERVAL:
        balances[u]["last_bonus"] = now
        balances[u]["balance"] += BONUS_AMOUNT
        save_balances()
        return text_response(f"🎁 {user} получает {BONUS_AMOUNT} монет! Баланс: {balances[u]['balance']}")
    else:
        remain = int(BONUS_INTERVAL - (now - last))
        m, s = divmod(remain, 60)
        return text_response(f"⏳ {user}, бонус через {m}м {s}с")

@app.route("/top")
def top():
    if not balances:
        return text_response("🏆 Пока нет игроков")
    sorted_users = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)
    lines = [f"{i+1}. {u} — {d['balance']} монет" for i, (u, d) in enumerate(sorted_users[:10])]
    return text_response("🏆 Топ игроков:\n" + "\n".join(lines))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


