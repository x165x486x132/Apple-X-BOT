import discord
from discord.ext import commands
from discord import app_commands, ui
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

# --- WHITELIST CONFIGURATION ---
REPO_NAME = "x165x486x132/Apple-X-Key"    # 🟢 CORRIGÉ : Dépôt officiel public
FILE_PATH = "hwid_db.json"               
ROLE_PREMIUM_ID = 1498644209840951468    # Premium/Booster Role ID

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
    payload = {"message": "🤖 Update Whitelist Database (Modal Submission)", "content": content_b64}
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

# --- DISCORD UI: WHITELIST MODAL ---
class WhitelistModal(ui.Modal, title="Apple X Premium Whitelist"):
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
        
        raw_hwid = self.hwid_input.value
        # Standardize HWID to uppercase, removing braces and spaces
        cleaned_hwid = raw_hwid.strip().upper().replace("{", "").replace("}", "").replace(" ", "")
        
        db, sha = get_github_db()
        user_id_str = str(interaction.user.id)
        
        # Save registration
        db[user_id_str] = {
            "hwid": cleaned_hwid,
            "username": str(interaction.user)
        }
        
        success = update_github_db(db, sha)
        if success:
            loader = '```lua\nloadstring(game:HttpGet("https://raw.githubusercontent.com/x165x486x132/AppleX/refs/heads/main/Game4"))()\n```'
            embed = discord.Embed(
                title="🍏 Device Whitelisted successfully!",
                description=f"Welcome to Apple X Premium, {interaction.user.mention}!\n\n**Registered HWID:** `{cleaned_hwid}`\n\nYou can now execute the loader script directly in Roblox without any keys:",
                color=0x57F287
            )
            embed.add_field(name="📜 Loader Script", value=loader, inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send("❌ Error saving to GitHub database. Please check if `GH_API_TOKEN` is configured correctly.", ephemeral=True)

# --- DISCORD UI: PANEL BUTTON VIEW ---
class WhitelistView(ui.View):
    def __init__(self):
        super().__init__(timeout=None) 

    @ui.button(label="🍏 Whitelist Device", style=discord.ButtonStyle.green, custom_id="whitelist_btn")
    async def whitelist_button(self, interaction: discord.Interaction, button: ui.Button):
        # Premium Booster role check
        has_role = any(role.id == ROLE_PREMIUM_ID for role in interaction.user.roles)
        if not has_role:
            await interaction.response.send_message("❌ **Access Denied.** This whitelist panel is reserved for Server Boosters and Premium users.", ephemeral=True)
            return
        
        # Open the modal
        await interaction.response.send_modal(WhitelistModal())

class AppleXBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(WhitelistView())
        await self.tree.sync()
        print("✅ Slash commands and UI views successfully synchronized.")

bot = AppleXBot()

# =========================================================================
# 🧹 AUTOMATED PREMIUM CLEANUP (Runs on startup / Every 6 hours)
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
            
            # Check if the user still has the Premium role
            has_role = any(role.id == ROLE_PREMIUM_ID for role in member.roles)
            if not has_role:
                print(f"❌ Removing {member.name} (Discord ID: {user_id_str}) - Missing Premium Role.")
                users_to_remove.append(user_id_str)
                
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
# 🟢 EVENTS
# =========================================================================
@bot.event
async def on_ready():
    print(f'✅ Bot is online! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="roblox"))
    
    for guild in bot.guilds:
        await update_member_count(guild)
        
    bot.loop.create_task(github_timer())
    bot.loop.create_task(cleanup_inactive_premium_users())

# =========================================================================
# 🛠️ ADMIN COMMAND: SETUP THE WHITELIST PANEL
# =========================================================================
@bot.tree.command(name="setup_panel", description="Send the Premium Whitelist Panel to the current channel (Admin only)")
@app_commands.checks.has_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
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
    
    await interaction.response.send_message(embed=embed, view=WhitelistView())

bot.run(TOKEN)
