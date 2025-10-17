# -*- coding: utf-8 -*-
from flask import Flask, request, Response
import random, json, time, os

app = Flask(__name__)

# === Настройки ===
BALANCES_FILE = "balances.json"
ADMINS = ["gxku999"]  # <-- впиши свой ник(и) в нижнем регистре
BONUS_AMOUNT = 500
BONUS_INTERVAL = 60 * 60 * 24  # 24 часа
ACTIVE_REWARD = 500
ACTIVE_INTERVAL = 60 * 15  # 15 минут
START_BALANCE = 1000

# === Загрузка данных ===
if os.path.exists(BALANCES_FILE):
    with open(BALANCES_FILE, "r", encoding="utf-8") as f:
        try:
            balances = json.load(f)
        except:
            balances = {}
else:
    balances = {}

# === Утилиты ===
def save_data():
    with open(BALANCES_FILE, "w", encoding="utf-8") as f:
        json.dump(balances, f, ensure_ascii=False, indent=2)

def text_response(msg: str):
    return Response(msg, mimetype="text/plain; charset=utf-8")

def norm_name(n: str) -> str:
    return (n or "").strip()

def norm_key(n: str) -> str:
    return (n or "").strip().lower()

def get_user_entry(key_name: str):
    """Возвращает объект пользователя; если нет — создаёт"""
    k = norm_key(key_name)
    if k == "":
        return None
    if k not in balances:
        balances[k] = {
            "display": norm_name(key_name),
            "balance": START_BALANCE,
            "wins": 0,
            "losses": 0,
            "last_bonus": 0,
            "last_active": 0
        }
    # Убедимся, что display поле присутствует и содержит оригинальный регистр (если передавали)
    if not balances[k].get("display"):
        balances[k]["display"] = norm_name(key_name)
    return balances[k]

def ensure_user_by_candidates(*cands):
    """Пытаемся найти правильный ник среди кандидатов (возвращаем первый адекватный).
       'Адекватный' = не color word и не чисто число и не пустая строка."""
    colors = {"red","black","green"}
    for c in cands:
        if not c:
            continue
        s = str(c).strip()
        if s == "":
            continue
        low = s.lower()
        if low in ("null","none"):
            continue
        if low in colors:
            continue
        if s.isdigit():
            continue
        return s
    # если не нашли — вернём первый ненулевой кандидат в естественном виде
    for c in cands:
        if c and str(c).strip() and str(c).strip().lower() not in ("null","none"):
            return str(c).strip()
    return ""

def color_icon(color):
    icons = {"red": "🟥", "black": "⬛", "green": "🟩"}
    return icons.get((color or "").lower(), "❓")

def parse_params_for_roll():
    """
    Универсально вытаскивает user_display, user_key, color, bet из любых комбинаций параметров,
    устойчив к: user/null swapping, sender, nick, username и т.п.
    """
    # Соберём сырьё
    raw_user = request.args.get("user") or request.args.get("sender") or request.args.get("nick") or request.args.get("username") or ""
    raw_color = request.args.get("color") or request.args.get("1") or ""
    raw_bet = request.args.get("bet") or request.args.get("amount") or request.args.get("2") or ""

    # Иногда StreamElements/шаблоны могут передать цвет в поле user (например user=red),
    # или передать ник в поле color. Попробуем определить правильный ник:
    colors = {"red","black","green"}
    candidates = []
    # Соберём все переданные значения в порядке вероятности
    for v in [raw_user, raw_color, raw_bet]:
        if v is not None:
            candidates.append(str(v).strip())

    # Попытка 1: нормальная ситуация — raw_user не цвет и не число -> good
    if raw_user and raw_user.strip().lower() not in colors and not raw_user.strip().isdigit() and raw_user.strip().lower() not in ("null","none"):
        user_display = raw_user.strip()
        user_key = norm_key(user_display)
        color = (raw_color or "").strip().lower()
        bet = (raw_bet or "").strip()
        return user_display, user_key, color, bet

    # Попытка 2: если raw_user выглядит как цвет или число — найдем реальный ник среди других params
    alt_user = ensure_user_by_candidates(raw_color, raw_bet, *candidates)
    if alt_user:
        # теперь нужно определить, какой из полей является цвет, а какой ставка
        # предпочтение: поле, которое равняется color word -> color; numeric -> bet
        color = ""
        bet = ""
        # check each original arg
        for v in [raw_user, raw_color, raw_bet]:
            if not v:
                continue
            s = str(v).strip()
            low = s.lower()
            if low in colors and color == "":
                color = low
            elif (s.isdigit() or (s.startswith('-') and s[1:].isdigit())) and bet == "":
                bet = s
        # if still missing, try fill from remaining candidates (best effort)
        if color == "":
            for v in [raw_color, raw_bet, raw_user]:
                if v and str(v).strip().lower() in colors:
                    color = str(v).strip().lower()
                    break
        if bet == "":
            for v in [raw_color, raw_bet, raw_user]:
                if v and str(v).strip().isdigit():
                    bet = str(v).strip()
                    break
        user_display = alt_user
        user_key = norm_key(user_display)
        return user_display, user_key, color, bet

    # Попытка 3: ничего не подошло — используем raw_user как ник (может быть empty)
    user_display = raw_user.strip()
    user_key = norm_key(user_display)
    color = (raw_color or "").strip().lower()
    bet = (raw_bet or "").strip()
    return user_display, user_key, color, bet

