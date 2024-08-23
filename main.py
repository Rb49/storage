import discord


class MyClient(discord.Client):
    async def on_ready(self):
        print('Logged on as', self.user)

    async def on_message(self, message):
        # don't respond to ourselves
        if message.author == self.user:
            return

        if message.content == 'ping':
            await message.channel.send('pong')


if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.message_content = True
    client = MyClient(intents=intents)

    with open('TOKEN', 'r') as f:
        token = f.read()

    client.run(token)


