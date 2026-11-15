"""把 AI 生成的角色圖做成 AR 用的狀態圖：對齊、補嘴型、去背、輸出 WebP。

輸入（design/avatar-source/）：
    greet.png          比 YA、閉嘴
    greet_talking.png  比 YA、張嘴
    talking.png        雙手平放、張嘴
輸出（avatar/）：
    idle.webp / talking.webp / greet.webp / greet_talking.webp

雙手平放的「閉嘴」版沒有直接用生成圖：生成的閉嘴圖身體色塊整個重畫過，
跟張嘴版切換時人物會跳動。所以改用 talking.png 當底，把 greet.png 的閉嘴
嘴巴貼上去（兩張的臉是對齊的）。

用法：python tools/build_avatar.py
需要：pip install pillow numpy scipy
"""
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "design" / "avatar-source"
OUT = ROOT / "avatar"

SIZE = (1086, 1448)               # 生成圖的尺寸；不同的話會先縮放到這個大小
MOUTH = (515, 560, 62, 44)        # 嘴巴橢圓：中心 x, y 與半徑 rx, ry（以 SIZE 為座標）
WEB_WIDTH = 600                   # 網頁用的輸出寬度


def load(name):
    img = Image.open(SRC / name).convert("RGB")
    if img.size != SIZE:
        img = img.resize(SIZE, Image.LANCZOS)
    return np.asarray(img).astype(np.float32)


def paste_mouth(base, mouth_from):
    w, h = SIZE
    yy, xx = np.mgrid[0:h, 0:w]
    cx, cy, rx, ry = MOUTH
    dist = ((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2
    mask = np.clip((1.35 - dist) / 0.35, 0, 1)[..., None]   # 邊緣淡化
    return base * (1 - mask) + mouth_from * mask


def cutout(rgb):
    """去掉白色背景：從外圍連通的白色，加上被圍住但面積夠大的白色區塊（例如腋下）。"""
    bright = rgb.min(axis=2)
    spread = rgb.max(axis=2) - bright
    bg_like = (bright > 232) & (spread < 18)
    labels, _ = ndimage.label(bg_like)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    bg = np.isin(labels, border[border > 0])
    sizes = ndimage.sum(bg_like, labels, range(1, labels.max() + 1))
    bg |= np.isin(labels, np.nonzero(sizes > 300)[0] + 1)   # 眼鏡反光、牙齒等小白點保留
    alpha = 1 - ndimage.gaussian_filter(bg.astype(np.float32), 1.0)
    alpha[ndimage.binary_erosion(bg, iterations=2)] = 0
    return Image.fromarray(np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8), "RGBA")


def main():
    greet = load("greet.png")
    greet_talking = load("greet_talking.png")
    talking = load("talking.png")
    idle = paste_mouth(talking, greet)

    images = {name: cutout(rgb) for name, rgb in {
        "idle": idle, "talking": talking, "greet": greet, "greet_talking": greet_talking,
    }.items()}

    # 四張用同一個裁切範圍，切換時才不會跳動
    boxes = [img.getbbox() for img in images.values()]
    pad = 12
    box = (max(0, min(b[0] for b in boxes) - pad), max(0, min(b[1] for b in boxes) - pad),
           min(SIZE[0], max(b[2] for b in boxes) + pad), min(SIZE[1], max(b[3] for b in boxes) + pad))

    OUT.mkdir(exist_ok=True)
    for name, img in images.items():
        img = img.crop(box)
        img = img.resize((WEB_WIDTH, round(img.height * WEB_WIDTH / img.width)), Image.LANCZOS)
        img.save(OUT / f"{name}.webp", quality=90, method=6)
        print("wrote", OUT / f"{name}.webp", img.size)


if __name__ == "__main__":
    main()
