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

# 🚫 Exact names of the files to block
FORBIDDEN_FILENAMES = [
    "img_7625.jpg",
    "img_7632.jpg",
    "img_7620.jpg",
    "untitled.jpg"
]

# The timer that will stop the bot right before the fatal 6h GitHub limit
async def github_timer():
    # 5 hours, 58 minutes (358 minutes in total)
    delay_seconds = (5 * 3600) + (58 * 60)
    await asyncio.sleep(delay_seconds)
    print("⏳ 6h limit approaching: Clean and voluntary shutdown of the bot to allow restart without crashing.")
    await bot.close()

@bot.event
async def on_ready():
    print(f'✅ Operational! Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="suspicious images"))
    
    # Start the timer as soon as the bot is ready
    bot.loop.create_task(github_timer())

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # If the message contains attachments (images, files)
    if message.attachments:
        for attachment in message.attachments:
            if attachment.filename.lower() in FORBIDDEN_FILENAMES:
                try:
                    # 1. Delete the image instantly
                    await message.delete()

                    # 2. Timeout the member for 1 week
                    duration = datetime.timedelta(weeks=1)
                    await message.author.timeout(duration, reason="Blacklisted file detected by the system.")

                    # 3. Create the stylish embed message
                    embed = discord.Embed(
                        title="⚠️ Threat Neutralized",
                        description=f"An unauthorized file from {message.author.mention} has been deleted.",
                        color=0xff0000, # Red color code
                        timestamp=datetime.datetime.now()
                    )
                    
                    embed.add_field(name="Blocked File", value=f"`{attachment.filename}`", inline=False)
                    embed.add_field(name="Penalty", value="⏳ **1-week timeout** applied instantly.", inline=False)
                    
                    # Thumbnail with the culprit's avatar
                    avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
                    embed.set_thumbnail(url=avatar_url)
                    
                    # Send the warning in the channel
                    await message.channel.send(embed=embed)
                    
                    # Stop checking other files in the same message to avoid double timeout
                    break

                except discord.Forbidden:
                    print("⚠️ ERROR: The bot must have a role HIGHER than the members, and 'Manage Messages' + 'Timeout Members' permissions.")
                except Exception as e:
                    print(f"⚠️ System error: {e}")

    await bot.process_commands(message)

# Launch the bot via the GitHub Secret
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Error: Token not found.")
