#!/usr/bin/env python3

from pathlib import Path
import argparse
import shutil
import subprocess
import sys


SUPPORTED_WAV_SUFFIXES = {".wav", ".wave"}


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available in PATH."""
    return shutil.which("ffmpeg") is not None


def run_ffmpeg(wav_path: Path, aiff_path: Path) -> subprocess.CompletedProcess:
    """
    Convert WAV to AIFF using FFmpeg.

    pcm_s24be = 24-bit PCM big-endian, standard AIFF-friendly format.
    """
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(wav_path),
        "-map_metadata",
        "0",
        "-c:a",
        "pcm_s24be",
        str(aiff_path),
    ]

    return subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def is_valid_output_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def find_wav_files(folder: Path, recursive: bool) -> list[Path]:
    if recursive:
        files = [p for p in folder.rglob("*") if p.is_file()]
    else:
        files = [p for p in folder.iterdir() if p.is_file()]

    return sorted(
        p for p in files
        if p.suffix.lower() in SUPPORTED_WAV_SUFFIXES
    )


def move_to_backup(wav_path: Path) -> Path:
    backup_dir = wav_path.parent / "_WAV_BACKUP_AFTER_AIFF"
    backup_dir.mkdir(exist_ok=True)

    backup_target = backup_dir / wav_path.name

    counter = 1
    while backup_target.exists():
        backup_target = backup_dir / f"{wav_path.stem}_{counter}{wav_path.suffix}"
        counter += 1

    shutil.move(str(wav_path), str(backup_target))
    return backup_target


def convert_one_file(
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
        print("SKIP: AIFF already exists. Use --overwrite to replace it.")
        return False

    if dry_run:
        print("DRY RUN: No conversion performed.")
        return True

    result = run_ffmpeg(wav_path, aiff_path)

    if result.returncode != 0:
        print("ERROR: FFmpeg conversion failed.")
        print(result.stderr)
        return False

    if not is_valid_output_file(aiff_path):
        print("ERROR: AIFF output was not created correctly. WAV was kept.")
        return False

    print("OK: AIFF created and verified.")

    if backup_wav:
        backup_target = move_to_backup(wav_path)
        print(f"BACKUP: WAV moved to {backup_target}")

    elif delete_wav:
        wav_path.unlink()
        print("DELETE: WAV removed.")

    else:
        print("KEEP: WAV kept. Use --backup-wav or --delete-wav when ready.")

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch convert WAV audio files to AIFF safely."
    )

    parser.add_argument(
        "folder",
        help="Folder containing WAV files.",
    )

    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Search inside subfolders.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be converted without changing files.",
    )

    parser.add_argument(
        "--backup-wav",
        action="store_true",
        help="Move WAV files to a backup folder after successful conversion.",
    )

    parser.add_argument(
        "--delete-wav",
        action="store_true",
        help="Delete WAV files after successful conversion.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing AIFF files.",
    )

    args = parser.parse_args()

    if args.backup_wav and args.delete_wav:
        print("ERROR: Use only one option: --backup-wav or --delete-wav.")
        return 1

    folder = Path(args.folder).expanduser().resolve()

    if not folder.exists() or not folder.is_dir():
        print(f"ERROR: Folder does not exist: {folder}")
        return 1

    if not check_ffmpeg():
        print("ERROR: FFmpeg is not installed or not available in PATH.")
        print("Install it with:")
        print("  brew install ffmpeg")
        return 1

    wav_files = find_wav_files(folder, args.recursive)

    print(f"Folder: {folder}")
    print(f"Recursive: {args.recursive}")
    print(f"WAV files found: {len(wav_files)}")

    if not wav_files:
        return 0

    converted = 0
    failed = 0

    for wav_path in wav_files:
        ok = convert_one_file(
            wav_path=wav_path,
            delete_wav=args.delete_wav,
            backup_wav=args.backup_wav,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )

        if ok:
            converted += 1
        else:
            failed += 1

    print("")
    print("Done.")
    print(f"Successful/skipped dry-run items: {converted}")
    print(f"Failed/skipped existing items: {failed}")

    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
