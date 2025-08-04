import hashlib
import io
from pathlib import Path
from typing import Generator, Union
import os
import gc
import discord
import asyncio
from dataclasses import dataclass

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes

MAX_SIZE = 10 * 1024 * 1024  # discord's max file upload size


@dataclass(slots=True)
class Segment:
    name: str
    checksum: str
    iv: bytes
    key: bytes


@dataclass(slots=True)
class File:
    name: str
    segments: list[Segment]
    checksum: str
    size: int

    def __repr__(self) -> str:
        return (f"name: \n{self.name}" +
                "\nsegments:\n" + "\n".join(seg.name for seg in self.segments) +
                f"\nchecksum: \n{self.checksum}" +
                f"\nsize:  \n{self.size}")


def get_slice(path: str) -> Generator[bytes, None, None]:
    """
    given a path return the next MAX_SIZE limit segment
    :param path: abs path of file
    :return: binary data
    """
    try:
        if "nt" == os.name:
            fd = os.open(path, os.O_RDONLY | os.O_BINARY)
        else:
            fd = os.open(path, os.O_RDONLY)
    except (OSError, PermissionError):
        return

    try:
        while True:
            data = os.read(fd, MAX_SIZE)
            if not data:
                break
            yield data
    finally:
        os.close(fd)


async def send_segments(ctx, path: str, queue) -> Union[tuple[File, bool], int]:
    """
    splits the file into segments, encrypts it and sends it to the message's channel
    """
    checksum = get_checksum(path)

    # create channel
    if not await create_channel(ctx, checksum):
        return 0

    segments_names = []

    tasks = []
    checks = []
    size = 0

    for index, bin_data in enumerate(get_slice(path)):
        size += len(bin_data)

        # create filename
        name = hashlib.new('sha256')
        name.update(bin_data)
        piece_checksum = name.copy()
        name.update(os.urandom(32))
        name = name.hexdigest()

        if len(bin_data) < MAX_SIZE:
            bin_data += b"1" + b"0" * (MAX_SIZE - len(bin_data) - 1)

        # encrypt slice
        key, iv = get_random_bytes(32), get_random_bytes(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)

        bin_data = pad(bin_data, AES.block_size)
        bin_data = cipher.encrypt(bin_data)
        file_like_object = io.BytesIO(bin_data)

        file = discord.File(file_like_object, filename=name)
        checks.append(False)
        tasks.append(asyncio.create_task(
            send(discord.utils.get(ctx.guild.channels, name=checksum), Path(path).name, name, file, checks, index,
                 queue)))

        if index % 3 == 0:
            await asyncio.gather(*tasks)
            tasks = []

        segments_names.append(Segment(name, piece_checksum.hexdigest(), iv, key))
        del name, iv, key
        gc.collect()

    await asyncio.gather(*tasks)
    del tasks
    file_obj = File(Path(path).name, segments_names, checksum, size)
    return file_obj, all(checks) and len(checks) == len(file_obj.segments) and size


async def send(channel: discord.TextChannel, file_name: str, obs_name: str, file: discord.File,
               checks: list[bool], index: int, queue, retry: int = 1):
    try:
        await channel.send(content=obs_name, file=file)
        checks[index] = True
        queue.put({"file name": file_name, "action": ("upload", "segment")})
    except Exception as e:
        if retry == 3:
            print(f"Upload failed due to {e}")
            # TODO terminate upload
            ...
        else:
            await send(channel, file_name, obs_name, file, checks, index, queue, retry + 1)
    finally:
        del file
        gc.collect()


async def download(ctx, save_path: str, file: File, queue) -> bool:
    new_path = os.path.join(save_path, file.name)
    try:
        if "nt" == os.name:
            fd = os.open(new_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_BINARY)
        else:
            fd = os.open(new_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except (OSError, PermissionError, FileExistsError):
        return False

    segment_names = list(map(lambda x: x.name, file.segments))
    try:
        channel = discord.utils.get(ctx.guild.channels, name=file.checksum)

        async for message in channel.history(limit=len(file.segments)):
            attachment = message.attachments[0]
            bin_data = await attachment.read()
            index = segment_names.index(attachment.filename)
            print(index)

            # dencrypt slice
            key, iv = file.segments[index].key, file.segments[index].iv
            cipher = AES.new(key, AES.MODE_CBC, iv)

            bin_data = cipher.decrypt(bin_data)
            bin_data: bytes = unpad(bin_data, AES.block_size)

            if index == len(segment_names) - 1:
                last_data_index = len(bin_data.rstrip(b"0"))
                bin_data = bin_data[:last_data_index - 1]

            # validate the piece
            Hash = hashlib.new('sha256')
            Hash.update(bin_data)
            if file.segments[index].checksum != Hash.hexdigest():
                raise Exception

            os.lseek(fd, MAX_SIZE * index, os.SEEK_SET)
            os.write(fd, bin_data)
            del key, iv
            queue.put({"file name": file.name, "action": ("download", "segment")})

        # validate the entire file
        if file.checksum != get_checksum(new_path):
            raise Exception


    except Exception as e:
        print(f"Download failed: {e}")
        os.close(fd)
        os.remove(new_path)
        return False

    print('done')
    os.close(fd)
    return True


def get_checksum(path: str) -> str:
    checksum = hashlib.new('sha256')

    for bin_data in get_slice(path):
        checksum.update(bin_data)
    return checksum.hexdigest()


async def create_channel(ctx, channel_name: str) -> bool:
    guild = ctx.guild
    existing_channel = discord.utils.get(guild.channels, name=channel_name)

    if existing_channel:
        return False
    else:

        bot_member = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            # deny access to everyone
            bot_member: discord.PermissionOverwrite(read_messages=True, send_messages=True)  # allow bot access
        }

        # create a new text channel
        await guild.create_text_channel(name=channel_name, overwrites=overwrites)

        return True
