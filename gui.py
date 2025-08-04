import os
import threading
import time
from typing import List
from discord_webhook import DiscordWebhook

import customtkinter
from tkinter import filedialog as FD


from db_utils import UploadedFilesDB, File


class MainWindow(customtkinter.CTk):

    WIDTH = 800
    HEIGHT = 550

    def __init__(self, client_ref, loop):
        super().__init__()

        while client_ref.CONTEXT is None:
            time.sleep(0.1)
        self.loop = loop
        self.CLIENT_REF = client_ref

        print('context achieved')

        customtkinter.set_appearance_mode("System")
        customtkinter.set_default_color_theme("blue")

        self.title("Discord Drive")

        self.minsize(MainWindow.WIDTH, MainWindow.HEIGHT)

        column_weights = [1, 1, 2, 2, 0, 0]
        for i, w in enumerate(column_weights):
            self.grid_columnconfigure(i, weight=w)

        row_weights = [0, 1, 1, 1, 0]
        for i, w in enumerate(row_weights):
            self.grid_rowconfigure(i, weight=w)

        self.db_helper = UploadedFilesDB()
        self.items_list: List[str] = self.db_helper.get_all_names()
        self.choice: str = ""

        # names to show in progress frame
        self.names_uploading_n_downloading_rn: List[str] = []

        self.option_menu = customtkinter.CTkOptionMenu(master=self, values=self.items_list, command=self.handle_selection)
        self.option_menu.grid(row=0, column=0, padx=15, pady=20, columnspan=2, rowspan=1, sticky="news")
        self.option_menu.set("Choose a file")

        self.metadata_frame = customtkinter.CTkFrame(master=self)
        self.metadata_frame.grid(row=1, column=0, padx=15, pady=10, columnspan=2, rowspan=2, sticky="news")

        self.upload_button = customtkinter.CTkButton(master=self, text="Upload a new file", command=self.upload_wrapper, fg_color="green")
        self.upload_button.grid(row=3, column=0, padx=15, pady=20, columnspan=2, rowspan=1, sticky="news")

        # frame items
        self.metadata_frame_name = customtkinter.CTkLabel(master=self.metadata_frame, text="Name: ")
        self.metadata_frame_name.grid(row=0, column=0, padx=15, pady=(10, 5), columnspan=7, rowspan=1, sticky="nws")

        self.metadata_frame_size = customtkinter.CTkLabel(master=self.metadata_frame, text="Size: ")
        self.metadata_frame_size.grid(row=1, column=0, padx=15, pady=5, columnspan=3, rowspan=1, sticky="nws")
        self.metadata_frame_num_segments = customtkinter.CTkLabel(master=self.metadata_frame, text="Segments: ")
        self.metadata_frame_num_segments.grid(row=1, column=4, padx=15, pady=5, columnspan=3, rowspan=1, sticky="nws")

        self.metadata_frame_delete_button = customtkinter.CTkButton(master=self.metadata_frame, text="Delete", command=self.delete_file_wrapper, fg_color="#FF474C", state="disabled")
        self.metadata_frame_delete_button.grid(row=2, column=0, padx=10, pady=(5, 10), columnspan=3, rowspan=1, sticky="news")
        self.metadata_frame_download_button = customtkinter.CTkButton(master=self.metadata_frame, text="Download", command=self.download_wrapper, state="disabled")
        self.metadata_frame_download_button.grid(row=2, column=4, padx=10, pady=(5, 10), columnspan=3, rowspan=1, sticky="news")

        column_weights = [1] * 7
        for i, w in enumerate(column_weights):
            self.metadata_frame.grid_columnconfigure(i, weight=w)

        row_weights = [1] * 3
        for i, w in enumerate(row_weights):
            self.metadata_frame.grid_rowconfigure(i, weight=w)

        # progress frame
        self.progress_frame = customtkinter.CTkScrollableFrame(master=self)
        self.progress_frame.grid(row=0, column=2, padx=15, pady=10, columnspan=4, rowspan=4, sticky="news")

        # log frame
        self.log_frame = customtkinter.CTkScrollableFrame(master=self)
        self.log_frame.grid(row=4, column=0, padx=15, pady=10, columnspan=6, rowspan=1, sticky="news")

    def handle_selection(self, choice: str):
        self.choice = choice
        self.display_metadata()

        self.metadata_frame_delete_button.configure(state="normal")
        self.metadata_frame_download_button.configure(state="normal")

    def delete_selection(self):
        self.items_list.remove(self.choice)
        self.option_menu.configure(values=self.items_list)
        self.option_menu.set("Choose a file")
        self.choice = ""

        self.metadata_frame_delete_button.configure(state="disabled")
        self.metadata_frame_download_button.configure(state="disabled")

        self.metadata_frame_name.configure(text=f"Name: ")
        self.metadata_frame_size.configure(text=f"Size: ")
        self.metadata_frame_num_segments.configure(text=f"Segments: ")

    def delete_file_wrapper(self):
        self.db_helper.delete_file_with_name(self.choice)

        self.delete_selection()

        threading.Thread(target=self.delete_file, daemon=True).start()

    def delete_file(self):
        webhook = DiscordWebhook(url=self.CLIENT_REF.HOOK_URL, content="!Validate", rate_limit_retry=True)
        webhook.execute()

    def update_option_list(self, new_choices: List[str]):
        self.choice = ""
        self.items_list = new_choices
        self.option_menu.configure(values=self.items_list)

    def upload_wrapper(self):
        threading.Thread(target=self.upload, daemon=True).start()

    def upload(self):
        path = MainWindow.open_file_dialog(False, "")
        self.CLIENT_REF.CURRENT_UPLOAD_PATH = path
        webhook = DiscordWebhook(url=self.CLIENT_REF.HOOK_URL, content="!Upload", rate_limit_retry=True)
        webhook.execute()

    def download_wrapper(self):
        name = self.choice
        threading.Thread(target=self.download, args=[name], daemon=True).start()

    def download(self, name):
        path = MainWindow.open_file_dialog(True, "")
        self.CLIENT_REF.CURRENT_NAME_TO_DOWNLOAD = name
        self.CLIENT_REF.CURRENT_SAVE_DIR = path
        webhook = DiscordWebhook(url=self.CLIENT_REF.HOOK_URL, content="!Download", rate_limit_retry=True)
        webhook.execute()

    def display_metadata(self):
        if self.choice == "":
            return
        file: File = self.db_helper.get_file_by_name(self.choice)
        if file is None:
            self.update_option_list(self.items_list)

        self.metadata_frame_name.configure(text=f"Name: {file.name}")
        self.metadata_frame_size.configure(text=f"Size: {convert_size(file.size)}")
        self.metadata_frame_num_segments.configure(text=f"Segments: {len(file.segments)}")

    @staticmethod
    def open_file_dialog(is_folder: bool, start_directory: str) -> str:
        if not start_directory:
            start_directory = os.path.abspath(os.sep)
        if is_folder:
            path = FD.askdirectory(title="Select a Folder", initialdir=start_directory)
        else:
            path = FD.askopenfilename(title="Select a file", initialdir=start_directory)
        if path:
            return path
        else:
            return ""


def convert_size(size: int) -> str:
    bytes_in_gib = 9.313225746154785e-10
    bytes_in_mib = 9.5367431640625e-07
    bytes_in_kib = 9.765625e-4
    if size * bytes_in_gib < 1:
        if size * bytes_in_mib < 1:
            return f"{round(size * bytes_in_kib, 2)} KiB"
        return f"{round(size * bytes_in_mib, 2)} MiB"
    return f"{round(size * bytes_in_gib, 2)} GiB"
