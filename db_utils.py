import pickle
import sqlite3
import threading
from typing import Union, List, Any, Dict

from file import File


class Singleton:
    """
    threaded singleton pattern instance for sqlite databases instances
    """
    _instances: Dict[int, Dict[Any, Any]] = dict()

    def __new__(cls, *args, **kwargs):
        thread_id = threading.get_ident()
        if thread_id not in cls._instances:
            cls._instances[thread_id]: Dict[cls, cls] = dict()
        if cls not in cls._instances[thread_id]:
            cls._instances[thread_id][cls] = super().__new__(cls, *args, **kwargs)
        return cls._instances[thread_id][cls]


class UploadedFilesDB(Singleton):
    """
    sqlite database api for accessing or inserting into the database of completed torrents (PickleableFile) for seeding.
    """
    def __init__(self):
        conn = sqlite3.connect('uploaded_files.db')
        # checksum, file name, File object
        conn.cursor().execute('CREATE TABLE IF NOT EXISTS uploaded_files (checksum TEXT PRIMARY KEY, name TEXT, file_object BLOB)')
        conn.commit()
        self.conn = conn

    def insert_file(self, file_object: File):
        params = (file_object.checksum, file_object.name, pickle.dumps(file_object))
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO uploaded_files (checksum, name, file_object) VALUES (?, ?, ?)", params)
        self.conn.commit()

    def get_file_by_name(self, name: str) -> Union[File, None]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT file_object FROM uploaded_files WHERE name=?", (name,))
        file_object = cursor.fetchone()
        if file_object:
            return pickle.loads(file_object[0])
        else:
            return None

    def find_name(self, name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM uploaded_files WHERE name=?", (name,))
        count = cursor.fetchone()[0]
        return count > 0

    def find_checksum(self, name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM uploaded_files WHERE checksum=?", (name,))
        count = cursor.fetchone()[0]
        return count > 0

    def delete_file_with_name(self, name: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM uploaded_files WHERE name=?", (name,))
        self.conn.commit()

    def delete_file_with_checksum(self, checksum: str):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM uploaded_files WHERE checksum=?", (checksum,))
        self.conn.commit()

    def get_all_names(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM uploaded_files")
        return list(map(lambda x: x[0], cursor.fetchall()))

    def get_all_checksums(self) -> List[str]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT checksum FROM uploaded_files")
        return list(map(lambda x: x[0], cursor.fetchall()))

    def __del__(self):
        self.conn.close()
