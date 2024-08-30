import discord


from file import send_segments


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content == 'ping':
            # Example byte array (binary data)
            path = r"C:\Users\roeyb\Downloads\balenaEtcher-portable.exe"
            path = r"C:\Users\roeyb\Downloads\25MB_file.bin"
            await send_segments(message, path)

            await message.channel.send('pong')


if __name__ == '__main__':
    import tracemalloc
    tracemalloc.start()

    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents)

    with open('TOKEN', 'r') as f:
        token = f.read()

    client.run(token)


