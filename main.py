import json
import random
import time
import traceback
import requests
from flask import Flask, request, Response
import os

app = Flask(__name__)

# === ⚙️ Настройки GitHub Sync ===
GITHUB_TOKEN = os.getenv("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")
GITHUB_REPO = os.getenv("Gxku999/kazikbotwitch228")       # например: "gxku999/kazikbot"
GITHUB_PATH = os.getenv("GITHUB_PATH", "balances.json")

LOCAL_FILE = "balances.json"
BONUS_AMOUNT = 500
BONUS_INTERVAL = 15 * 60  # 15 минут
DEFAULT_BALANCE = 1500

# === Логирование ===
def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# === GitHub ===
def github_api_url():
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"


def load_from_github():
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(github_api_url(), headers=headers)
        if r.status_code == 200:
            content = r.json()["content"]
            import base64
            decoded = base64.b64decode(content).decode("utf-8")
            return json.loads(decoded)
        else:
            log(f"⚠️ GitHub load error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"⚠️ Ошибка загрузки из GitHub: {e}")
    return {}


def save_to_github(data):
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(github_api_url(), headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None

        import base64
        encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("utf-8")

        payload = {
            "message": "update balances.json",
            "content": encoded,
        }
        if sha:
            payload["sha"] = sha

        put = requests.put(github_api_url(), headers=headers, data=json.dumps(payload))
        log(f"💾 Синхронизация с GitHub ({put.status_code})")
        if put.status_code >= 300:
            log(f"⚠️ Ошибка GitHub: {put.text}")
    except Exception as e:
        log(f"⚠️ Ошибка синхронизации: {e}")


# === Локальная работа с балансом ===
def load_balances():
    try:
        if os.path.exists(LOCAL_FILE):
            with open(LOCAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        traceback.print_exc()
    return {}


def save_balances(data):
    with open(LOCAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    save_to_github(data)


# === Инициализация ===
balances = load_balances()
if not balances and GITHUB_TOKEN and GITHUB_REPO:
    balances = load_from_github()
    save_balances(balances)

log("✅ Twitch Casino Bot запущен и синхронизирован с GitHub")


# === Вспомогательные функции ===
def get_user(user):
    user = user.lower()
    if user not in balances:
        balances[user] = {"balance": DEFAULT_BALANCE, "last_bonus": 0}
        save_balances(balances)
    return balances[user]


def update_balance(user, delta):
    data = get_user(user)
    data["balance"] += delta
    save_balances(balances)
    return data["balance"]


# === Хелпер для StreamElements (без иероглифов) ===
def text_response(text):
    return Response(text, content_type="text/plain; charset=utf-8")


# === РОУТЫ ===

@app.route("/balance")
def balance():
    user = request.args.get("user", "").lower()
    info = get_user(user)
    return text_response(f"💰 Баланс {user}: {info['balance']} монет")


@app.route("/roll")
def roll():
    user = request.args.get("user", "").lower()
    color = request.args.get("color", "").lower()
    try:
        bet = int(request.args.get("bet", 0))
    except:
        return text_response("❌ Неверная ставка")

    if bet <= 0:
        return text_response("❌ Минимальная ставка — 1 монета")

    data = get_user(user)
    if data["balance"] < bet:
        return text_response(f"❌ Недостаточно средств! Баланс: {data['balance']}")

    outcome = random.choice(["red", "black", "green"])
    emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}[outcome]
    bet_emoji = {"red": "🟥", "black": "⬛", "green": "🟩"}.get(color, "❓")

    if color == outcome:
        win = bet * (14 if outcome == "green" else 2)
        new_balance = update_balance(user, win)
        msg = f"🎰 {user} ставит {bet} на {bet_emoji}! Выпало {emoji} — ✅ Победа! | +{win} | Баланс: {new_balance}"
    else:
        new_balance = update_balance(user, -bet)
        msg = f"🎰 {user} ставит {bet} на {bet_emoji}! Выпало {emoji} — ❌ Проигрыш | Баланс: {new_balance}"

    return text_response(msg)


@app.route("/bonus")
def bonus():
    user = request.args.get("user", "").lower()
    now = time.time()
    info = get_user(user)

    if now - info["last_bonus"] >= BONUS_INTERVAL:
        info["last_bonus"] = now
        info["balance"] += BONUS_AMOUNT
        save_balances(balances)
        return text_response(f"🎁 {user} получает {BONUS_AMOUNT} монет за активность! Баланс: {info['balance']}")
    else:
        remain = int(BONUS_INTERVAL - (now - info["last_bonus"]))
        m, s = divmod(remain, 60)
        return text_response(f"⏳ {user}, бонус будет доступен через {m}м {s}с")


@app.route("/top")
def top():
    if not balances:
        return text_response("🏆 Пока нет игроков")
    sorted_users = sorted(balances.items(), key=lambda x: x[1]["balance"], reverse=True)
    top10 = sorted_users[:10]
    lines = [f"{i+1}. {u} — {d['balance']} монет" for i, (u, d) in enumerate(top10)]
    return text_response("🏆 Топ игроков:\n" + "\n".join(lines))


@app.route("/")
def home():
    return text_response("✅ Twitch Casino Bot работает!")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