# === Эндпоинты ===

@app.route("/roulette")
def roulette():
    # универсальный парсер
    user_display, user_key, color, bet_raw = parse_params_for_roll()

    if not user_display:
        return text_response("❌ Не удалось определить пользователя. Укажи правильно: !roll <color> <bet>")

    if not color:
        return text_response("❌ Не указан цвет. Используй: red, black или green")

    if color not in ("red","black","green"):
        return text_response("❌ Цвет должен быть red, black или green")

    if not bet_raw:
        return text_response("❌ Укажи ставку. Пример: !roll red 100")

    if bet_raw.lower() in ("null","none",""):
        return text_response("❌ Ставка должна быть числом!")

    try:
        bet = int(bet_raw)
    except ValueError:
        return text_response("❌ Ставка должна быть целым числом!")

    # Получаем entry пользователя (создаст, если нет)
    entry = get_user_entry(user_display)
    if entry is None:
        return text_response("❌ Неверный ник пользователя.")

    if bet <= 0:
        return text_response("❌ Ставка должна быть положительной!")

    if entry["balance"] < bet:
        return text_response(f"💸 У {entry['display']} недостаточно средств! Баланс: {entry['balance']}")

    # снимаем ставку сразу
    entry["balance"] -= bet

    # результат
    result = random.choices(["red","black","green"], weights=[47,47,6])[0]
    multiplier = 14 if result == "green" else 2

    win_amount = bet * multiplier if result == color else 0

    if win_amount > 0:
        # добавляем выигрыш (включая возврат ставки)
        entry["balance"] += win_amount
        entry["wins"] = entry.get("wins",0) + 1
        delta = win_amount - bet
        msg = f"🎰 {entry['display']} ставит {bet} на {color_icon(color)}! Выпало {color_icon(result)} — ✅ Победа! | +{delta} | Баланс: {entry['balance']}"
    else:
        entry["losses"] = entry.get("losses",0) + 1
        msg = f"🎰 {entry['display']} ставит {bet} на {color_icon(color)}! Выпало {color_icon(result)} — ❌ Проигрыш | Баланс: {entry['balance']}"

    save_data()
    return text_response(msg)

@app.route("/balance")
def balance():
    # Try multiple possible fields for user
    user_try = request.args.get("user") or request.args.get("sender") or request.args.get("nick") or request.args.get("username") or ""
    user_display = ensure_user_by_candidates(user_try, request.args.get("1"), request.args.get("2")) or user_try
    if not user_display:
        return text_response("❌ Укажи имя пользователя.")
    entry = get_user_entry(user_display)
    if entry is None:
        return text_response("❌ Неверный ник.")
    now = time.time()
    reward_msg = ""
    if now - entry.get("last_active",0) >= ACTIVE_INTERVAL:
        entry["balance"] += ACTIVE_REWARD
        entry["last_active"] = now
        reward_msg = f"\n⏱ {entry['display']} получает {ACTIVE_REWARD} монет за активность на стриме! 🎁"
    save_data()
    return text_response(f"💰 Баланс {entry['display']}: {entry['balance']}{reward_msg}")

