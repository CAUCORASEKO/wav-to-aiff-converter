# WAV to AIFF Converter

A macOS-friendly command-line utility to batch-convert WAV audio files to AIFF safely.

The tool scans a folder, finds `.wav` or `.wave` files, converts them to `.aiff`, verifies that the AIFF output exists, and then optionally backs up or deletes the original WAV files.

## Features

- Batch convert WAV to AIFF
- Optional recursive folder scanning
- Safe dry-run mode
- Keeps WAV files by default
- Optional WAV backup after successful conversion
- Optional WAV deletion after successful conversion
- FFmpeg-based conversion
- Preserves metadata when possible

## Requirements

- macOS
- Python 3
- FFmpeg

Install FFmpeg with Homebrew:

    brew install ffmpeg

## Usage

Dry run:

    python3 src/wav_to_aiff.py "/path/to/music/folder" --recursive --dry-run

Convert and keep WAV files:

    python3 src/wav_to_aiff.py "/path/to/music/folder" --recursive

Convert and move WAV files to backup folders:

    python3 src/wav_to_aiff.py "/path/to/music/folder" --recursive --backup-wav

Convert and delete WAV files after successful AIFF creation:

    python3 src/wav_to_aiff.py "/path/to/music/folder" --recursive --delete-wav

Overwrite existing AIFF files:

    python3 src/wav_to_aiff.py "/path/to/music/folder" --recursive --overwrite

## Safety

The program does not remove WAV files by default.

Use `--backup-wav` first before using `--delete-wav`.
