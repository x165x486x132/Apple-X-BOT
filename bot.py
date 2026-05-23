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

# 🚫 Exact filenames to block ONLY when they are inside a link
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
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="suspicious links"))
    
    # Start the timer as soon as the bot is ready
    bot.loop.create_task(github_timer())

@bot.event
async def on_message(message):
    # Ignore messages from bots
    if message.author.bot:
        return

    # We will store tuples: (filename, full_url) to create clickable links
    detected_data = []

    # Split the message into words to isolate links
    words = message.content.split()

    # Check each word individually
    for word in words:
        # Verify if the word is a URL
        if "http://" in word or "https://" in word:
            # Clean the URL just in case they wrap it in < > to hide previews
            clean_url = word.strip("<>")
            
            # Check if it contains a forbidden filename
            for forbidden_name in FORBIDDEN_FILENAMES:
                if forbidden_name in clean_url:
                    # Avoid duplicates in our list
                    if not any(f == forbidden_name for f, u in detected_data):
                        detected_data.append((forbidden_name, clean_url))

    # If AT LEAST ONE forbidden link is detected, execute the punishment
    if len(detected_data) > 0:
        
        # Format the detected files into AESTHETIC BLUE HYPERLINKS
        # Syntax: [Text to display](URL)
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
                color=0x2b2d31, # A sleek dark gray/black color (Discord's theme) for a premium look, or you can put 0xff0000 for red.
                timestamp=datetime.datetime.now()
            )
            
            # Show the blue clickable links
            embed.add_field(name="📂 Evidence (Clickable Links)", value=detected_list_str, inline=False)
            embed.add_field(name="⚖️ Punishment Applied", value="⏳ **1-Week Timeout**", inline=False)
            
            # Avatar of the culprit as the thumbnail (top right)
            avatar_url = message.author.avatar.url if message.author.avatar else message.author.default_avatar.url
            embed.set_thumbnail(url=avatar_url)
            
            # SHOWCASE: Display the very first forbidden image directly in the Embed
            # (If you don't want the image to be visible to everyone, just delete the line below)
            embed.set_image(url=detected_data[0][1])
            
            embed.set_footer(text="Automated Security System", icon_url=bot.user.avatar.url if bot.user.avatar else None)

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
