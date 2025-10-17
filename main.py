import asyncio
import json
import random
import os
import time
from flask import Flask
from threading import Thread
from twitchio.ext import commands, tasks

# === Настройки ===
TOKEN = os.getenv(TWITCH_TOKEN)  # OAuth токен
CHANNEL = os.getenv(TWITCH_CHANNEL)  # Имя Twitch-канала
PREFIX = !
BALANCE_FILE = balances.json
START_BALANCE = 1000
RESTORE_INTERVAL = 900  # каждые 15 минут

# === Flask сервер (Railway не заснёт) ===
app = Flask(__name__)

@app.route('')
def home()
    return 🎰 Twitch Casino Bot работает на Railway!

def run_flask()
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_flask).start()

# === Twitch бот ===
bot = commands.Bot(
    token=TOKEN,
    prefix=PREFIX,
    initial_channels=[CHANNEL]
)

def load_balances()
    try
        with open(BALANCE_FILE, r) as f
            return json.load(f)
    except FileNotFoundError
        return {}

def save_balances(balances)
    with open(BALANCE_FILE, w) as f
        json.dump(balances, f, indent=2)

def get_balance(user)
    balances = load_balances()
    return balances.get(user, {}).get(balance, START_BALANCE)

def update_balance(user, new_balance)
    balances = load_balances()
    if user not in balances
        balances[user] = {balance START_BALANCE, last_seen time.time()}
    balances[user][balance] = new_balance
    balances[user][last_seen] = time.time()
    save_balances(balances)

# --- Команда рулетки ---
@bot.command(name=roulette)
async def roulette(ctx)
    args = ctx.message.content.split()[1]
    if len(args) != 2
        await ctx.send(f@{ctx.author.name}, используй !roulette [redblackgreen] [ставка])
        return

    color = args[0].lower()
    user = ctx.author.name
    try
        bet = int(args[1])
    except ValueError
        await ctx.send(f@{user}, ставка должна быть числом.)
        return

    if color not in [red, black, green]
        await ctx.send(f@{user}, цвет должен быть red, black или green.)
        return

    balance = get_balance(user)

    if balance = 0
        await ctx.send(f@{user}, у тебя 0 💸! Смотри стрим, чтобы получить бонус за активность ❤️)
        return

    if bet  balance or bet = 0
        await ctx.send(f@{user}, ставка недопустима. Баланс {balance}.)
        return

    roll = random.randint(0, 36)
    result_color = green if roll == 0 else (red if roll % 2 == 0 else black)

    if result_color == green
        multiplier = 14
    elif result_color == color
        multiplier = 2
    else
        multiplier = 0

    if multiplier  0
        win = bet  (multiplier - 1)
        balance += win
        msg = f🎯 @{user}, выпало {result_color} ({roll}) — выигрыш ×{multiplier}! 💰 +{win}  Баланс {balance}
    else
        balance -= bet
        msg = f💀 @{user}, выпало {result_color} ({roll}) — проигрыш {bet}. Остаток {balance}

    update_balance(user, balance)
    await ctx.send(msg)

# --- Проверка баланса ---
@bot.command(name=balance)
async def balance_cmd(ctx)
    user = ctx.author.name
    bal = get_balance(user)
    await ctx.send(f@{user}, твой баланс {bal} 💰)

# --- Восстановление ---
@tasks.loop(seconds=60)
async def restore_balances()
    balances = load_balances()
    now = time.time()
    changed = False
    for user, data in balances.items()
        if data[balance] = 0 and now - data.get(last_seen, 0) = RESTORE_INTERVAL
            balances[user][balance] = START_BALANCE
            balances[user][last_seen] = now
            changed = True
            print(fБаланс {user} восстановлен.)
    if changed
        save_balances(balances)

@bot.event
async def event_ready()
    print(f✅ Бот {bot.nick} подключён к чату Twitch!)
    restore_balances.start()

@bot.event
async def event_message(ctx)
    if ctx.echo
        return
    update_balance(ctx.author.name, get_balance(ctx.author.name))
    await bot.handle_commands(ctx)

if __name__ == __main__
    bot.run()
