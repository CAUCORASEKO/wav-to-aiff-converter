#!/usr/bin/env python3

from pathlib import Path
from typing import Optional, List, Iterable
import argparse
import re
import shutil
import subprocess
import traceback

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except ImportError:
    get_ffmpeg_exe = None

try:
    from send2trash import send2trash
except ImportError:
    send2trash = None

try:
    from mutagen import File as mutagen_file
except ImportError:
    mutagen_file = None


WAV_SUFFIXES = {".wav", ".wave"}
AIFF_SUFFIXES = {".aiff", ".aif"}
ORGANIZABLE_SUFFIXES = {".aiff", ".aif", ".flac", ".mp3"}
UNKNOWN_GENRE = "Unknown Genre"
BACKUP_DIR_NAME = "_WAV_BACKUP_AFTER_AIFF"
IGNORABLE_EMPTY_DIR_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", "Icon\r"}


def get_ffmpeg_command() -> Optional[str]:
    system_ffmpeg = shutil.which("ffmpeg")

    if system_ffmpeg:
        return system_ffmpeg

    if get_ffmpeg_exe is not None:
        return get_ffmpeg_exe()

    return None


def run_command(command: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_ffmpeg(ffmpeg_cmd: str, wav_path: Path, aiff_path: Path) -> subprocess.CompletedProcess:
    command = [
        ffmpeg_cmd,
        "-y",
        "-i",
        str(wav_path),
        "-map_metadata",
        "0",
        "-c:a",
        "pcm_s24be",
        str(aiff_path),
    ]

    return run_command(command)


def validate_audio_file(ffmpeg_cmd: str, path: Path) -> bool:
    if not path.exists() or not path.is_file() or path.stat().st_size == 0:
        return False

    command = [
        ffmpeg_cmd,
        "-v",
        "error",
        "-i",
        str(path),
        "-f",
        "null",
        "-",
    ]

    result = run_command(command)
    return result.returncode == 0


def move_to_trash(path: Path) -> None:
    if send2trash is None:
        raise RuntimeError("send2trash is not installed. Run: pip install -r requirements.txt")

    send2trash(str(path))


def path_is_inside_backup(path: Path) -> bool:
    return BACKUP_DIR_NAME in path.parts


def find_files(folder: Path, suffixes: set[str], recursive: bool) -> List[Path]:
    if recursive:
        files = [p for p in folder.rglob("*") if p.is_file()]
    else:
        files = [p for p in folder.iterdir() if p.is_file()]

    return sorted(
        p for p in files
        if p.suffix.lower() in suffixes
        and not path_is_inside_backup(p)
    )


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target

    counter = 1
    while True:
        candidate = target.parent / f"{target.stem}_{counter}{target.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def flatten_metadata_value(value) -> List[str]:
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        items = []
        for item in value:
            items.extend(flatten_metadata_value(item))
        return items

    if hasattr(value, "text"):
        return flatten_metadata_value(value.text)

    return [str(value)]


def clean_genre_name(raw_genre: str) -> str:
    genre = raw_genre.strip()

    if not genre:
        return UNKNOWN_GENRE

    genre = re.split(r"[;/|]", genre)[0].strip()
    genre = re.sub(r'[\\/:*?"<>|]', "-", genre)
    genre = re.sub(r"\s+", " ", genre).strip()

    if not genre:
        return UNKNOWN_GENRE

    return genre[:80]


def get_audio_genre(path: Path) -> str:
    if mutagen_file is None:
        return UNKNOWN_GENRE

    candidates: List[str] = []

    try:
        easy_audio = mutagen_file(path, easy=True)
        if easy_audio is not None and easy_audio.tags:
            for key in ("genre", "GENRE"):
                if key in easy_audio.tags:
                    candidates.extend(flatten_metadata_value(easy_audio.tags.get(key)))
    except Exception:
        pass

    try:
        audio = mutagen_file(path)
        if audio is not None and audio.tags:
            for key in ("genre", "GENRE", "TCON", "\xa9gen"):
                value = audio.tags.get(key)
                candidates.extend(flatten_metadata_value(value))
    except Exception:
        pass

    for candidate in candidates:
        genre = clean_genre_name(candidate)
        if genre != UNKNOWN_GENRE:
            return genre

    return UNKNOWN_GENRE


def get_mp3_bitrate_kbps(path: Path) -> Optional[int]:
    if mutagen_file is None:
        return None

    try:
        audio = mutagen_file(path)
        if audio is None or audio.info is None:
            return None

        bitrate = getattr(audio.info, "bitrate", None)

        if bitrate is None:
            return None

        return round(int(bitrate) / 1000)

    except Exception:
        return None


def convert_wavs_to_aiff(
    folder: Path,
    ffmpeg_cmd: str,
    recursive: bool,
    dry_run: bool,
    overwrite: bool,
    trash_source_wav: bool,
) -> tuple[int, int]:
    wav_files = find_files(folder, WAV_SUFFIXES, recursive)

    print("")
    print(f"WAV files found: {len(wav_files)}")

    successful = 0
    failed = 0

    for wav_path in wav_files:
        try:
            aiff_path = wav_path.with_suffix(".aiff")

            print("")
            print(f"WAV : {wav_path}")
            print(f"AIFF: {aiff_path}")

            if aiff_path.exists() and not overwrite:
                if validate_audio_file(ffmpeg_cmd, aiff_path):
                    print("SKIP CONVERSION: AIFF already exists and is valid.")

                    if trash_source_wav:
                        if dry_run:
                            print("DRY RUN: WAV would be moved to Trash.")
                        else:
                            move_to_trash(wav_path)
                            print("TRASH: WAV moved to macOS Trash.")

                    successful += 1
                    continue

                print("ERROR: Existing AIFF does not validate. Use --overwrite to recreate it.")
                failed += 1
                continue

            if dry_run:
                print("DRY RUN: WAV would be converted to AIFF.")
                if trash_source_wav:
                    print("DRY RUN: WAV would be moved to Trash after AIFF validation.")
                successful += 1
                continue

            result = run_ffmpeg(ffmpeg_cmd, wav_path, aiff_path)

            if result.returncode != 0:
                print("ERROR: FFmpeg conversion failed.")
                print(result.stderr)
                failed += 1
                continue

            if not validate_audio_file(ffmpeg_cmd, aiff_path):
                print("ERROR: AIFF output did not validate. WAV was kept.")
                failed += 1
                continue

            print("OK: AIFF created and verified.")

            if trash_source_wav:
                move_to_trash(wav_path)
                print("TRASH: WAV moved to macOS Trash.")

            successful += 1

        except Exception:
            failed += 1
            print("")
            print(f"UNEXPECTED ERROR while processing WAV: {wav_path}")
            print(traceback.format_exc())

    return successful, failed


def trash_low_quality_mp3(
    folder: Path,
    recursive: bool,
    dry_run: bool,
    min_bitrate_kbps: int,
) -> tuple[int, int]:
    mp3_files = find_files(folder, {".mp3"}, recursive)

    print("")
    print(f"MP3 files found: {len(mp3_files)}")
    print(f"Minimum MP3 bitrate: {min_bitrate_kbps} kbps")

    trashed = 0
    kept = 0

    for mp3_path in mp3_files:
        bitrate = get_mp3_bitrate_kbps(mp3_path)

        if bitrate is None:
            print(f"KEEP: bitrate unknown -> {mp3_path}")
            kept += 1
            continue

        if bitrate < min_bitrate_kbps:
            print(f"LOW QUALITY MP3: {bitrate} kbps -> {mp3_path}")

            if dry_run:
                print("DRY RUN: MP3 would be moved to Trash.")
            else:
                move_to_trash(mp3_path)
                print("TRASH: MP3 moved to macOS Trash.")

            trashed += 1
        else:
            print(f"KEEP: {bitrate} kbps -> {mp3_path}")
            kept += 1

    return trashed, kept


def organize_by_genre(
    folder: Path,
    recursive: bool,
    dry_run: bool,
) -> tuple[int, int]:
    audio_files = find_files(folder, ORGANIZABLE_SUFFIXES, recursive)

    print("")
    print(f"Organizable audio files found: {len(audio_files)}")

    moved = 0
    skipped = 0

    for audio_path in audio_files:
        try:
            if not audio_path.exists():
                skipped += 1
                continue

            genre = get_audio_genre(audio_path)
            genre_folder = folder / genre
            target_path = unique_path(genre_folder / audio_path.name)

            if audio_path.resolve() == target_path.resolve():
                print(f"SKIP: already in correct genre folder -> {audio_path}")
                skipped += 1
                continue

            print("")
            print(f"TRACK: {audio_path}")
            print(f"GENRE: {genre}")
            print(f"MOVE : {target_path}")

            if dry_run:
                print("DRY RUN: Track would be moved.")
                moved += 1
                continue

            genre_folder.mkdir(parents=True, exist_ok=True)
            shutil.move(str(audio_path), str(target_path))
            print("OK: Track moved.")
            moved += 1

        except Exception:
            skipped += 1
            print("")
            print(f"UNEXPECTED ERROR while organizing: {audio_path}")
            print(traceback.format_exc())

    return moved, skipped


def is_ignorable_empty_dir_item(path: Path) -> bool:
    return path.is_file() and path.name in IGNORABLE_EMPTY_DIR_FILES


def remove_empty_folders(folder: Path, dry_run: bool) -> int:
    removed = 0

    folders = sorted(
        [p for p in folder.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    )

    for current_folder in folders:
        if current_folder == folder:
            continue

        try:
            contents = list(current_folder.iterdir())
        except Exception:
            continue

        ignored_items = [
            item for item in contents
            if is_ignorable_empty_dir_item(item)
        ]

        real_items = [
            item for item in contents
            if item not in ignored_items
        ]

        if real_items:
            continue

        print(f"EMPTY OR JUNK-ONLY FOLDER: {current_folder}")

        if ignored_items:
            for item in ignored_items:
                print(f"JUNK FILE: {item}")

        if dry_run:
            print("DRY RUN: Junk files and folder would be removed.")
            removed += 1
            continue

        for item in ignored_items:
            try:
                item.unlink()
                print(f"REMOVE JUNK: {item}")
            except Exception as exc:
                print(f"SKIP JUNK: could not remove {item} ({exc})")

        try:
            current_folder.rmdir()
            print("REMOVE: Empty folder removed.")
            removed += 1
        except Exception as exc:
            print(f"SKIP: folder could not be removed: {current_folder} ({exc})")

    return removed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert WAV to AIFF, remove low-quality MP3, organize music by genre, and clean empty folders."
    )

    parser.add_argument("folder", help="Music folder to process.")
    parser.add_argument("--recursive", action="store_true", help="Search inside subfolders.")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without changing files.")
    parser.add_argument("--clean-library", action="store_true", help="Run the full cleaning pipeline.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing AIFF files.")
    parser.add_argument("--min-mp3-bitrate", type=int, default=320, help="Minimum MP3 bitrate in kbps.")

    args = parser.parse_args()

    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Folder does not exist: {folder}")
        return 1

    if send2trash is None:
        print("ERROR: send2trash is not installed.")
        print("Run: pip install -r requirements.txt")
        return 1

    if mutagen_file is None:
        print("ERROR: mutagen is not installed.")
        print("Run: pip install -r requirements.txt")
        return 1

    ffmpeg_cmd = get_ffmpeg_command()

    if not ffmpeg_cmd:
        print("ERROR: FFmpeg is not available.")
        print("Run: pip install -r requirements.txt")
        return 1

    print(f"FFmpeg: {ffmpeg_cmd}")
    print(f"Folder: {folder}")
    print(f"Recursive: {args.recursive}")
    print(f"Dry run: {args.dry_run}")

    if not args.clean_library:
        print("")
        print("No action selected.")
        print("Use:")
        print('  python src/wav_to_aiff.py "$HOME/Desktop/complete" --recursive --clean-library --dry-run')
        return 0

    total_failed = 0

    wav_ok, wav_failed = convert_wavs_to_aiff(
        folder=folder,
        ffmpeg_cmd=ffmpeg_cmd,
        recursive=args.recursive,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
        trash_source_wav=True,
    )

    total_failed += wav_failed

    mp3_trashed, mp3_kept = trash_low_quality_mp3(
        folder=folder,
        recursive=args.recursive,
        dry_run=args.dry_run,
        min_bitrate_kbps=args.min_mp3_bitrate,
    )

    moved, skipped = organize_by_genre(
        folder=folder,
        recursive=args.recursive,
        dry_run=args.dry_run,
    )

    removed_folders = remove_empty_folders(
        folder=folder,
        dry_run=args.dry_run,
    )

    print("")
    print("Library cleaning finished.")
    print(f"WAV converted/handled: {wav_ok}")
    print(f"WAV failed: {wav_failed}")
    print(f"Low-quality MP3 trashed/planned: {mp3_trashed}")
    print(f"MP3 kept: {mp3_kept}")
    print(f"Tracks moved/planned by genre: {moved}")
    print(f"Tracks skipped: {skipped}")
    print(f"Empty folders removed/planned: {removed_folders}")

    return 0 if total_failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
