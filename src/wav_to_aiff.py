#!/usr/bin/env python3

from pathlib import Path
from typing import Optional, List
import argparse
import shutil
import subprocess
import traceback

try:
    from imageio_ffmpeg import get_ffmpeg_exe
except ImportError:
    get_ffmpeg_exe = None


SUPPORTED_WAV_SUFFIXES = {".wav", ".wave"}
BACKUP_DIR_NAME = "_WAV_BACKUP_AFTER_AIFF"


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


def path_is_inside_backup(path: Path) -> bool:
    return BACKUP_DIR_NAME in path.parts


def find_wav_files(folder: Path, recursive: bool) -> List[Path]:
    if recursive:
        files = [p for p in folder.rglob("*") if p.is_file()]
    else:
        files = [p for p in folder.iterdir() if p.is_file()]

    return sorted(
        p for p in files
        if p.suffix.lower() in SUPPORTED_WAV_SUFFIXES
        and not path_is_inside_backup(p)
    )


def move_to_backup(wav_path: Path) -> Path:
    backup_dir = wav_path.parent / BACKUP_DIR_NAME
    backup_dir.mkdir(exist_ok=True)

    backup_target = backup_dir / wav_path.name

    counter = 1
    while backup_target.exists():
        backup_target = backup_dir / f"{wav_path.stem}_{counter}{wav_path.suffix}"
        counter += 1

    shutil.move(str(wav_path), str(backup_target))
    return backup_target


def finalize_wav_after_valid_aiff(
    wav_path: Path,
    backup_wav: bool,
    delete_wav: bool,
) -> None:
    if backup_wav:
        backup_target = move_to_backup(wav_path)
        print(f"BACKUP: WAV moved to {backup_target}")
    elif delete_wav:
        wav_path.unlink()
        print("DELETE: WAV removed.")
    else:
        print("KEEP: WAV kept. Use --backup-wav or --delete-wav when ready.")


def convert_one_file(
    ffmpeg_cmd: str,
    wav_path: Path,
    delete_wav: bool,
    backup_wav: bool,
    dry_run: bool,
    overwrite: bool,
) -> bool:
    aiff_path = wav_path.with_suffix(".aiff")

    print("")
    print(f"WAV : {wav_path}")
    print(f"AIFF: {aiff_path}")

    if aiff_path.exists() and not overwrite:
        if validate_audio_file(ffmpeg_cmd, aiff_path):
            print("SKIP CONVERSION: AIFF already exists and is valid.")
            if dry_run:
                print("DRY RUN: WAV would be finalized according to selected option.")
            else:
                finalize_wav_after_valid_aiff(
                    wav_path=wav_path,
                    backup_wav=backup_wav,
                    delete_wav=delete_wav,
                )
            return True

        print("ERROR: AIFF already exists but does not validate. Use --overwrite to recreate it.")
        return False

    if dry_run:
        print("DRY RUN: No conversion performed.")
        return True

    result = run_ffmpeg(ffmpeg_cmd, wav_path, aiff_path)

    if result.returncode != 0:
        print("ERROR: FFmpeg conversion failed.")
        print(result.stderr)
        return False

    if not validate_audio_file(ffmpeg_cmd, aiff_path):
        print("ERROR: AIFF output was not created correctly. WAV was kept.")
        return False

    print("OK: AIFF created and verified.")

    finalize_wav_after_valid_aiff(
        wav_path=wav_path,
        backup_wav=backup_wav,
        delete_wav=delete_wav,
    )

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch convert WAV audio files to AIFF safely."
    )

    parser.add_argument("folder", help="Folder containing WAV files.")
    parser.add_argument("--recursive", action="store_true", help="Search inside subfolders.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be converted without changing files.")
    parser.add_argument("--backup-wav", action="store_true", help="Move WAV files to backup after successful conversion.")
    parser.add_argument("--delete-wav", action="store_true", help="Delete WAV files after successful conversion.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing AIFF files.")

    args = parser.parse_args()

    if args.backup_wav and args.delete_wav:
        print("ERROR: Use only one option: --backup-wav or --delete-wav.")
        return 1

    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Folder does not exist: {folder}")
        return 1

    ffmpeg_cmd = get_ffmpeg_command()

    if not ffmpeg_cmd:
        print("ERROR: FFmpeg is not available.")
        print("Run:")
        print("  pip install -r requirements.txt")
        return 1

    print(f"FFmpeg: {ffmpeg_cmd}")

    wav_files = find_wav_files(folder, args.recursive)

    print(f"Folder: {folder}")
    print(f"Recursive: {args.recursive}")
    print(f"WAV files found outside backup folders: {len(wav_files)}")

    if not wav_files:
        return 0

    successful = 0
    failed = 0

    for wav_path in wav_files:
        try:
            ok = convert_one_file(
                ffmpeg_cmd=ffmpeg_cmd,
                wav_path=wav_path,
                delete_wav=args.delete_wav,
                backup_wav=args.backup_wav,
                dry_run=args.dry_run,
                overwrite=args.overwrite,
            )

            if ok:
                successful += 1
            else:
                failed += 1

        except Exception:
            failed += 1
            print("")
            print(f"UNEXPECTED ERROR while processing: {wav_path}")
            print(traceback.format_exc())

    print("")
    print("Done.")
    print(f"Successful items: {successful}")
    print(f"Failed items: {failed}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
