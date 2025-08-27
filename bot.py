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
intents.message_content = True  # Needed for reading messages
intents.members = True          # Needed to assign/remove roles
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

async def assign_job_role(interaction, new_job):
    member = interaction.user
    guild = interaction.guild

    # Remove old job role if it exists
    old_job = get_user_data(member.id)["job"]
    if old_job and old_job != new_job:
        old_role = discord.utils.get(guild.roles, name=old_job)
        if old_role in member.roles:
            await member.remove_roles(old_role)

    # Assign new job role
    role = discord.utils.get(guild.roles, name=new_job)
    if role:
        await member.add_roles(role)
        return True
    return False

# --- COMMANDS ---
@tree.command(name="joblist", description="Show all available jobs and chances")
async def joblist_command(interaction: discord.Interaction):
    jobs_text = "\n".join([f"{job}: {chance*100:.0f}%" for job, chance in jobs.items()])
    await interaction.response.send_message(f"**Available Jobs:**\n{jobs_text}")

@tree.command(name="apply", description="Apply for a job")
async def apply(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    if user["job"]:
        await interaction.response.send_message(f"You already have a job as {user['job']}. Applying again may switch your role if lucky.")
    
    roll = random.random()
    for job, chance in jobs.items():
        if roll <= chance:
            user["job"] = job
            save_data()
            role_assigned = await assign_job_role(interaction, job)
            msg = f"You got the job: {job}!"
            if role_assigned:
                msg += f" Discord role '{job}' assigned."
            else:
                msg += " (No role found to assign.)"
            await interaction.response.send_message(msg)
            return
    await interaction.response.send_message("No job this time. Try again later!")

# --- Other commands remain the same ---
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

@tree.command(name="inventory", description="Check your inventory")
async def inventory(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    inv = user["inventory"]
    if not inv:
        await interaction.response.send_message("Your inventory is empty.")
        return
    message = "**Inventory:**\n"
    for item, qty in inv.items():
        message += f"{item}: {qty}\n"
    await interaction.response.send_message(message)

# --- START BOT ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()

bot.run(os.getenv("DISCORD_TOKEN"))

