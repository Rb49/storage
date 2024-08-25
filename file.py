import hashlib
import io
from typing import Generator, List
import os
import discord
import asyncio


MAX_SIZE = 26214400  # 25MB in binary


def get_slice(path: str) -> Generator[bytes, None, None]:
    """
    given a path return the next MAX_SIZE limit segment
    :param path: abs path of file
    :return: binary data
    """
    try:
        if "nt" == os.name:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_BINARY)
        else:
            fd = os.open(path, os.O_RDWR | os.O_CREAT)
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


async def send_segments(message, path: str) -> None:
    for bin_data in get_slice(path):
        file_like_object = io.BytesIO(bin_data)
        # create filename
        name = hashlib.new('sha256')
        name.update(bin_data)
        name.update(os.urandom(64))
        name = name.hexdigest()

        file = discord.File(file_like_object, filename=name)
        asyncio.create_task(message.channel.send(file=file))
        del file





