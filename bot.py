import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import asyncio
import requests
import base64
import json

# =========================================================================
# ⚙️ GLOBAL CONFIGURATION
# =========================================================================
TOKEN = os.getenv("DISCORD_TOKEN")
GH_API_TOKEN = os.getenv("GH_API_TOKEN") 
STATS_CHANNEL_ID = os.getenv("CHANNEL_ID")

# --- HWID CONFIGURATION ---
REPO_NAME = "x165x486x132/Apple-X-Key"    # Your public database repository
FILE_PATH = "hwid_db.json"               
ROLE_PREMIUM_ID = 1498644209840951468    # Premium/Booster Role ID

# --- ANTI-MALICIOUS LINK CONFIGURATION ---
FORBIDDEN_FILENAMES = [
    "IMG_7625.jpg", "IMG_7625.jpeg",
    "IMG_7632.jpg", "IMG_7632.jpeg",
    "IMG_7620.jpg", "IMG_7620.jpeg",
    "Untitled.jpg", "Untitled.jpeg",
    "image.jpg", "image.jpeg"
]

FORBIDDEN_LINKS = [
    "roblox-scam.com",    
    "discord-nitro.gift", 
    "steamspecial.com"    
]

# =========================================================================
# 📂 GITHUB API UTILS
# =========================================================================
def get_github_db():
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        data = r.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        return json.loads(content), data['sha']
    return {}, None

def update_github_db(json_data, sha):
    url = f"https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}"
    headers = {"Authorization": f"token {GH_API_TOKEN}"}
    content_b64 = base64.b64encode(json.dumps(json_data, indent=4).encode('utf-8')).decode('utf-8')
    payload = {"message": "🤖 Update HWID Database", "content": content_b64}
    if sha:
        payload["sha"] = sha
    r = requests.put(url, headers=headers, json=payload)
    return r.status_code in [200, 201]

# =========================================================================
# 🤖 BOT INITIALIZATION
# =========================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

class AppleXBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands successfully synchronized.")

bot = AppleXBot()

# =========================================================================
# 📊 STATISTICS & LIFETIME TIMER
# =========================================================================
async def update_member_count(guild):
    if not STATS_CHANNEL_ID:
        return
    try:
        channel_id = int(STATS_CHANNEL_ID)
        channel = guild.get_channel(channel_id)
        if channel:
            member_count = guild.member_count
            new_name = f"👥 Members: {member_count}"
            if channel.name != new_name:
                await channel.edit(name=new_name)
                print(f"📊 Updated stats channel name to: {new_name}")
    except discord.RateLimited:
        print("⏳ Rate limited by Discord API for channel renaming. Waiting...")
    except Exception as e:
        print(f"⚠️ Failed to update stats channel: {e}")

async def github_timer():
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching. Voluntary graceful shutdown.")
    await bot.close()

# =========================================================================
# 🟢 EVENTS
# =========================================================================
@bot.event
async def on_ready():
    print(f'✅ Bot is online! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="roblox"))
    
    for guild in bot.guilds:
        await update_member_count(guild)
        
    bot.loop.create_task(github_timer())

@bot.event
async def on_member_join(member):
    print(f"👤 {member.name} joined.")
    await update_member_count(member.guild)

@bot.event
async def on_member_remove
