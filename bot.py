import asyncio
import re
from pathlib import Path
import threading
import queue

import discord
from discord.ext import commands
from discord_webhook import AsyncDiscordWebhook

from file import upload, File, download
from db_utils import UploadedFilesDB


class MyClient(commands.Bot):
    CONTEXT = None
    db_helper = None

    async def on_ready(self):
        asyncio.create_task(self.set_context())
        print("Logged on as", self.user)

    async def set_context(self):
        webhook = AsyncDiscordWebhook(url=self.HOOK_URL, content="!Hello_there", rate_limit_retry=True)
        await webhook.execute()

    async def validate(self):
        print('called validate')

        # remove files without a channel
        guild = self.CONTEXT.guild
        for checksum in self.db_helper.get_all_checksums():
            existing_channel = discord.utils.get(guild.channels, name=checksum[0])
            if not existing_channel:
                self.db_helper.delete_file_with_checksum(checksum[0])
        # remove channels without a file
        sha256_regex = r"\b[a-f0-9]{64}\b"
        for channel in guild.channels:
            if re.match(sha256_regex, channel.name):
                if not self.db_helper.find_checksum(channel.name):
                    await channel.delete()