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
# ⚙️ CONFIGURATION GLOBALE
# =========================================================================
TOKEN = os.getenv("DISCORD_TOKEN")
GH_API_TOKEN = os.getenv("GH_API_TOKEN") # Le nouveau token pour écrire sur GitHub
STATS_CHANNEL_ID = os.getenv("CHANNEL_ID")

# --- CONFIGURATION HWID ---
REPO_NAME = "x165x486x132/Apple-X-Key"    # Ton repository public (Base de données)
FILE_PATH = "hwid_db.json"               # Le fichier qui sert de base de données
ROLE_PREMIUM_ID = 1498644209840951468    # ID du rôle requis pour générer une clé

# --- CONFIGURATION ANTI-LIENS ---
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
# 📂 FONCTIONS GITHUB API (BASE DE DONNÉES HWID)
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
# 🤖 INITIALISATION DU BOT
# =========================================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

class AppleXBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync() # Synchronise les commandes Slash (/key, /get_hwid)
        print("✅ Slash commands synchronisées.")

bot = AppleXBot()

# =========================================================================
# 📊 FONCTION STATS MEMBRES & TIMER
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
                print(f"📊 Updated stats channel to: {new_name}")
    except discord.RateLimited:
        print("⏳ Rate limited by Discord for channel renaming. Retrying later...")
    except Exception as e:
        print(f"⚠️ Failed to update stats channel: {e}")

async def github_timer():
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching: Clean and voluntary shutdown of the bot.")
    await bot.close()

# =========================================================================
# 🟢 ÉVÉNEMENTS DISCORD (READY, JOIN, LEAVE)
# =========================================================================
@bot.event
async def on_ready():
    print(f'✅ Operational! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="roblox"))
    
    for guild in bot.guilds:
        await update_member_count(guild)
        
    bot.loop.create_task(github_timer())

@bot.event
async def on_member_join(member):
    print(f"👤 {member.name} joined the server.")
    await update_member_count(member.guild)

@bot.event
async def on_member_remove(member):
    print(f"👤 {member.name} left the server.")
    await update_member_count(member.guild)

# =========================================================================
# 🔑 COMMANDES SLASH (SYSTÈME HWID)
# =========================================================================
@bot.tree.command(name="get_hwid", description="Obtiens le script pour copier ton HWID")
async def get_hwid(interaction: discord.Interaction):
    script = "```lua\nsetclipboard(game:GetService('RbxAnalyticsService'):GetClientId())\n```"
    await interaction.response.send_message(f"🛠️ **Comment obtenir ton HWID ?**\nExécute ce script dans ton exécuteur Roblox. Ton HWID sera copié dans ton presse-papier :\n{script}", ephemeral=True)

@bot.tree.command(name="key", description="Génère ta clé Premium avec ton HWID")
@app_commands.describe(hwid="Ton code HWID (Fais /get_hwid pour l'obtenir)")
async def generate_key(interaction: discord.Interaction, hwid: str):
    # Vérification du rôle
    if not any(role.id == ROLE_PREMIUM_ID for role in interaction.user.roles):
        await interaction.response.send_message("❌ **Accès refusé.** Tu dois avoir le rôle Booster/Premium pour générer une clé.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True) 
    
    db, sha = get_github_db()
    user_id_str = str(interaction.user.id)

    if user_id_str in db:
        user_key = db[user_id_str]["key"]
        db[user_id_str]["hwid"] = hwid 
    else:
        user_key = f"APPLEX-{uuid.uuid4().hex[:8].upper()}"
        db[user_id_str] = {"key": user_key, "hwid": hwid}

    success = update_github_db(db, sha)
    
    if success:
        script_to_copy = f'```lua\n_G.AppleKey = "{user_key}"\nloadstring(game:HttpGet("https://raw.githubusercontent.com/Tamachiru/AppleX/refs/heads/main/Game4"))()\n```'
        await interaction.followup.send(f"✅ **Base de données mise à jour.**\n\nVoici ton script personnel. Ton PC est désormais enregistré.\n{script_to_copy}\n\n*Note : Patiente 1 à 2 minutes pour que GitHub enregistre la modif avant d'injecter.*")
    else:
        await interaction.followup.send("❌ Erreur lors de la sauvegarde sur GitHub. Vérifie le secret GH_API_TOKEN.")

# =========================================================================
# 🛡️ MOTEUR ANTI-LIENS MALVEILLANTS
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
# 🚀 DÉMARRAGE DU BOT
# =========================================================================
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: DISCORD_TOKEN not found. Check your GitHub Secrets.")
