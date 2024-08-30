import hashlib
import io
from typing import Generator, Tuple, List
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import discord
import asyncio


MAX_SIZE = 25 * 1024 * 1024  # discord's max file upload size


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


async def send_segments(message: discord.Message, path: str) -> Tuple[List[str], bytes, bytes, bytes]:
    """
    splits the file into segments, encrypts it and sends it to the message's channel
    :param message: message requesting the upload
    :param path: path of file to upload
    :return:
    [0]: names of all segments, in order
    [1]: iv used for encryption
    [2]: key used for encryption.
    [3]: the sha1 checksum of the unencrypted file.
    """
    key, iv = os.urandom(32), os.urandom(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    checksum = hashlib.new('sha256')
    segments_names = []
    for bin_data in get_slice(path):
        # update checksum
        checksum.update(bin_data)

        # encrypt slice
        if len(bin_data) % AES.block_size != 0:
            bin_data = pad(bin_data, AES.block_size)
        bin_data = cipher.encrypt(bin_data)
        file_like_object = io.BytesIO(bin_data)

        # create filename
        name = hashlib.new('sha256')
        name.update(bin_data)
        name.update(os.urandom(32))
        name = name.hexdigest() + '.bin'

        file = discord.File(file_like_object, filename=name)
        asyncio.create_task(message.channel.send(file=file))
        segments_names.append(name)

    return segments_names, iv, key, checksum.digest()


