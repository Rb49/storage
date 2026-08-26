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
from gui import MainWindow


class MyClient(commands.Bot):
    HOOK_URL = ""
    CONTEXT = None
    CURRENT_UPLOAD_PATH = ""
    CURRENT_NAME_TO_DOWNLOAD = ""
    CURRENT_SAVE_DIR = r"C:\Users\roeyb\PycharmProjects\storage"
    db_helper = None
    update_queue = queue.Queue()

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

    async def on_message(self, message: discord.Message):
        async def handler() -> bool:
            nonlocal message
            if message.content == "!Hello_there":
                self.db_helper = UploadedFilesDB()
                # get context
                self.CONTEXT = await self.get_context(message)
                await self.validate()
                return True

            # check commands
            if message.content == "!Upload" and self.CURRENT_UPLOAD_PATH != "":
                # file is not in db
                if self.db_helper.find_name(Path(self.CURRENT_UPLOAD_PATH).name):
                    self.CURRENT_UPLOAD_PATH = ""
                    self.update_queue.put({"file name": Path(self.CURRENT_UPLOAD_PATH).name, "action": ("upload", "failed", "File was already uploaded")})
                    return False
                path = self.CURRENT_UPLOAD_PATH
                self.CURRENT_UPLOAD_PATH = ""

                # was the file uploaded successfully?
                if (not isinstance(file_data := await upload(self.CONTEXT, path, self.update_queue), tuple)) or (not file_data[1]):
                    self.update_queue.put({"file name": Path(path).name, "action": ("upload", "failed", "Upload error")})
                    return False

                file: File = file_data[0]
                self.db_helper.insert_file(file)
                self.update_queue.put({"file name": file.name, "action": ("upload", "success")})
                return True

            if message.content == "!Download" and self.CURRENT_NAME_TO_DOWNLOAD != "":
                name = self.CURRENT_NAME_TO_DOWNLOAD
                # file is in db
                if (file := self.db_helper.get_file_by_name(name)) is None:
                    self.update_queue.put({"file name": name, "action": ("download", "failed", "File was not found")})
                    self.CURRENT_NAME_TO_DOWNLOAD = ""
                    self.CURRENT_SAVE_DIR = ""
                    return False
                self.CURRENT_NAME_TO_DOWNLOAD = ""
                path = self.CURRENT_SAVE_DIR
                self.CURRENT_SAVE_DIR = ""

                # download was not successful
                if not await download(self.CONTEXT, path, file, self.update_queue):
                    self.update_queue.put({"file name": name, "action": ("download", "failed", "Download error. Consider deleting the file")})
                    return False

                self.update_queue.put({"file name": name, "action": ("download", "success")})
                return True

            if message.content == "!Validate":
                await self.validate()
                return True

            # else
            return True

        if not await handler():
            await self.validate()


def run_tkinter_app(Client):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_window = MainWindow(Client, loop)
    main_window.mainloop()
    loop.call_soon_threadsafe(loop.stop)


def run_bot(Client, Bot_token):
    Client.run(Bot_token)


if __name__ == "__main__":
    import tracemalloc
    tracemalloc.start()

    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(command_prefix="!", intents=intents)

    with open("ENV", "r") as f:
        bot_token, MyClient.HOOK_URL = f.read().split("\n")

    tkinter_thread = threading.Thread(target=run_tkinter_app, args=[client], daemon=True)
    tkinter_thread.start()

    bot_thread = threading.Thread(target=run_bot, args=[client, bot_token], daemon=True)
    bot_thread.start()

    tkinter_thread.join()
