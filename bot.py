import discord
from discord.ext import commands
import datetime
import os
import asyncio

# Bot permissions configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 🚫 Exact filenames to block (both as attachments and inside links)
FORBIDDEN_FILENAMES = [
    "IMG_7625.jpg",
    "IMG_7632.jpg",
    "IMG_7620.jpg",
    "Untitled.jpg"
]

# The timer that will stop the bot right before the fatal 6h GitHub limit
async def github_timer():
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching: Clean and voluntary shutdown of the bot.")
    await bot.close()

@bot.event
async def on_ready():
    print(f'✅ Operational! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="suspicious links and images"))
    
    # Start the timer as soon as the bot is ready
    bot.loop.create_task(github_timer())

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    trigger_moderation = False
    detected_file = ""

    # 1. Check if any forbidden filename is in the message text (e.g., pasted Discord links)
    for forbidden_name in FORBIDDEN_FILENAMES:
        if forbidden_name in message.content:
            trigger_moderation = True
            detected_file = forbidden_name
            print(f"🔎 Found blacklisted link/text sent by {message.author}: {detected_file}")
            break

    # 2. Check if any forbidden filename is in the attachments (if not caught by step 1)
    if not trigger_moderation and message.attachments:
        for attachment in message.attachments:
            exact_filename = attachment.filename
            print(f"🔎 Scanning file sent by {message.author}: {exact_filename}")
            if exact_filename in FORBIDDEN_FILENAMES:
                trigger_moderation = True
                detected_file = exact_filename
                break

    # If a threat is detected (link OR file), execute the punishment
    if trigger_moderation:
        print(f"🚨 EXACT MATCH FOUND! Triggering moderation for {message.author}...")
        
        try:
            # 1. Delete the entire message instantly
            await message.delete()
            print(f"🗑️ Deleted message from {message.author}")

            # 2. Timeout the member for 1 week
            duration = datetime.timedelta(weeks=1)
            await message.author.timeout(duration, reason="Exact blacklisted file/link detected.")
            print(f"⏳ Timed out {message.author} for 1 week.")

            # 3. Create the stylish embed message
            embed = discord.Embed(
                title="⚠️ Threat Neutralized",
                description=f"An unauthorized file or link from {message.author.mention} has been deleted.",
                color=0xff0000, # Red color code
                timestamp=datetime.datetime.now()
            )
            
            embed.add_field(name="Blocked Content", value=f"`{detected_file}`", inline=False)
            embed.add_field(name="Penalty", value="⏳ **1-week timeout** applied instantly.", inline=False)
            
            # Thumbnail with the culprit's avatar
            avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
            embed.set_thumbnail(url=avatar_url)
            
            # Send the warning in the channel
            await message.channel.send(embed=embed)
            
        except discord.Forbidden:
            print(f"⚠️ ERROR: Missing permissions! The bot role MUST be higher than {message.author}'s role, and have 'Manage Messages' & 'Timeout Members'.")
        except Exception as e:
            print(f"⚠️ System error: {e}")

    await bot.process_commands(message)

# Launch the bot via the GitHub Secret
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: Token not found. Check your GitHub Secrets.")
