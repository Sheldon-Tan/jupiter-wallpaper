"""Measure vortex positions in the playback maps.

The shader places swirls at fixed texture coordinates, so those coordinates have
to be measured from the actual maps instead of assumed.  This tool reports, for
each map, the most contrasty oval in a few latitude bands, in texture uv
(u = x / width, v = 0 at the south pole, 1 at the north pole) -- the same
convention `atmosphere.js` uses for `VORTICES`.

It is a rough finder: verify a reported centre on screen with
`python render_preview.py cassini 0.36 static 0 "mark=u,v"`.
"""

from pathlib import Path
import sys

import numpy as np
from PIL import Image

ASSETS = Path(__file__).resolve().parent / "assets"
MAPS = {
    "cassini": "jupiter_cassini_2000.png",
    "hubble": "jupiter_hubble_2015.png",
    "merged": "jupiter_cassini_juno_8k.png",
}


def box_blur(a: np.ndarray, radius: int) -> np.ndarray:
    """Separable box blur that wraps in x (longitude) and clamps in y."""
    if radius < 1:
        return a
    k = 2 * radius + 1
    pad = np.concatenate([a[:, -radius:], a, a[:, :radius]], axis=1)
    c = np.cumsum(pad, axis=1, dtype=np.float64)
    c = np.concatenate([np.zeros((a.shape[0], 1)), c], axis=1)
    out = (c[:, k:] - c[:, :-k]) / k
    pad = np.concatenate([np.repeat(out[:1], radius, 0), out,
                          np.repeat(out[-1:], radius, 0)], axis=0)
    c = np.cumsum(pad, axis=0, dtype=np.float64)
    c = np.concatenate([np.zeros((1, out.shape[1])), c], axis=0)
    return ((c[k:] - c[:-k]) / k).astype(np.float32)


def load(name: str) -> np.ndarray:
    with Image.open(ASSETS / name) as image:
        image = image.convert("RGB")
        # Longitude is the sensitive axis; keep it wide for stable centroids.
        width = 1440
        height = round(image.height * width / image.width)
        small = image.resize((width, height), Image.Resampling.LANCZOS)
        data = np.asarray(small, dtype=np.float32)
    # Image row 0 is the north pole; the shader samples with v pointing north.
    return data[::-1]


def find_oval(score: np.ndarray, lat_range: tuple[float, float]) -> dict | None:
    """Strongest compact anomaly inside a latitude band."""
    height, width = score.shape
    v = (np.arange(height) + 0.5) / height
    lat = (v - 0.5) * 180.0
    band = (lat >= lat_range[0]) & (lat <= lat_range[1])
    masked = np.where(band[:, None], score, -np.inf)
    iy, ix = np.unravel_index(np.argmax(masked), masked.shape)
    peak = float(masked[iy, ix])
    if peak <= 0:
        return None
    # Restrict the region of interest to a local window, otherwise the whole
    # coloured belt wins and the centroid means nothing.
    dy = max(2, int(round(14 / 180 * height)))
    dx = max(4, int(round(0.055 * width)))
    xs = (np.arange(ix - dx, ix + dx + 1)) % width
    ys = np.arange(max(0, iy - dy), min(height, iy + dy + 1))
    window = score[np.ix_(ys, xs)]
    region = window >= 0.55 * peak
    if region.sum() < 6:
        return None
    yy, xx = np.nonzero(region)
    # Wrap-safe centroid in longitude.
    angles = xs[xx] / width * 2 * np.pi
    cu = (np.arctan2(np.sin(angles).mean(), np.cos(angles).mean())
          / (2 * np.pi)) % 1.0
    cv = ys[yy].mean() / height
    half_u = (np.abs(((xs[xx] + 0.5) / width - cu + 0.5) % 1.0 - 0.5).max()
              + 0.5 / width)
    half_v = (yy.max() - yy.min()) / 2 / height
    return {"peak": peak, "u": cu, "v": cv, "ru": half_u, "rv": half_v,
            "lat": (cv - 0.5) * 180.0, "area": int(region.sum())}


def main() -> None:
    names = sys.argv[1:] or list(MAPS)
    for key in names:
        print(f"{key}: {MAPS[key]}")
        data = load(MAPS[key])
        r, g, b = data[..., 0], data[..., 1], data[..., 2]
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        blur = max(3, round(data.shape[0] / 110))
        # Local contrast: subtract the per-latitude median so the bright and
        # dark belts themselves do not dominate the search.
        redness = r - 0.5 * (g + b)
        redness = box_blur(redness - np.median(redness, axis=1, keepdims=True), blur)
        brightness = box_blur(luma - np.median(luma, axis=1, keepdims=True), blur)
        for label, score, band in (
            ("GRS / red oval", redness, (-30, -14)),
            ("white oval (S)", brightness, (-44, -29)),
            ("white oval (N)", brightness, (29, 48)),
            ("dark barge (NEB)", -brightness, (10, 21)),
        ):
            found = find_oval(score, band)
            if not found:
                print(f"  {label}: none")
                continue
            print(f"  {label}: peak {found['peak']:6.1f} "
                  f"uv=({found['u']:.4f}, {found['v']:.4f}) "
                  f"lat={found['lat']:+6.1f} "
                  f"r=({found['ru']:.4f}, {found['rv']:.4f}) "
                  f"area={found['area']}")


if __name__ == "__main__":
    main()
