"""
Builds a grid contact sheet of the selected frames, with timestamp
labels, so we can eyeball whether the algorithm picked sensible
frames. This is also the best demo artifact for the hackathon.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont


def build_contact_sheet(
    frame_paths: list[str],
    timestamps: list[float],
    output_path: str,
    thumb_size: tuple[int, int] = (320, 180),
    cols: int = 4,
) -> str:
    if not frame_paths:
        raise ValueError("No frames to build a contact sheet from.")

    n = len(frame_paths)
    rows = math.ceil(n / cols)

    sheet_w = cols * thumb_size[0]
    sheet_h = rows * thumb_size[1]
    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(20, 20, 20))
    draw = ImageDraw.Draw(sheet)

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    for i, (path, ts) in enumerate(zip(frame_paths, timestamps)):
        img = Image.open(path).convert("RGB")
        img = img.resize(thumb_size, Image.LANCZOS)

        r, c = divmod(i, cols)
        x, y = c * thumb_size[0], r * thumb_size[1]
        sheet.paste(img, (x, y))

        label = f"{int(ts // 60):02d}:{ts % 60:05.2f}"
        draw.rectangle([x, y, x + 90, y + 26], fill=(0, 0, 0))
        draw.text((x + 4, y + 3), label, fill=(255, 255, 255), font=font)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sheet.save(output_path, quality=90)
    return output_path