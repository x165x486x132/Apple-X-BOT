import discord
from discord.ext import commands
from discord import app_commands
import datetime
import os
import asyncio
import requests
import base64
import json
import uuid

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
async def on_member_remove(member):
    print(f"👤 {member.name} left.")
    await update_member_count(member.guild)

# =========================================================================
# 🔑 PREMIUM SLASH COMMANDS (HWID KEY SYSTEM)
# =========================================================================
@bot.tree.command(name="get_hwid", description="Get the Lua code to copy your HWID")
async def get_hwid(interaction: discord.Interaction):
    script = "```lua\nsetclipboard(game:GetService('RbxAnalyticsService'):GetClientId())\n```"
    await interaction.response.send_message(
        f"🛠 *How to get your HWID?*\nRun this line in your Roblox executor. Your HWID will be copied to your clipboard:\n{script}", 
        ephemeral=True
    )

@bot.tree.command(name="key", description="Generate your lifetime Premium Key using your HWID")
@app_commands.describe(hwid="Your Roblox HWID (Run /get_hwid to copy it)")
async def generate_key(interaction: discord.Interaction, hwid: str):
    # Premium check
    if not any(role.id == ROLE_PREMIUM_ID for role in interaction.user.roles):
        await interaction.response.send_message("❌ **Access Denied.** This command is reserved for Server Boosters / Premium users.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True) 
    
    db, sha = get_github_db()
    user_id_str = str(interaction.user.id)

    # Clean the input HWID
    cleaned_hwid = hwid.strip().lower().replace("{", "").replace("}", "").replace(" ", "")

    if user_id_str in db:
        user_key = db[user_id_str]["key"]
        db[user_id_str]["hwid"] = cleaned_hwid 
    else:
        user_key = f"APPLEX-{uuid.uuid4().hex[:8].upper()}"
        db[user_id_str] = {"key": user_key, "hwid": cleaned_hwid}

    success = update_github_db(db, sha)
    
    if success:
        script_to_copy = f'```lua\nloadstring(game:HttpGet("https://raw.githubusercontent.com/Tamachiru/AppleX/refs/heads/main/Game4"))()\n```'
        await interaction.followup.send(f"✅ **Database successfully updated.**\n\nYour premium key is: `{user_key}`\n\nHere is your loader. Your device is now registered:\n{script_to_copy}\n\n*Note: Please wait 1 or 2 minutes for GitHub to register changes before running the script.*")
    else:
        await interaction.followup.send("❌ Error saving to GitHub. Please check if the `GH_API_TOKEN` secret is correctly configured.")

# =========================================================================
# 🛡️ ANTI-MALICIOUS LINK ENGINE
# =========================================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    detected_data = []
    words = message.content.split()

    for word in words:
        word_lower = word.lower()
        clean_url = word.strip("<>")
        
        for forbidden_link in FORBIDDEN_LINKS:
            if forbidden_link.lower() in word_lower:
                if not any(f == forbidden_link for f, u in detected_data):
                    detected_data.append((forbidden_link, clean_url))

        if "http://" in word_lower or "https://" in word_lower:
            for forbidden_name in FORBIDDEN_FILENAMES:
                if forbidden_name.lower() in clean_url.lower():
                    if not any(f == forbidden_name for f, u in detected_data):
                        detected_data.append((forbidden_name, clean_url))

    if len(detected_data) > 0:
        detected_list_str = "\n".join([f"🔗 **[{name}]({url if 'http' in url else 'https://'+url})**" for name, url in detected_data])
        
        try:
            await message.delete()
            print(f"🗑️ Deleted message from {message.author}")

            duration = datetime.timedelta(weeks=1)
            await message.author.timeout(duration, reason="Blacklisted link/image detected.")
            print(f"⏳ Timed out {message.author} for 1 week.")

            embed = discord.Embed(
                title="🚨 Security Alert: Malicious Link Blocked",
                description=f"An unauthorized link sent by {message.author.mention} has been intercepted and removed from the server.",
                color=0x2b2d31,
                timestamp=datetime.datetime.now()
            )
            embed.add_field(name="📂 Evidence (Clickable Links)", value=detected_list_str, inline=False)
            embed.add_field(name="⚖️ Punishment Applied", value="⏳ **1-Week Timeout**", inline=False)
            
            avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
            embed.set_thumbnail(url=avatar_url)
            
            image_to_display = None
            for name, url in detected_data:
                if name in FORBIDDEN_FILENAMES:
                    image_to_display = url
                    break
            
            if image_to_display:
                embed.set_image(url=image_to_display)
            
            embed.set_footer(text="Automated Security System", icon_url=bot.user.avatar.url if bot.user.avatar else None)
            await message.channel.send(embed=embed)
            
        except discord.Forbidden:
            print(f"⚠️ ERROR: Missing permissions to punish {message.author}!")
        except Exception as e:
            print(f"⚠️ System error: {e}")

    await bot.process_commands(message)

# =========================================================================
# 🚀 RUN THE BOT
# =========================================================================
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: DISCORD_TOKEN secret not found.")
