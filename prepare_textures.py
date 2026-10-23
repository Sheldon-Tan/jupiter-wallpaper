"""Prepare browser textures from NASA TIFFs and the Cassini-Juno composite."""

from pathlib import Path
import numpy as np
from PIL import Image


ASSETS = Path(__file__).resolve().parent / "assets"
MAPS = (
    ("PIA07782_Cassini.tif", "jupiter_cassini_2000.png"),
    ("Hubble_Jupiter_color_global_map_2015a.tif", "jupiter_hubble_2015.png"),
)
MERGED_SOURCE = ASSETS / "jupiter_cassini_juno_14400.png"
MERGED_DESTINATION = ASSETS / "jupiter_cassini_juno_8k.png"


def convert(source: Path, destination: Path) -> None:
    pixels = np.asarray(Image.open(source).convert("RGB"), dtype=np.float32).copy()
    width = pixels.shape[1]
    band = 64
    left = pixels[:, :band].copy()
    right = pixels[:, -band:][:, ::-1].copy()
    common = (left + right) * 0.5
    x = np.arange(band, dtype=np.float32)
    blend = (0.5 + 0.5 * np.cos(np.pi * x / (band - 1)))[None, :, None]
    pixels[:, :band] = left * (1 - blend) + common * blend
    pixels[:, -band:] = (right * (1 - blend) + common * blend)[:, ::-1]
    Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8), "RGB").save(destination, optimize=True)
    print(f"{source.name} -> {destination.name} ({width}x{pixels.shape[0]})")


if __name__ == "__main__":
    for src, dst in MAPS:
        convert(ASSETS / src, ASSETS / dst)
    if MERGED_SOURCE.exists():
        # The published 14400x7200 PNG is costly as a live WebGL texture.
        # 8192x4096 keeps more useful detail than the original 3601x1801 map.
        Image.MAX_IMAGE_PIXELS = 110_000_000
        with Image.open(MERGED_SOURCE) as image:
            image = image.convert("RGB").resize((8192, 4096), Image.Resampling.LANCZOS)
            image.save(MERGED_DESTINATION, optimize=True)
        print(f"{MERGED_SOURCE.name} -> {MERGED_DESTINATION.name} (8192x4096)")
