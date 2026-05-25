import discord
from discord.ext import commands
from discord import app_commands, ui
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

# --- WHITELIST CONFIGURATION ---
REPO_NAME = "x165x486x132/Apple-X-Key"    # Ton dépôt public officiel
FILE_PATH = "hwid_db.json"               
ROLE_PREMIUM_ID = 1498644209840951468    # Rôle Booster/Premium (Donné après achat)
ROLE_BOOSTER_ID = 1055452140522446889    # Second Rôle Booster (Boosters de serveur)
PREMIUM_GAMEPASS_ID = 188694924          # ID de ton GamePass Roblox pour l'achat Premium

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
# 🔍 ROBLOX API: CONVERT USERNAME & CHECK GAMEPASS OWNERSHIP
# =========================================================================
def get_roblox_userid(username):
    url = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": False}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data["data"]:
                return data["data"][0]["id"], data["data"][0]["name"]
    except Exception as e:
        print(f"⚠️ Roblox API Error: {e}")
    return None, None

def check_gamepass_ownership(userid, gamepassid):
    url = f"https://inventory.roblox.com/v1/users/{userid}/items/GamePass/{gamepassid}"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            # If the user owns the gamepass, the data array will have 1 item
            if data and data.get("data") and len(data["data"]) > 0:
                return "owned"
            else:
                return "not_owned"
        elif r.status_code == 403:
            return "private"
    except Exception as e:
        print(f"⚠️ Roblox Inventory API Error: {e}")
    return "error"

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

