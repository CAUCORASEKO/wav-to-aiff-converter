from pathlib import Path
from PIL import Image, ImageOps
import subprocess
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "docs" / "logo.jpg"
ICONSET = ROOT / "build_assets" / "logo.iconset"
ICNS = ROOT / "build_assets" / "logo.icns"

SIZES = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]

if not LOGO.exists():
    print(f"ERROR: logo not found: {LOGO}")
    sys.exit(1)

if ICONSET.exists():
    shutil.rmtree(ICONSET)

ICONSET.mkdir(parents=True, exist_ok=True)

img = Image.open(LOGO).convert("RGBA")

for size, filename in SIZES:
    output = ICONSET / filename
    fitted = ImageOps.fit(img, (size, size), method=Image.Resampling.LANCZOS)
    fitted.save(output)

subprocess.run(
    ["iconutil", "-c", "icns", str(ICONSET), "-o", str(ICNS)],
    check=True,
)

print(f"Created: {ICNS}")
