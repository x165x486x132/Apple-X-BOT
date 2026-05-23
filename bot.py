import discord
from discord.ext import commands
import datetime
import os
import asyncio

# Bot permissions configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # REQUIRED for member count and join/leave events

bot = commands.Bot(command_prefix="!", intents=intents)

# 🚫 Exact filenames to block ONLY when they are inside a link
FORBIDDEN_FILENAMES = [
    "IMG_7625.jpg",
    "IMG_7632.jpg",
    "IMG_7620.jpg",
    "Untitled.jpg"
]

# Fetch the Stats Channel ID from GitHub Secrets
STATS_CHANNEL_ID = os.getenv("CHANNEL_ID")

# --- 📊 MEMBER COUNT UPDATE FUNCTION ---
async def update_member_count(guild):
    if not STATS_CHANNEL_ID:
        return
        
    try:
        channel_id = int(STATS_CHANNEL_ID)
        channel = guild.get_channel(channel_id)
        
        if channel:
            member_count = guild.member_count
            new_name = f"👥 Members: {member_count}"
            
            # Check if the name actually needs to be changed
            if channel.name != new_name:
                await channel.edit(name=new_name)
                print(f"📊 Updated stats channel to: {new_name}")
    except discord.RateLimited:
        print("⏳ Rate limited by Discord for channel renaming (Limit is 2 per 10 mins). Retrying later...")
    except Exception as e:
        print(f"⚠️ Failed to update stats channel: {e}")

# --- ⏳ GITHUB ACTIONS TIMER ---
async def github_timer():
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching: Clean and voluntary shutdown of the bot.")
    await bot.close()

# --- 🟢 ON READY EVENT ---
@bot.event
async def on_ready():
    print(f'✅ Operational! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="roblox"))
    
    # Update the member count as soon as the bot boots up
    for guild in bot.guilds:
        await update_member_count(guild)
        
    # Start the timer
    bot.loop.create_task(github_timer())

# --- ➕ ON MEMBER JOIN ---
@bot.event
async def on_member_join(member):
    print(f"👤 {member.name} joined the server.")
    await update_member_count(member.guild)

# --- ➖ ON MEMBER LEAVE ---
@bot.event
async def on_member_remove(member):
    print(f"👤 {member.name} left the server.")
    await update_member_count(member.guild)

# --- 🛡️ ANTI-MALICIOUS LINK ENGINE ---
@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    detected_data = []

    # Split the message into words to isolate links
    words = message.content.split()

    # Check each word individually
    for word in words:
        if "http://" in word or "https://" in word:
            clean_url = word.strip("<>")
            
            for forbidden_name in FORBIDDEN_FILENAMES:
                if forbidden_name in clean_url:
                    if not any(f == forbidden_name for f, u in detected_data):
                        detected_data.append((forbidden_name, clean_url))

    # If AT LEAST ONE forbidden link is detected
    if len(detected_data) > 0:
        
        # Format the detected files into AESTHETIC BLUE HYPERLINKS
        detected_list_str = "\n".join([f"🔗 **[{name}]({url})**" for name, url in detected_data])
        
        try:
            # 1. Delete the entire message instantly
            await message.delete()
            print(f"🗑️ Deleted message from {message.author}")

            # 2. Timeout the member for 1 week
            duration = datetime.timedelta(weeks=1)
            await message.author.timeout(duration, reason="Blacklisted link detected.")
            print(f"⏳ Timed out {message.author} for 1 week.")

            # 3. Create the PREMIUM stylish embed message
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
            
            # Showcase the very first forbidden image directly
            embed.set_image(url=detected_data[0][1])
            
            embed.set_footer(text="Automated Security System", icon_url=bot.user.avatar.url if bot.user.avatar else None)

            await message.channel.send(embed=embed)
            
        except discord.Forbidden:
            print(f"⚠️ ERROR: Missing permissions to punish {message.author}!")
        except Exception as e:
            print(f"⚠️ System error: {e}")

    await bot.process_commands(message)

# --- 🚀 RUN THE BOT ---
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: Token not found. Check your GitHub Secrets.")
