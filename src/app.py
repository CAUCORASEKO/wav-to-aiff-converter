#!/usr/bin/env python3

from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
except ImportError:
    TkinterDnD = None
    DND_FILES = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

from wav_to_aiff import (
    convert_wavs_to_aiff,
    get_ffmpeg_command,
    organize_by_genre,
    remove_empty_folders,
    trash_low_quality_mp3,
)


APP_NAME = "Music Genre Cleaner"


def resource_path(relative_path: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path

    return Path(__file__).resolve().parents[1] / relative_path


class StdoutRedirector:
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, text):
        if text:
            self.log_queue.put(text)

    def flush(self):
        pass


class MusicCleanerApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("720x560")
        self.root.resizable(True, True)

        self.selected_folder = tk.StringVar(value="")
        self.is_running = False
        self.log_queue = queue.Queue()
        self.logo_image = None
        self.window_icon_image = None

        self.set_window_icon()
        self.build_ui()
        self.poll_log_queue()

    def load_logo_image(self, max_size=(140, 140)):
        logo_path = resource_path("docs/logo.jpg")

        if Image is None or ImageTk is None or not logo_path.exists():
            return None

        img = Image.open(logo_path).convert("RGBA")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)

    def set_window_icon(self):
        icon = self.load_logo_image((256, 256))

        if icon is not None:
            self.window_icon_image = icon
            self.root.iconphoto(True, self.window_icon_image)

    def build_ui(self):
        container = tk.Frame(self.root, padx=24, pady=20)
        container.pack(fill="both", expand=True)

        logo = self.load_logo_image((120, 120))

        if logo is not None:
            self.logo_image = logo
            logo_label = tk.Label(container, image=self.logo_image)
            logo_label.pack(anchor="center", pady=(0, 8))

        title = tk.Label(
            container,
            text=APP_NAME,
            font=("Helvetica", 22, "bold"),
        )
        title.pack(anchor="center")

        subtitle = tk.Label(
            container,
            text="Drop a music folder, then press Start.",
            font=("Helvetica", 13),
        )
        subtitle.pack(anchor="center", pady=(6, 18))

        self.drop_area = tk.Label(
            container,
            text="Drop folder here\nor click Choose Folder",
            relief="ridge",
            borderwidth=2,
            height=5,
            font=("Helvetica", 16),
            padx=20,
            pady=20,
        )
        self.drop_area.pack(fill="x", pady=(0, 12))

        if TkinterDnD is not None:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind("<<Drop>>", self.on_drop)

        choose_button = tk.Button(
            container,
            text="Choose Folder",
            command=self.choose_folder,
            height=2,
        )
        choose_button.pack(fill="x")

        folder_label = tk.Label(
            container,
            textvariable=self.selected_folder,
            wraplength=650,
            anchor="w",
            justify="left",
        )
        folder_label.pack(fill="x", pady=(10, 10))

        self.start_button = tk.Button(
            container,
            text="Start",
            command=self.start_cleaning,
            height=2,
            font=("Helvetica", 14, "bold"),
        )
        self.start_button.pack(fill="x", pady=(0, 14))

        self.log_box = scrolledtext.ScrolledText(
            container,
            height=12,
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True)

        self.log(
            "Ready.\n"
            "Process: WAV → AIFF, WAV to Trash, remove MP3 below 320 kbps, "
            "organize AIFF/FLAC/MP3 by genre, remove empty folders.\n"
        )

    def log(self, text):
        self.log_box.insert("end", text)
        self.log_box.see("end")

    def poll_log_queue(self):
        try:
            while True:
                text = self.log_queue.get_nowait()
                self.log(text)
        except queue.Empty:
            pass

        self.root.after(100, self.poll_log_queue)

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Choose music folder")
        if folder:
            self.selected_folder.set(folder)

    def on_drop(self, event):
        try:
            paths = self.root.tk.splitlist(event.data)

            if not paths:
                return

            folder = Path(paths[0])

            if folder.is_file():
                folder = folder.parent

            self.selected_folder.set(str(folder))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not read dropped folder:\n{exc}")

    def start_cleaning(self):
        if self.is_running:
            return

        folder_text = self.selected_folder.get().strip()

        if not folder_text:
            messagebox.showwarning(APP_NAME, "Please choose or drop a music folder first.")
            return

        folder = Path(folder_text).expanduser().resolve()

        if not folder.exists() or not folder.is_dir():
            messagebox.showerror(APP_NAME, f"Invalid folder:\n{folder}")
            return

        answer = messagebox.askyesno(
            APP_NAME,
            "This will modify the selected folder:\n\n"
            "- Convert WAV to AIFF\n"
            "- Move original WAV files to Trash\n"
            "- Move MP3 below 320 kbps to Trash\n"
            "- Organize AIFF, FLAC and MP3 by genre\n"
            "- Remove empty folders\n\n"
            "Continue?",
        )

        if not answer:
            return

        self.is_running = True
        self.start_button.config(text="Running...", state="disabled")
        self.log_box.delete("1.0", "end")

        worker = threading.Thread(
            target=self.run_cleaning_pipeline,
            args=(folder,),
            daemon=True,
        )
        worker.start()

    def run_cleaning_pipeline(self, folder: Path):
        old_stdout = sys.stdout
        old_stderr = sys.stderr

        sys.stdout = StdoutRedirector(self.log_queue)
        sys.stderr = StdoutRedirector(self.log_queue)

        try:
            print(f"Folder: {folder}")
            print("Starting cleaning pipeline...\n")

            ffmpeg_cmd = get_ffmpeg_command()

            if not ffmpeg_cmd:
                print("ERROR: FFmpeg is not available.")
                return

            print(f"FFmpeg: {ffmpeg_cmd}")

            wav_ok, wav_failed = convert_wavs_to_aiff(
                folder=folder,
                ffmpeg_cmd=ffmpeg_cmd,
                recursive=True,
                dry_run=False,
                overwrite=False,
                trash_source_wav=True,
            )

            mp3_trashed, mp3_kept = trash_low_quality_mp3(
                folder=folder,
                recursive=True,
                dry_run=False,
                min_bitrate_kbps=320,
            )

            moved, skipped = organize_by_genre(
                folder=folder,
                recursive=True,
                dry_run=False,
            )

            removed_folders = remove_empty_folders(
                folder=folder,
                dry_run=False,
            )

            print("\nDone.")
            print(f"WAV converted/handled: {wav_ok}")
            print(f"WAV failed: {wav_failed}")
            print(f"Low-quality MP3 moved to Trash: {mp3_trashed}")
            print(f"MP3 kept: {mp3_kept}")
            print(f"Tracks moved by genre: {moved}")
            print(f"Tracks skipped: {skipped}")
            print(f"Empty folders removed: {removed_folders}")

            self.root.after(
                0,
                lambda: messagebox.showinfo(APP_NAME, "Library cleaning finished."),
            )

        except Exception as exc:
            print(f"\nERROR: {exc}")
            self.root.after(
                0,
                lambda: messagebox.showerror(APP_NAME, f"Error:\n{exc}"),
            )

        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            self.root.after(0, self.finish_run)

    def finish_run(self):
        self.is_running = False
        self.start_button.config(text="Start", state="normal")


def main():
    if TkinterDnD is not None:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    MusicCleanerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