# --- DISCORD UI: WHITELIST & CLAIM MODAL ---
class WhitelistModal(ui.Modal, title="Apple X Premium Purchase"):
    roblox_username = ui.TextInput(
        label="Roblox Username",
        placeholder="Enter your exact Roblox Username...",
        style=discord.TextStyle.short,
        min_length=3,
        max_length=20,
        required=True
    )
    hwid_input = ui.TextInput(
        label="Roblox HWID",
        placeholder="Paste your Roblox ClientId/HWID here...",
        style=discord.TextStyle.short,
        min_length=15,
        max_length=100,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        username = self.roblox_username.value.strip()
        raw_hwid = self.hwid_input.value
        cleaned_hwid = raw_hwid.strip().upper().replace("{", "").replace("}", "").replace(" ", "")
        
        # 1. Convertit le pseudo en UserID Roblox
        roblox_id, real_username = get_roblox_userid(username)
        if not roblox_id:
            await interaction.followup.send(f"❌ **Roblox account '{username}' not found.** Check the spelling and try again.", ephemeral=True)
            return

        # 2. Vérifie la possession du GamePass
        ownership_status = check_gamepass_ownership(roblox_id, PREMIUM_GAMEPASS_ID)
        
        if ownership_status == "not_owned":
            await interaction.followup.send(f"❌ **Access Denied.** You do not own the required GamePass on Roblox. Please purchase it first!", ephemeral=True)
            return
        elif ownership_status == "private":
            await interaction.followup.send(
                "🔒 **Your Roblox inventory is private!**\n\n"
                "To verify your purchase, the bot must see your inventory:\n"
                "1. Go to **Roblox Settings -> Privacy**.\n"
                "2. Set **'Who can see my inventory?'** to **'Everyone'**.\n"
                "3. Try whitelisting again.\n"
                "*(You can set it back to private after verification).* ", 
                ephemeral=True
            )
            return
        elif ownership_status == "error":
            await interaction.followup.send("❌ Roblox API error. Please try again in a few minutes.", ephemeral=True)
            return

        # 3. Si l'achat est validé, on l'attribue et on donne le rôle Discord
        guild = interaction.guild
        member = await guild.fetch_member(interaction.user.id)
        
        # Attribution automatique du rôle Discord Premium
        role = guild.get_role(ROLE_PREMIUM_ID)
        if role and role not in member.roles:
            await member.add_roles(role)
            print(f"🎁 Automatically granted Premium role to {member.name} via verification.")

        # Sauvegarde en base de données sur GitHub
        db, sha = get_github_db()
        user_id_str = str(interaction.user.id)
        db[user_id_str] = {
            "hwid": cleaned_hwid,
            "username": real_username,
            "role": "Premium"
        }
        
        success = update_github_db(db, sha)
        if success:
            # 🟢 CORRIGÉ : Utilise maintenant Game5
            loader = '```lua\nloadstring(game:HttpGet("https://raw.githubusercontent.com/x165x486x132/AppleX/refs/heads/main/Game5"))()\n```'
            embed = discord.Embed(
                title=f"🍏 Purchase Registered successfully as {self.role_type}!",
                description=f"Thank you for your support, {interaction.user.mention}!\n\n**Registered HWID:** `{cleaned_hwid}`\n\nYou can now execute the loader script directly in Roblox to claim your items:",
                color=0x57F287
            )
            embed.add_field(name="📜 Loader Script", value=loader, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Error saving to GitHub database. Please check if `GH_API_TOKEN` is configured.", ephemeral=True)

# --- DISCORD UI: PANEL BUTTON VIEW ---
class WhitelistView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @ui.button(label="🍏 Unlock Premium", style=discord.ButtonStyle.green, custom_id="whitelist_btn")
    async def whitelist_button(self, interaction: discord.Interaction, button: ui.Button):
        has_premium = any(role.id == ROLE_PREMIUM_ID for role in interaction.user.roles)
        has_booster = any(role.id == ROLE_BOOSTER_ID for role in interaction.user.roles)
        
        if not has_premium and not has_booster:
            await interaction.response.send_message("❌ **Access Denied.** This premium panel is reserved for Server Boosters and Premium users.", ephemeral=True)
            return
        
        role_type = "Premium" if has_premium else "Booster"
        await interaction.response.send_modal(WhitelistModal(role_type))

class AppleXBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WhitelistView())
        await self.tree.sync()
        print("✅ Slash commands and UI views successfully synchronized.")

bot = AppleXBot()

# =========================================================================
# 🧹 SCAN DE SECURITÉ AU DÉMARRAGE (Toutes les 6h via GitHub Actions)
# =========================================================================
async def cleanup_inactive_premium_users():
    await bot.wait_until_ready()
    await asyncio.sleep(10)
    
    print("🧹 Starting automated premium whitelist cleanup & Roblox claim check...")
    db, sha = get_github_db()
    if not db:
        print("⚠️ Whitelist database empty or could not be fetched. Cleanup aborted.")
        return
        
    if not bot.guilds:
        print("⚠️ Bot is not in any server. Cleanup aborted.")
        return
        
    guild = bot.guilds[0] 
    changed = False
    users_to_remove = []
    
    for user_id_str in list(db.keys()):
        try:
            user_id = int(user_id_str)
            member = await guild.fetch_member(user_id)
            
            # --- CHECK 1 : ROBLOX ROLE RECLAIM SYSTEM ---
            if db[user_id_str].get("pending_role_claim") == True:
                role = guild.get_role(ROLE_PREMIUM_ID)
                if role and role not in member.roles:
                    await member.add_roles(role)
                    print(f"🎁 Automatically granted Premium role to {member.name} (Claimed via Roblox!)")
                
                # Clear the pending flag
                db[user_id_str]["pending_role_claim"] = False
                changed = True

            # --- CHECK 2 : SECURITY CLEANUP ---
            has_premium = any(role.id == ROLE_PREMIUM_ID for role in member.roles)
            has_booster = any(role.id == ROLE_BOOSTER_ID for role in member.roles)
            
            if not has_premium and not has_booster:
                print(f"❌ Removing {member.name} (Discord ID: {user_id_str}) - Missing Access Roles.")
                users_to_remove.append(user_id_str)
            else:
                current_role = "Premium" if has_premium else "Booster"
                if db[user_id_str].get("role") != current_role:
                    db[user_id_str]["role"] = current_role
                    changed = True
                
        except discord.NotFound:
            print(f"❌ Removing Discord ID {user_id_str} - User left the server.")
            users_to_remove.append(user_id_str)
        except Exception as e:
            print(f"⚠️ Error checking Discord ID {user_id_str}: {e}")
            
    for uid in users_to_remove:
        if uid in db:
            del db[uid]
            changed = True
            
    if changed:
        success = update_github_db(db, sha)
        if success:
            print("✅ Whitelist database successfully updated on GitHub.")
        else:
            print("❌ Failed to push cleaned database to GitHub.")
    else:
        print("✨ Whitelist database is already clean.")

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
        print("⏳ Rate limited by Discord API.")
    except Exception as e:
        print(f"⚠️ Failed to update stats channel: {e}")

async def github_timer():
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching. Voluntary graceful shutdown.")
    await bot.close()

# =========================================================================
# 🟢 EVENTS & MONITORING (REAL-TIME WHITELIST REMOVAL)
# =========================================================================
@bot.event
async def on_ready():
    print(f'✅ Bot is online! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="roblox"))
    
    for guild in bot.guilds:
        await update_member_count(guild)
        
    bot.loop.create_task(github_timer())
    bot.loop.create_task(cleanup_inactive_premium_users())

# Si un membre perd ses deux rôles d'accès, il est retiré à la seconde !
@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        before_had_access = any(role.id in [ROLE_PREMIUM_ID, ROLE_BOOSTER_ID] for role in before.roles)
        after_has_access = any(role.id in [ROLE_PREMIUM_ID, ROLE_BOOSTER_ID] for role in after.roles)
        
        # 1. Retrait de la whitelist s'il n'a plus aucun rôle requis
        if before_had_access and not after_has_access:
            print(f"🧹 Member {after.name} lost all access roles. Updating database...")
            db, sha = get_github_db()
            user_id_str = str(after.id)
            if user_id_str in db:
                del db[user_id_str]
                success = update_github_db(db, sha)
                if success:
                    print(f"❌ Successfully removed {after.name} from whitelist database.")
        
        # 2. Mise à jour dynamique de son statut (ex: s'il passe de Booster à Premium ou inversement)
        elif after_has_access:
            after_premium = any(role.id == ROLE_PREMIUM_ID for role in after.roles)
            current_role = "Premium" if after_premium else "Booster"
            
            db, sha = get_github_db()
            user_id_str = str(after.id)
            if user_id_str in db and db[user_id_str].get("role") != current_role:
                db[user_id_str]["role"] = current_role
                update_github_db(db, sha)
                print(f"🔄 Updated {after.name}'s role status to {current_role}.")

# Si un membre quitte le serveur, il est retiré à la seconde !
@bot.event
async def on_member_remove(member):
    print(f"👤 {member.name} left the server.")
    await update_member_count(member.guild)
    
    db, sha = get_github_db()
    user_id_str = str(member.id)
    if user_id_str in db:
        del db[user_id_str]
        success = update_github_db(db, sha)
        if success:
            print(f"❌ Successfully removed {member.name} from whitelist (Left Server).")

# =========================================================================
# 🛡️ ANTI-MALICIOUS LINK ENGINE (ON MESSAGE)
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
# 👥 NEW SLASH COMMAND: LIST MEMBERS (EPHEMERAL)
# =========================================================================
@bot.tree.command(name="list_members", description="List the members of the current server (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def list_members(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("❌ This command must be used within a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    members = guild.members
    total_members = len(members)

    member_list = []
    for i, member in enumerate(members[:30]):
        member_list.append(f"{i+1}. {member.mention} (`{member.name}`)")

    member_list_str = "\n".join(member_list) if member_list else "No members found."
    
    if total_members > 30:
        member_list_str += f"\n\n*... and {total_members - 30} more members.*"

    embed = discord.Embed(
        title=f"👥 Member List — {guild.name}",
        description=f"Total Members: **{total_members}**\n\n{member_list_str}",
        color=0x2b2d31,
        timestamp=datetime.datetime.now()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Apple X Security System")

    await interaction.followup.send(embed=embed, ephemeral=True)

# =========================================================================
# 🛠️ ADMIN COMMAND: SETUP THE WHITELIST PANEL (ANONYMOUS & REBRANDED)
# =========================================================================
@bot.tree.command(name="setup_panel", description="Send the Premium Panel to the current channel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Whitelist panel successfully sent anonymously!", ephemeral=True)
    
    embed = discord.Embed(
        title="🍏 Apple X — Premium Panel",
        description=(
            "Welcome to the Premium Whitelist area!\n\n"
            "To gain access to the executor loader, you must register your device's unique identifier (HWID).\n\n"
            "👉 **How to whitelist your device:**\n"
            "1. Click the green **Whitelist Device** button below.\n"
            "2. Paste your Roblox HWID into the text field.\n"
            "3. Submit to instantly register your device.\n\n"
            "-# *To copy your HWID in-game, run the helper command:* \n"
            "-# `setclipboard(game:GetService('RbxAnalyticsService'):GetClientId())`"
        ),
        color=0x2b2d31
    )
    embed.set_footer(text="Apple X Security System", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    
    await interaction.channel.send(embed=embed, view=WhitelistView())

bot.run(TOKEN)
