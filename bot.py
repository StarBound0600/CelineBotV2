import discord
from discord import app_commands
from discord.ext import commands
import json
import random
import os
from datetime import datetime, timedelta

# --- CONFIG ---
DATA_PATH = "/opt/render/project/data/CelineBotV2/data.json"
JOBS_PATH = "/opt/render/project/data/CelineBotV2/jobs.json"
SHOP_PATH = "/opt/render/project/data/CelineBotV2/shop.json"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Needed for role assignment
bot = commands.Bot(command_prefix="/", intents=intents)
tree = bot.tree


# --- LOAD FILES ---
# User save data
if os.path.exists(DATA_PATH):
    with open(DATA_PATH, "r") as f:
        user_data = json.load(f)
else:
    user_data = {}

# Jobs
if os.path.exists(JOBS_PATH):
    with open(JOBS_PATH, "r") as f:
        jobs = json.load(f)
else:
    jobs = {}

# Shop
if os.path.exists(SHOP_PATH):
    with open(SHOP_PATH, "r") as f:
        shop = json.load(f)
else:
    shop = {}

WORK_COOLDOWN = timedelta(hours=6)
DAILY_COOLDOWN = timedelta(hours=24)

# --- HELPERS ---
def save_data():
    with open(DATA_PATH, "w") as f:
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

async def assign_job_role(member: discord.Member, job_name: str):
    guild = member.guild
    role = discord.utils.get(guild.roles, name=job_name)
    if not role:
        role = await guild.create_role(name=job_name)
    await member.add_roles(role)

# --- COMMANDS ---
@tree.command(name="celine_joblist", description="Show all available jobs with chances and earnings")
async def joblist_command(interaction: discord.Interaction):
    if not jobs:
        await interaction.response.send_message("No jobs available. Ask the admin to add some in jobs.json.")
        return
    jobs_text = ""
    for job, info in jobs.items():
        jobs_text += f"**{job}** - Chance: {info['chance']*100:.0f}%, Earnings: {info['min']}-{info['max']} coins\n"
    await interaction.response.send_message(f"**Available Jobs:**\n{jobs_text}")

@tree.command(name="celine_apply", description="Apply for a specific job")
@app_commands.describe(job="The job you want to apply for")
async def apply(interaction: discord.Interaction, job: str):
    user = get_user_data(interaction.user.id)
    if user["job"]:
        await interaction.response.send_message(f"You already have a job as {user['job']}.")
        return

    job = job.title()  # normalize input, e.g., "lawyer" → "Lawyer"
    if job not in jobs:
        await interaction.response.send_message(f"{job} is not a valid job. Check /celine_joblist.")
        return

    # Assign job and role
    user["job"] = job
    save_data()
    await assign_job_role(interaction.user, job)
    await interaction.response.send_message(f"You got the job: {job}!")

@tree.command(name="celine_work", description="Work your job to earn coins")
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

    job_info = jobs[user["job"]]
    earnings = random.randint(job_info["min"], job_info["max"])
    user["coins"] += earnings
    user["last_work"] = datetime.utcnow().isoformat()
    save_data()
    await interaction.response.send_message(f"{interaction.user.mention}, you worked as a {user['job']} and earned {earnings} coins!")

@tree.command(name="celine_daily", description="Claim your daily coins")
async def daily(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    last_daily = user["last_daily"]
    if last_daily:
        cooldown_remaining = datetime.fromisoformat(last_daily) + DAILY_COOLDOWN - datetime.utcnow()
        if cooldown_remaining.total_seconds() > 0:
            await interaction.response.send_message(f"You already claimed daily. Come back in {str(cooldown_remaining).split('.')[0]}.")
            return

    earnings = random.randint(100, 300)
    user["coins"] += earnings
    user["last_daily"] = datetime.utcnow().isoformat()
    save_data()
    await interaction.response.send_message(f"{interaction.user.mention}, you claimed {earnings} coins for your daily reward!")

@tree.command(name="celine_balance", description="Check your coin balance")
async def balance(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    await interaction.response.send_message(f"{interaction.user.mention}, you have {user['coins']} coins.")

@tree.command(name="celine_leaderboard", description="Show the richest users")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(user_data.items(), key=lambda x: x[1]["coins"], reverse=True)
    top = sorted_users[:10]
    message = "**Leaderboard:**\n"
    for i, (uid, info) in enumerate(top, start=1):
        member = interaction.guild.get_member(int(uid))
        name = member.name if member else f"User {uid}"
        message += f"{i}. {name}: {info['coins']} coins\n"
    await interaction.response.send_message(message)

@tree.command(name="celine_shop", description="Show items in the shop")
async def shop_command(interaction: discord.Interaction):
    if not shop:
        await interaction.response.send_message("The shop is empty. Ask the admin to add items in shop.json.")
        return
    message = "**Shop Items:**\n"
    for item, info in shop.items():
        message += f"{item}: {info['price']} coins - {info['description']}\n"
    await interaction.response.send_message(message)

@tree.command(name="celine_buy", description="Buy an item from the shop")
@app_commands.describe(item="The item you want to buy")
async def buy(interaction: discord.Interaction, item: str):
    user = get_user_data(interaction.user.id)
    if item not in shop:
        await interaction.response.send_message("This item does not exist.")
        return
    price = shop[item]["price"]
    if user["coins"] < price:
        await interaction.response.send_message("You don't have enough coins.")
        return
    user["coins"] -= price
    user["inventory"][item] = user["inventory"].get(item, 0) + 1
    save_data()
    await interaction.response.send_message(f"You bought {item}!")

@tree.command(name="celine_inventory", description="Check your inventory")
async def inventory(interaction: discord.Interaction):
    user = get_user_data(interaction.user.id)
    if not user["inventory"]:
        await interaction.response.send_message("Your inventory is empty.")
        return
    items = "\n".join([f"{item}: {amount}" for item, amount in user["inventory"].items()])
    await interaction.response.send_message(f"**Inventory:**\n{items}")

@tree.command(name="celine_gift", description="Gift an item to another user")
@app_commands.describe(user="The member to gift to", item="The item to gift")
async def gift(interaction: discord.Interaction, user: discord.Member, item: str):
    sender = get_user_data(interaction.user.id)
    recipient = get_user_data(user.id)
    if item not in sender["inventory"] or sender["inventory"][item] <= 0:
        await interaction.response.send_message("You don't have this item to gift.")
        return
    sender["inventory"][item] -= 1
    if sender["inventory"][item] == 0:
        del sender["inventory"][item]
    recipient["inventory"][item] = recipient["inventory"].get(item, 0) + 1
    save_data()
    await interaction.response.send_message(f"You gifted {item} to {user.mention}!")

# --- START BOT ---
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()

bot.run(os.getenv("DISCORD_TOKEN"))
