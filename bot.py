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
REPO_NAME = "x165x486x132/Apple-X-Key"    
FILE_PATH = "hwid_db.json"               
ROLE_PREMIUM_ID = 1498644209840951468    # Premium/Booster Role ID
ROLE_BOOSTER_ID = 1055452140522446889    # Second Booster Role ID
PREMIUM_GAMEPASS_ID = 1817589078         # Roblox GamePass ID for the Purchase panel button

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
    payload = {"message": "🤖 Update Whitelist Database", "content": content_b64}
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
class WhitelistModal(ui.Modal):
    def __init__(self, role_type: str):
        super().__init__(title=f"Apple X {role_type} Whitelist")
        self.role_type = role_type
        
        # 🟢 Unique Input Field: Roblox HWID only (No Username required)
        self.hwid_input = ui.TextInput(
            label="Roblox HWID",
            placeholder="Paste your Roblox ClientId/HWID here...",
            style=discord.TextStyle.short,
            min_length=15,
            max_length=100,
            required=True
        )
        self.add_item(self.hwid_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        raw_hwid = self.hwid_input.value
        cleaned_hwid = raw_hwid.strip().upper().replace("{", "").replace("}", "").replace(" ", "")
        
        db, sha = get_github_db()
        user_id_str = str(interaction.user.id)
        
        # Saves Discord username as placeholder to avoid breaking Roblox script logic
        db[user_id_str] = {
            "hwid": cleaned_hwid,
            "username": str(interaction.user),
            "role": self.role_type 
        }
        
        success = update_github_db(db, sha)
        if success:
            loader = '```lua\nloadstring(game:HttpGet("https://raw.githubusercontent.com/x165x486x132/AppleX/refs/heads/main/Game5"))()\n```'
            embed = discord.Embed(
                title=f"🍏 Whitelisted successfully as {self.role_type}!",
                description=f"Welcome to Apple X, {interaction.user.mention}!\n\n**Registered HWID:** `{cleaned_hwid}`\n\nYou can now execute the loader script directly in Roblox to claim your items:",
                color=0x57F287
            )
            embed.add_field(name="📜 Loader Script", value=loader, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Error saving to GitHub database. Please check if `GH_API_TOKEN` is configured correctly.", ephemeral=True)

# --- DISCORD UI: PANEL BUTTON VIEW (WHITELIST) ---
class WhitelistView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @ui.button(label="🍏 Whitelist Device", style=discord.ButtonStyle.green, custom_id="whitelist_btn")
    async def whitelist_button(self, interaction: discord.Interaction, button: ui.Button):
        has_premium = any(role.id == ROLE_PREMIUM_ID for role in interaction.user.roles)
        has_booster = any(role.id == ROLE_BOOSTER_ID for role in interaction.user.roles)
        
        if not has_premium and not has_booster:
            await interaction.response.send_message("❌ **Access Denied.** This premium panel is reserved for Server Boosters and Premium users.", ephemeral=True)
            return
        
        role_type = "Premium" if has_premium else "Booster"
        await interaction.response.send_modal(WhitelistModal(role_type))

# --- DISCORD UI: LINK BUTTON VIEW (PURCHASE INFO) ---
class BuyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Adds a persistent Link Button pointing to your Roblox GamePass
        self.add_item(ui.Button(
            label="🛒 Buy Premium GamePass (15 Robux)",
            style=discord.ButtonStyle.link,
            url=f"https://www.roblox.com/game-pass/{PREMIUM_GAMEPASS_ID}/Premium"
        ))

class AppleXBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WhitelistView())
        self.add_view(BuyView()) # Register the link button view
        await self.tree.sync()
        print("✅ Slash commands and UI views successfully synchronized.")

bot = AppleXBot()

# =========================================================================
# 🧹 SCAN DE SECURITÉ AU DÉMARRAGE (Toutes les 6h via GitHub Actions)
# =========================================================================
async def cleanup_inactive_premium_users():
    await bot.wait_until_ready()
    await asyncio.sleep(10)
    
    print("🧹 Starting automated premium whitelist cleanup...")
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
            print("✅ Database cleanup successfully pushed to GitHub.")
        else:
            print("❌ Failed to push cleaned database to GitHub.")
    else:
        print("✨ Whitelist is already clean.")

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

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        before_had_access = any(role.id in [ROLE_PREMIUM_ID, ROLE_BOOSTER_ID] for role in before.roles)
        after_has_access = any(role.id in [ROLE_PREMIUM_ID, ROLE_BOOSTER_ID] for role in after.roles)
        
        if before_had_access and not after_has_access:
            print(f"🧹 Member {after.name} lost all access roles. Updating database...")
            db, sha = get_github_db()
            user_id_str = str(after.id)
            if user_id_str in db:
                del db[user_id_str]
                success = update_github_db(db, sha)
                if success:
                    print(f"❌ Successfully removed {after.name} from whitelist database.")
        
        elif after_has_access:
            after_premium = any(role.id == ROLE_PREMIUM_ID for role in after.roles)
            current_role = "Premium" if after_premium else "Booster"
            
            db, sha = get_github_db()
            user_id_str = str(after.id)
            if user_id_str in db and db[user_id_str].get("role") != current_role:
                db[user_id_str]["role"] = current_role
                update_github_db(db, sha)
                print(f"🔄 Updated {after.name}'s role status to {current_role}.")

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
        title="👥 Member List — " + guild.name,
        description=f"Total Members: **{total_members}**\n\n{member_list_str}",
        color=0x2b2d31,
        timestamp=datetime.datetime.now()
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text="Apple X Security System")

    await interaction.followup.send(embed=embed, ephemeral=True)

