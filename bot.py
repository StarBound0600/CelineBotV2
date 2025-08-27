import os
import json
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.guilds = True       # Required for slash commands
intents.members = False     # DISABLED to avoid privileged intents error
intents.message_content = False  # Not needed for slash commands

bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# --- DATA FILES ---
DATA_FILE = "data.json"
SHOP_FILE = "shop.json"
JOBS_FILE = "jobs.json"
CONFIG_FILE = "config.json"

data_lock = asyncio.Lock()

# --- LOAD / SAVE HELPERS ---
def load_json(file, default):
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump(default, f, indent=4)
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, content):
    with open(file, "w") as f:
        json.dump(content, f, indent=4)

# --- INITIALIZE FILES ---
shop = load_json(SHOP_FILE, {
    "Coffee": 50, "Bicycle": 500, "Laptop": 1200,
    "Smartphone": 1000, "Washing Machine": 2000,
    "TV": 1500, "Refrigerator": 2500, "Microwave": 400,
    "Sofa": 1800, "Bed": 2200, "Car": 10000,
    "Motorcycle": 7000, "Diamond Ring": 25000,
    "Yacht": 100000, "Mansion": 500000
})

jobs = load_json(JOBS_FILE, {
    "Barista": {"chance": 1.0, "min": 50, "max": 150},
    "Receptionist": {"chance": 0.95, "min": 80, "max": 200},
    "Farmer": {"chance": 0.90, "min": 100, "max": 250},
    "Delivery Driver": {"chance": 0.85, "min": 120, "max": 300},
    "Streamer": {"chance": 0.80, "min": 150, "max": 400},
    "Musician": {"chance": 0.80, "min": 200, "max": 500},
    "Influencer": {"chance": 0.70, "min": 250, "max": 600},
    "Lawyer": {"chance": 0.60, "min": 600, "max": 1200},
    "Astronaut": {"chance": 0.40, "min": 2000, "max": 4000}
})

config = load_json(CONFIG_FILE, {
    "work_cooldown": 21600,  # 6h
    "daily_cooldown": 86400  # 24h
})

data = load_json(DATA_FILE, {})

# --- UTILITIES ---
async def get_user_data(user_id):
    async with data_lock:
        if str(user_id) not in data:
            data[str(user_id)] = {"balance": 0, "job": None, "last_work": 0, "last_daily": 0, "inventory": []}
            save_json(DATA_FILE, data)
        return data[str(user_id)]

async def update_user_data(user_id, key, value):
    async with data_lock:
        data[str(user_id)][key] = value
        save_json(DATA_FILE, data)

# --- COMMANDS ---
@tree.command(name="celine_job", description="Apply for a job")
@app_commands.describe(job="Job you want to apply for")
async def job_command(interaction: discord.Interaction, job: str):
    job = job.title()
    if job not in jobs:
        await interaction.response.send_message(f"❌ Job '{job}' does not exist.")
        return
    chance = jobs[job]["chance"]
    roll = random.random()
    if roll <= chance:
        await update_user_data(interaction.user.id, "job", job)
        await interaction.response.send_message(f"✅ Congrats {interaction.user.mention}, you got the job as **{job}**!")
    else:
        await interaction.response.send_message(f"😞 Sorry {interaction.user.mention}, you didn’t get the **{job}** job. Try again later!")

@tree.command(name="celine_work", description="Work your job and earn coins")
async def work_command(interaction: discord.Interaction):
    user = await get_user_data(interaction.user.id)
    job = user["job"]
    if not job:
        await interaction.response.send_message("❌ You don’t have a job. Use `/celine_job` first.")
        return

    now = datetime.utcnow().timestamp()
    if now - user["last_work"] < config["work_cooldown"]:
        wait = timedelta(seconds=int(config["work_cooldown"] - (now - user["last_work"])))
        await interaction.response.send_message(f"⏳ You must wait {wait} before working again.")
        return

    pay = random.randint(jobs[job]["min"], jobs[job]["max"])
    await update_user_data(interaction.user.id, "balance", user["balance"] + pay)
    await update_user_data(interaction.user.id, "last_work", now)

    await interaction.response.send_message(f"💼 {interaction.user.mention}, you worked as a **{job}** and earned **{pay} coins**!")

@tree.command(name="celine_daily", description="Claim your daily bonus")
async def daily_command(interaction: discord.Interaction):
    user = await get_user_data(interaction.user.id)
    now = datetime.utcnow().timestamp()
    if now - user["last_daily"] < config["daily_cooldown"]:
        wait = timedelta(seconds=int(config["daily_cooldown"] - (now - user["last_daily"])))
        await interaction.response.send_message(f"⏳ You must wait {wait} before claiming daily again.")
        return
    bonus = 500
    await update_user_data(interaction.user.id, "balance", user["balance"] + bonus)
    await update_user_data(interaction.user.id, "last_daily", now)
    await interaction.response.send_message(f"🎁 {interaction.user.mention}, you claimed your daily bonus of **{bonus} coins**!")

@tree.command(name="celine_balance", description="Check your balance")
async def balance_command(interaction: discord.Interaction):
    user = await get_user_data(interaction.user.id)
    await interaction.response.send_message(f"💰 {interaction.user.mention}, you have **{user['balance']} coins**.")

@tree.command(name="celine_shop", description="View items in the shop")
async def shop_command(interaction: discord.Interaction):
    msg = "🛒 **Shop Items:**\n" + "\n".join([f"- {item}: {price} coins" for item, price in shop.items()])
    await interaction.response.send_message(msg)

@tree.command(name="celine_buy", description="Buy an item from the shop")
@app_commands.describe(item="Item to buy")
async def buy_command(interaction: discord.Interaction, item: str):
    item = item.title()
    if item not in shop:
        await interaction.response.send_message("❌ That item is not in the shop.")
        return
    user = await get_user_data(interaction.user.id)
    price = shop[item]
    if user["balance"] < price:
        await interaction.response.send_message("❌ You don’t have enough coins.")
        return
    user["balance"] -= price
    user["inventory"].append(item)
    await update_user_data(interaction.user.id, "balance", user["balance"])
    await update_user_data(interaction.user.id, "inventory", user["inventory"])
    await interaction.response.send_message(f"✅ You bought **{item}** for {price} coins!")

@tree.command(name="celine_inventory", description="Check your inventory")
async def inventory_command(interaction: discord.Interaction):
    user = await get_user_data(interaction.user.id)
    if not user["inventory"]:
        await interaction.response.send_message("🎒 Your inventory is empty.")
        return
    items = {}
    for i in user["inventory"]:
        items[i] = items.get(i, 0) + 1
    msg = "🎒 **Your Inventory:**\n" + "\n".join([f"- {itm} x{cnt}" for itm, cnt in items.items()])
    await interaction.response.send_message(msg)

@tree.command(name="celine_leaderboard", description="Top 10 richest users")
async def leaderboard_command(interaction: discord.Interaction):
    top = sorted(data.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    msg = "🏆 **Leaderboard:**\n"
    for i, (uid, info) in enumerate(top, 1):
        user = bot.get_user(int(uid))
        name = user.name if user else f"User {uid}"
        msg += f"{i}. {name} — {info['balance']} coins\n"
    await interaction.response.send_message(msg)

# --- BOT READY ---
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user}")

# --- RUN ---
bot.run(os.getenv("DISCORD_TOKEN"))