@app.route("/bonus")
def bonus():
    user_try = request.args.get("user") or request.args.get("sender") or ""
    user_display = ensure_user_by_candidates(user_try, request.args.get("1")) or user_try
    if not user_display:
        return text_response("❌ Укажи имя пользователя.")
    entry = get_user_entry(user_display)
    if entry is None:
        return text_response("❌ Неверный ник.")
    now = time.time()
    last = entry.get("last_bonus", 0)
    if now - last < BONUS_INTERVAL:
        remaining = int((BONUS_INTERVAL - (now - last)) / 3600)
        return text_response(f"⏳ {entry['display']}, бонус будет доступен через {remaining} ч.")
    entry["balance"] += BONUS_AMOUNT
    entry["last_bonus"] = now
    save_data()
    return text_response(f"🎁 {entry['display']} получает ежедневный бонус {BONUS_AMOUNT} монет! Баланс: {entry['balance']}")

@app.route("/stats")
def stats_route():
    user_try = request.args.get("user") or request.args.get("sender") or ""
    user_display = ensure_user_by_candidates(user_try, request.args.get("1")) or user_try
    if not user_display:
        return text_response("❌ Укажи имя пользователя.")
    entry = get_user_entry(user_display)
    if entry is None:
        return text_response("❌ Неверный ник.")
    wins = entry.get("wins",0)
    losses = entry.get("losses",0)
    total = wins + losses
    wr = f"{(wins/total*100):.1f}%" if total>0 else "0%"
    save_data()
    return text_response(f"📊 Статистика {entry['display']}: Побед — {wins}, Поражений — {losses} (WinRate: {wr})")

@app.route("/top")
def top():
    # build top-10 sorted by balance
    if not balances:
        return text_response("📉 Пока никто не играет!")
    sorted_players = sorted(balances.items(), key=lambda x: x[1].get("balance",0), reverse=True)
    top10 = sorted_players[:10]
    lines = [f"🏆 Топ 10 игроков:"]
    for i,(k,v) in enumerate(top10, start=1):
        display = v.get("display", k)
        bal = v.get("balance", 0)
        lines.append(f"{i}. {display} — {bal}")
    save_data()
    return text_response("\n".join(lines))

@app.route("/admin")
def admin():
    caller = request.args.get("user") or request.args.get("sender") or ""
    caller_key = norm_key(caller)
    if caller_key not in [a.lower() for a in ADMINS]:
        return text_response("🚫 У тебя нет прав администратора!")

    target = request.args.get("target") or request.args.get("1") or ""
    action = (request.args.get("action") or request.args.get("2") or "").lower()
    amount_raw = request.args.get("amount") or request.args.get("3") or ""

    if not target or not action or not amount_raw:
        return text_response("❌ Использование: /admin?user=AdminNick&target=Nick&action=add|remove&amount=1000")

    try:
        amount = int(amount_raw)
    except:
        return text_response("❌ Сумма должна быть числом!")

    entry = get_user_entry(target)
    if entry is None:
        return text_response("❌ Неверный ник цели.")

    if action == "add":
        entry["balance"] += amount
        res = f"✅ Админ {caller} добавил {amount} монет игроку {entry['display']}. Баланс: {entry['balance']}"
    elif action in ("remove","sub","take"):
        entry["balance"] = max(0, entry["balance"] - amount)
        res = f"⚠️ Админ {caller} снял {amount} монет с {entry['display']}. Баланс: {entry['balance']}"
    else:
        return text_response("❌ Action должен быть add или remove")

    save_data()
    return text_response(res)

@app.route("/")
def home():
    return text_response("🎰 Casino bot API работает!")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
