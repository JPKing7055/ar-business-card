"""每張名片正面放不同的 QR Code（可變資料印刷）。

產生：
    （AR 辨識圖由 render_print.py 產生：design/mindar_target_front.png，QR 位置留白，
     一般版與每張不同 QR 的親友版共用同一個 targets.mind。）
    --mode test：design/variable/test_A4.pdf
        A4 上排 4 張不同 QR 的正面（實際尺寸、含裁切線），超商印來測 AR 辨識。
    --mode print：design/variable/cards_front.pdf
        給印刷店：每頁一張名片正面（60×96 mm，含 3 mm 出血），每頁 QR 不同。
        親友卡背面每張都一樣，用 design/card_back_family_print.png（赤陶紅、親友專屬標籤）。

用法：
    python tools/make_variable_cards.py --mode test --count 4
    python tools/make_variable_cards.py --mode print --codes codes.txt
        codes.txt：一行一個碼（由後端產生並登記，保證不重複）

需要：與 render_print.py 相同（pillow numpy reportlab opencv-python）
"""
import argparse
import secrets
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_print as rp  # noqa: E402

OUT = rp.HERE / "variable"
BASE_URL = "https://jpking7055.github.io/mySite/card.html?c="
SAFE = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # 去掉 0/O、1/I/L 這類容易看錯的字


def random_code(n=6):
    return "".join(secrets.choice(SAFE) for _ in range(n))


def check_qr(img, expected):
    ok, decoded, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(
        cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR))
    found = list(decoded) if ok else []
    if expected not in found:
        raise RuntimeError(f"QR 解碼失敗：預期 {expected}，讀到 {found}")


def render_cards(codes):
    cards = []
    for code in codes:
        url = BASE_URL + code
        img = rp.front(qr_url=url)
        check_qr(img, url)
        cards.append((code, img))
        print("ok", code, url)
    return cards


def test_pdf(cards):
    path = OUT / "test_A4.pdf"
    c = canvas.Canvas(str(path), pagesize=A4)
    pw, ph = A4
    w, h = rp.CARD_W_MM * mm, rp.CARD_H_MM * mm
    c.setFont("Helvetica", 8)
    c.drawString(15 * mm, ph - 12 * mm, "Variable-QR test print - A4, no scaling. Trim at the marks: 54 x 90 mm.")
    c.setLineWidth(0.8)
    c.line(15 * mm, ph - 18 * mm, 65 * mm, ph - 18 * mm)
    for xx in (15, 65):
        c.line(xx * mm, ph - 16.5 * mm, xx * mm, ph - 19.5 * mm)
    c.drawString(68 * mm, ph - 19 * mm, "<- this line should measure 5.0 cm")
    gap = 20 * mm
    x0 = (pw - 2 * w - gap) / 2
    positions = [(x0, ph - 30 * mm - h), (x0 + w + gap, ph - 30 * mm - h),
                 (x0, ph - 30 * mm - 2 * h - 22 * mm), (x0 + w + gap, ph - 30 * mm - 2 * h - 22 * mm)]
    for (code, img), (x, y) in zip(cards, positions):
        tmp = OUT / f"_tmp_{code}.jpg"
        img.save(tmp, quality=94)
        c.drawImage(str(tmp), x, y, w, h)
        rp.crop_marks(c, x, y, w, h)
        c.setFont("Helvetica", 7)
        c.drawString(x, y - 9 * mm, code)
        tmp.unlink()
    c.save()
    print("wrote", path)


def print_pdf(cards):
    path = OUT / "cards_front.pdf"
    w, h = rp.CARD_W_MM * mm, rp.CARD_H_MM * mm
    c = canvas.Canvas(str(path), pagesize=(w, h))
    for code, img in cards:
        tmp = OUT / f"_tmp_{code}.jpg"
        img.save(tmp, quality=94)
        c.drawImage(str(tmp), 0, 0, w, h)
        c.showPage()
        tmp.unlink()
    c.save()
    print("wrote", path, f"({len(cards)} pages)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["test", "print"], default="test")
    ap.add_argument("--count", type=int, default=4, help="test 模式：隨機產生幾組碼")
    ap.add_argument("--codes", help="print 模式：碼的清單檔，一行一個")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    if args.mode == "test":
        codes = [random_code() for _ in range(min(args.count, 4))]
        test_pdf(render_cards(codes))
    else:
        if not args.codes:
            sys.exit("print 模式需要 --codes 碼的清單檔")
        codes = [line.strip() for line in Path(args.codes).read_text().splitlines() if line.strip()]
        if len(set(codes)) != len(codes):
            sys.exit("碼的清單有重複，請檢查")
        print_pdf(render_cards(codes))


if __name__ == "__main__":
    main()
