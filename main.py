import re
import os
import shutil
import traceback
from time import time
import psutil
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import PeerIdInvalid

from helpers.utils import (
    processMediaGroup,
    get_parsed_msg,
    fileSizeLimit,
    getChatMsgID,
    send_media,
    get_readable_file_size,
    get_readable_time,
)

from config import PyroConf
from logger import LOGGER

# Initialize the bot client
bot = Client(
    "media_bot",
    api_id=PyroConf.API_ID,
    api_hash=PyroConf.API_HASH,
    bot_token=PyroConf.BOT_TOKEN,
    workers=1000,
    parse_mode="markdown",
)

# Client for user session
user = Client("user_session", workers=1000, session_string=PyroConf.SESSION_STRING)


def parse_link_or_range(text):
    """
    Parses single links or link ranges from user input.
    Returns a list of expanded links.
    """
    links = []
    lines = text.strip().splitlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match t.me/c/xxx/ID-ID or t.me/xxx/ID-ID
        range_match = re.search(r'(https:\/\/t\.me\/[^\s\/]+\/)(\d+)-(\d+)', line)
        if not range_match:
            range_match = re.search(r'(https:\/\/t\.me\/c\/[^\s\/]+\/)(\d+)-(\d+)')

        if range_match:
            base_url = range_match.group(1)
            start_id = int(range_match.group(2))
            end_id = int(range_match.group(3))
            for i in range(start_id, end_id + 1):
                links.append(f"{base_url}{i}")
        else:
            # Single link
            links.append(line)

    return links


@bot.on_message(filters.command("start") & filters.private)
async def start(bot, message: Message):
    welcome_text = (
        "**👋 Welcome to the Media Downloader Bot!**\n\n"
        "This bot helps you download media from Restricted channels\n"
        "Use /help for more information on how to use this bot."
    )
    await message.reply(welcome_text)


@bot.on_message(filters.command("help") & filters.private)
async def help_command(bot, message: Message):
    help_text = (
        "💡 **How to Use the Bot**\n\n"
        "1. Send the command `/dl post URL` to download media from a specific message.\n"
        "2. The bot will download the media (photos, videos, audio, or documents) also can copy message.\n"
        "3. Make sure the bot and the user client are part of the chat to download the media.\n\n"
        "**Example**: `/dl https://t.me/itsSmartDev/547`\n\n"
        "4. To batch download multiple links, use `/batch [URLs or ranges]`."
    )
    await message.reply(help_text)


@bot.on_message(filters.command("batch") & filters.private)
async def batch_download_media(bot, message: Message):
    if len(message.command) < 2:
        await message.reply("**Provide post URLs or a range of post URLs after the /batch command.**")
        return

    batch_input = message.command[1:]

    # Parse the provided batch input (single links or ranges)
    all_links = []
    for item in batch_input:
        all_links.extend(parse_link_or_range(item))
    
    for link in all_links:
        try:
            chat_id, message_id = getChatMsgID(link)
            chat_message = await user.get_messages(chat_id, message_id)

            LOGGER(__name__).info(f"Downloading media from URL: {link}")

            if chat_message.document or chat_message.video or chat_message.audio:
                # No file size check here, since there is no restriction
                pass

            parsed_caption = await get_parsed_msg(chat_message.caption or "", chat_message.caption_entities)
            parsed_text = await get_parsed_msg(chat_message.text or "", chat_message.entities)

            if chat_message.media_group_id:
                if not await processMediaGroup(user, chat_id, message_id, bot, message):
                    await message.reply("**Could not extract any valid media from the media group.**")
                continue

            elif chat_message.media:
                start_time = time()
                progress_message = await message.reply("**📥 Downloading Progress...**")

                media_path = await chat_message.download()
                LOGGER(__name__).info(f"Downloaded media: {media_path}")

                media_type = (
                    "photo"
                    if chat_message.photo
                    else "video"
                    if chat_message.video
                    else "audio"
                    if chat_message.audio
                    else "document"
                )
                await send_media(
                    bot,
                    message,
                    media_path,
                    media_type,
                    parsed_caption,
                    progress_message,
                    start_time,
                )

                os.remove(media_path)
                await progress_message.delete()

            elif chat_message.text or chat_message.caption:
                await message.reply(parsed_text or parsed_caption)
            else:
                await message.reply("**No media or text found in the post URL.**")

        except PeerIdInvalid:
            await message.reply("**Make sure the user client is part of the chat.**")
        except Exception as e:
            LOGGER(__name__).error(f"Error downloading {link}: {e}")
            error_message = f"**❌ Failed to download {link}: {str(e)}**"
            await message.reply(error_message)


@bot.on_message(filters.command("stats") & filters.private)
async def stats(bot, message: Message):
    current_time = get_readable_time(time() - PyroConf.BOT_START_TIME)
    total, used, free = shutil.disk_usage(".")
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    cpu_usage = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    process = psutil.Process(os.getpid())

    stats = (
        "**≧◉◡◉≦ Bot is Up and Running successfully.**\n\n"
        f"**➜ Bot Uptime:** `{current_time}`\n"
        f"**➜ Total Disk Space:** `{total}`\n"
        f"**➜ Used:** `{used}`\n"
        f"**➜ Free:** `{free}`\n"
        f"**➜ Memory Usage:** `{round(process.memory_info()[0] / 1024**2)} MiB`\n\n"
        f"**➜ Upload:** `{sent}`\n"
        f"**➜ Download:** `{recv}`\n\n"
        f"**➜ CPU:** `{cpu_usage}%` | "
        f"**➜ RAM:** `{memory}%` | "
        f"**➜ DISK:** `{disk}%`"
    )
    await message.reply(stats)


if __name__ == "__main__":
    LOGGER(__name__).info("Bot is starting...")
    user.start()
    bot.run()
    LOGGER(__name__).info("Bot is running!")
