import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import asyncio
import os
from datetime import datetime, timedelta

# --- CONFIG ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree

# --- LOAD FILES ---
with open("config.json") as f:
    config = json.load(f)

with open("data.json") as f:
    user_data = json.load(f)

with open("jobs.json") as f:
    jobs = json.load(f)

with open("shop.json") as f:
    shop = json.load(f)

WORK_COOLDOWN = timedelta(hours=6)
DAILY_COOLDOWN = timedelta(hours=24)

# --- HELPER FUNCTIONS ---
def save_data():
    with open("data.json", "w") as f:
        json.dump(user_data, f, indent=4)

def get_user_data(user_id):
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {
            "coins": 0,
            "job": None,
            "last_work": None,
            "last_daily": None,
            "inventory": {}
        }
    return user_data[str(user_id)]

# --- COMMANDS ---
@tree.command(name="joblist", description="Show all available jobs and chances")
async def joblist_command(interaction: discord.Interaction):
    jobs_text = "\n".join([f"{job}: {chance*100:.0f}%" for job, chance in jobs.items()])
    await interaction.response.send_message(f"**Available Jobs:**\n{jobs_text}")

@tree.command(name="apply", description="Apply for a job")
async def apply(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    if user["job"]:
        await interaction.response.send_message(f"You already have a job as {user['job']}.")
        return

    roll = random.random()
    for job, chance in jobs.items():
        if roll <= chance:
            user["job"] = job
            save_data()
            await interaction.response.send_message(f"You got the job: {job}!")
            return
    await interaction.response.send_message("No job this time. Try again later!")

@tree.command(name="work", description="Work your job to earn coins")
async def work(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    if not user["job"]:
        await interaction.response.send_message("You don't have a job! Apply first with `/celine_apply`.")
        return

    last_work = user["last_work"]
    if last_work:
        cooldown_remaining = datetime.fromisoformat(last_work) + WORK_COOLDOWN - datetime.utcnow()
        if cooldown_remaining.total_seconds() > 0:
            await interaction.response.send_message(f"You are on cooldown for {str(cooldown_remaining).split('.')[0]}.")
            return

    earnings = random.randint(50, 150)
    user["coins"] += earnings
    user["last_work"] = datetime.utcnow().isoformat()
    save_data()
    await interaction.response.send_message(f"{interaction.user.mention}, you worked as a {user['job']} and earned {earnings} coins!")

@tree.command(name="daily", description="Claim your daily coins")
async def daily(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    last_daily = user["last_daily"]
    if last_daily:
        cooldown_remaining = datetime.fromisoformat(last_daily) + DAILY_COOLDOWN - datetime.utcnow()
        if cooldown_remaining.total_seconds() > 0:
            await interaction.response.send_message(f"You have already claimed daily. Come back in {str(cooldown_remaining).split('.')[0]}.")
            return

    earnings = random.randint(100, 300)
    user["coins"] += earnings
    user["last_daily"] = datetime.utcnow().isoformat()
    save_data()
    await interaction.response.send_message(f"{interaction.user.mention}, you claimed {earnings} coins for your daily reward!")

@tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}, you have {user['coins']} coins.")

@tree.command(name="leaderboard", description="Show the richest users")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["coins"], reverse=True)
    top = sorted_users[:10]
    message = "**Leaderboard:**\n"
    for i, (uid, info) in enumerate(top, start=1):
        member = interaction.guild.get_member(int(uid))
        name = member.name if member else f"User {uid}"
        message += f"{i}. {name}: {info['coins']} coins\n"
    await interaction.response.send_message(message)

@tree.command(name="shop", description="Show items in the shop")
async def shop_command(interaction: discord.Interaction):
    message = "**Shop Items:**\n"
    for item, price in shop.items():
        message += f"{item}: {price} coins\n"
    await interaction.response.send_message(message)

@tree.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item="The item you want to buy")
async def buy(interaction: discord.Interaction, item: str):
    user = get_user_data(interaction.user.id)
    if item not in shop:
        await interaction.response.send_message("This item does not exist.")
        return
    price = shop[item]
    if user["coins"] < price:
        await interaction.response.send_message("You don't have enough coins.")
        return
    user["coins"] -= price
    user["inventory"][item] = user["inventory"].get(item, 0) + 1
    save_data()
    await interaction.response.send_message(f"You bought {item}!")

# --- NEW INVENTORY COMMAND ---
@tree.command(name="inventory", description="Check your items")
async def inventory(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    inventory = user["inventory"]
    if not inventory:
        await interaction.response.send_message("You have no items in your inventory.")
        return
    message = "**Your Inventory:**\n"
    for item, amount in inventory.items():
        message += f"{item}: {amount}\n"
    await interaction.response.send_message(message)

# --- START BOT ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()

bot.run(os.getenv("DISCORD_TOKEN"))
