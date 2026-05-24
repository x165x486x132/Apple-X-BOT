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

# 🚫 Exact filenames to block ONLY when they are inside a link (includes .jpg and .jpeg)
FORBIDDEN_FILENAMES = [
    "IMG_7625.jpg", "IMG_7625.jpeg",
    "IMG_7632.jpg", "IMG_7632.jpeg",
    "IMG_7620.jpg", "IMG_7620.jpeg",
    "Untitled.jpg", "Untitled.jpeg",
    "image.jpg", "image.jpeg"
]

# 🚫 Specific links, domains, or keywords to block
FORBIDDEN_LINKS = [
    "roblox-scam.com",    # Exemple de faux site
    "discord-nitro.gift", # Exemple de faux lien
    "steamspecial.com"    # Ajoute les liens que tu veux bloquer ici !
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
        word_lower = word.lower()
        clean_url = word.strip("<>")
        
        # 1. Check for forbidden domains/links (even without http://)
        for forbidden_link in FORBIDDEN_LINKS:
            if forbidden_link.lower() in word_lower:
                if not any(f == forbidden_link for f, u in detected_data):
                    detected_data.append((forbidden_link, clean_url))

        # 2. Check for specific filenames (usually in http/https links)
        if "http://" in word_lower or "https://" in word_lower:
            for forbidden_name in FORBIDDEN_FILENAMES:
                # We use .lower() here to catch variants like "IMAGE.JPEG"
                if forbidden_name.lower() in clean_url.lower():
                    if not any(f == forbidden_name for f, u in detected_data):
                        detected_data.append((forbidden_name, clean_url))

    # If AT LEAST ONE forbidden link or image is detected
    if len(detected_data) > 0:
        
        # Format the detected files/links into AESTHETIC BLUE HYPERLINKS
        # If it's not a full URL, we just display it as text to avoid broken Discord links
        detected_list_str = "\n".join([f"🔗 **[{name}]({url if 'http' in url else 'https://'+url})**" for name, url in detected_data])
        
        try:
            # 1. Delete the entire message instantly
            await message.delete()
            print(f"🗑️ Deleted message from {message.author}")

            # 2. Timeout the member for 1 week
            duration = datetime.timedelta(weeks=1)
            await message.author.timeout(duration, reason="Blacklisted link/image detected.")
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
            
            # Showcase the image ONLY if one of the triggers was an image filename
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

# --- 🚀 RUN THE BOT ---
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: Token not found. Check your GitHub Secrets.")