# =========================================================================
# 🛠️ ADMIN COMMAND: SETUP THE WHITELIST PANEL (ANONYMOUS VERSION)
# =========================================================================
@bot.tree.command(name="setup_panel", description="Send the Premium Whitelist Panel to the current channel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    await interaction.response.send_message("✅ Whitelist panel successfully sent anonymously!", ephemeral=True)
    
    embed = discord.Embed(
        title="🍏 Apple X — Premium Whitelist Panel",
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

# =========================================================================
# 🛒 NEW ADMIN COMMAND: SETUP THE BUY INFO PANEL (ANONYMOUS)
# =========================================================================
@bot.tree.command(name="setup_buy_panel", description="Send the Premium Information & Purchase Panel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_buy_panel(interaction: discord.Interaction):
    # Répond de manière éphémère pour confirmer à l'admin
    await interaction.response.send_message("✅ Premium info panel successfully sent anonymously!", ephemeral=True)
    
    embed = discord.Embed(
        title="🍏 How to Get Apple X Premium Access",
        description=(
            "Want to unlock lifetime premium bypasses and elite scripts in Highway Legends? "
            "Choose one of the methods below to gain instant access!\n\n"
            "---"
        ),
        color=0x9F33FF # Couleur violette élégante pour Booster/Premium
    )
    
    embed.add_field(
        name="🚀 Option 1: Boost This Discord Server",
        value=(
            "Boost this Discord server **twice** to instantly unlock the **Booster** role! "
            "You will receive automatic lifetime keyless access to our script."
        ),
        inline=False
    )
    
    embed.add_field(
        name="🛒 Option 2: Buy Roblox GamePass (15 Robux Only!)",
        value=(
            "Purchase the official **Apple X Premium GamePass** on Roblox for only **15 Robux**! "
            "Click the button below to purchase it directly on Roblox."
        ),
        inline=False
    )
    
    embed.add_field(
        name="📩 How to Claim Your Premium Status?",
        value=(
            "• **If you Boosted :** Click the button on our Whitelist Panel to register your device instantly!\n"
            "• **If you bought the GamePass :** DM the Owner / Admin directly with proof of purchase to get your Premium role, or use the Whitelist Panel button to register yourself!\n\n"
            "⚠️ *Always make sure your Roblox Inventory is set to 'Everyone' in your Privacy Settings before whitelisting!*"
        ),
        inline=False
    )
    
    embed.set_footer(text="Apple X Security System", icon_url=bot.user.avatar.url if bot.user.avatar else None)
    
    # Envoie le panneau de manière anonyme dans le salon
    await interaction.channel.send(embed=embed, view=BuyView())

bot.run(TOKEN)
