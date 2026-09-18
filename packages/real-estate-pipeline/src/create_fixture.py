"""Create a synthetic, clearly labeled fixture for offline testing."""

from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "fixtures" / "images"
IMAGES.mkdir(parents=True, exist_ok=True)

PROPERTY = {
    "source_url": "local://synthetic-fixture",
    "address": "100 Example Avenue, Testville",
    "price": "$625,000",
    "beds": 3,
    "baths": 2.5,
    "area_sqft": 2100,
    "features": ["open kitchen", "natural light", "covered patio", "dedicated office"],
    "description": "Synthetic fixture only. Not a real listing.",
}

FONT = ImageFont.load_default()
COLORS = [(34, 74, 110), (172, 116, 62), (65, 104, 75), (103, 78, 133), (133, 83, 67), (62, 112, 119)]
NAMES = ["exterior", "living-room", "kitchen", "office", "patio", "primary-bedroom"]

for index, (name, color) in enumerate(zip(NAMES, COLORS)):
    image = Image.new("RGB", (1600, 1000), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 90, 1510, 910), outline=(245, 245, 245), width=5)
    draw.text((140, 130), "SYNTHETIC FIXTURE — NOT A REAL PROPERTY", fill=(255, 255, 255), font=FONT)
    draw.text((140, 460), name.replace("-", " ").upper(), fill=(255, 255, 255), font=FONT)
    image.save(IMAGES / f"{index + 1:02d}-{name}.png")

(ROOT / "fixtures" / "property.json").write_text(json.dumps(PROPERTY, indent=2), encoding="utf-8")
