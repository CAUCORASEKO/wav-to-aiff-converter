# Music Genre Cleaner

A minimal macOS music library cleaner for DJs and collectors.

The app helps clean and organize a music folder in place. You select or drag a folder into the app, press Start, and the tool processes the music inside that original folder.

## What it does

- Converts WAV / WAVE files to AIFF
- Verifies that the AIFF file was created correctly
- Moves the original WAV files to macOS Trash after successful conversion
- Keeps FLAC files in their original format
- Keeps MP3 files only when they are 320 kbps or higher
- Moves MP3 files below 320 kbps to macOS Trash
- Reads genre metadata from AIFF, FLAC and MP3 files
- Creates one folder per genre
- Moves tracks into their corresponding genre folder
- Moves tracks with missing genre metadata into `Unknown Genre`
- Removes empty folders and macOS junk-only folders such as `.DS_Store`

## macOS App

The intended final format is a minimal macOS app:

    Music Genre Cleaner.app

Basic workflow:

    Drop music folder -> Start -> Done

The app keeps all organized music inside the original selected folder.

## Safety

The tool does not permanently delete WAV files by default in the app workflow.

Original WAV files and low-quality MP3 files are moved to macOS Trash after validation, so they can still be recovered manually from Trash if needed.

The tool modifies the selected folder, so it is recommended to test first with a copy of a small music folder.

## Supported audio formats

Input / processing:

- WAV
- WAVE
- AIFF
- AIF
- FLAC
- MP3

Output after cleaning:

- AIFF
- FLAC
- MP3 320 kbps
- Genre folders

## Requirements for development

- macOS
- Python 3.11 recommended
- Virtual environment
- Python dependencies from `requirements.txt`

Install dependencies:

    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install --upgrade pip
    pip install -r requirements.txt

## Command-line usage

Run a safe dry run:

    python src/wav_to_aiff.py "$HOME/Desktop/complete" --recursive --clean-library --dry-run

Run the full cleaning pipeline:

    python src/wav_to_aiff.py "$HOME/Desktop/complete" --recursive --clean-library

This will:

- Convert WAV to AIFF
- Move original WAV files to Trash
- Move MP3 files below 320 kbps to Trash
- Organize AIFF, FLAC and MP3 files by genre
- Remove empty folders

## GUI usage

Run the app from source:

    python src/app.py

Then:

1. Drag a music folder into the app
2. Press Start
3. Wait for the process to finish
4. Review the organized genre folders

## Build macOS app

Create the macOS icon from `docs/logo.jpg`:

    python scripts/make_macos_icon.py

Build the app:

    pyinstaller \
      --windowed \
      --name "Music Genre Cleaner" \
      --icon "build_assets/logo.icns" \
      --add-data "docs/logo.jpg:docs" \
      --collect-all imageio_ffmpeg \
      --collect-all tkinterdnd2 \
      --hidden-import send2trash \
      --hidden-import mutagen \
      src/app.py

Open the app:

    open "dist/Music Genre Cleaner.app"

## Build DMG

Create a simple DMG installer:

    rm -rf dmg_root
    mkdir -p dmg_root

    cp -R "dist/Music Genre Cleaner.app" dmg_root/

    hdiutil create \
      -volname "Music Genre Cleaner" \
      -srcfolder dmg_root \
      -ov \
      -format UDZO \
      "dist/Music Genre Cleaner.dmg"

The DMG will be created at:

    dist/Music Genre Cleaner.dmg

## Repository notes

The repository stores source code, documentation, scripts and assets.

Generated build artifacts are ignored:

- `build/`
- `dist/`
- `dmg_root/`
- `build_assets/`
- `*.spec`

## Current status

Early macOS prototype.

The CLI pipeline is working. The GUI app and DMG packaging are being prepared for a simple drag-folder-and-start workflow.
