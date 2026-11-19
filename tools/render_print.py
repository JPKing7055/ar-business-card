"""把名片正反面算成 600 dpi 的印刷圖，排在 A4 上輸出實際尺寸的 PDF。

輸入（design/）：portrait_source.png、qr/*.svg、linkedin.png、jpk-lab.png
輸出（design/）：card_front_print.jpg、card_back_print.png、card_print_A4.pdf、mindar_target_front.png

名片：54×90 mm 直式，四邊各 3 mm 出血（整張 60×96 mm）。
字型：Noto Sans CJK TC（中文）、Inter（英文）。路徑在下方 FONT_DIR / LATIN_DIR，
Windows 上請改成你安裝字型的位置。
用法：python tools/render_print.py
需要：pip install pillow numpy reportlab opencv-python
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
import cv2
import numpy as np

HERE = Path(__file__).resolve().parent.parent / "design"
FONT_DIR = "/usr/share/fonts/opentype/noto"     # NotoSansCJK-*.ttc
LATIN_DIR = "/usr/share/fonts/opentype/inter"   # Inter-*.otf
DPI = 600
CARD_W_MM, CARD_H_MM = 60, 96          # with 3 mm bleed on every side
BLEED_MM = 3
W = round(CARD_W_MM / 25.4 * DPI)
H = round(CARD_H_MM / 25.4 * DPI)
S = W / 227                            # design px -> render px


def cjk(weight, size):
    path = f"{FONT_DIR}/NotoSansCJK-{weight}.ttc"
    for i in range(10):
        f = ImageFont.truetype(path, size, index=i)
        if "TC" in f.getname()[0]:
            return f
    raise RuntimeError("no TC face")


def latin(weight, size):
    return ImageFont.truetype(f"{LATIN_DIR}/Inter-{weight}.otf", size)


def qr_image(svg_name, px):
    """Rasterise our QR svg (simple path of 1x1 squares) crisply."""
    import re
    txt = (HERE / "qr" / svg_name).read_text()
    n = int(re.search(r'viewBox="0 0 (\d+)', txt).group(1))
    grid = np.full((n, n), 255, np.uint8)
    for x, y in re.findall(r"M(\d+) (\d+)h1v1h-1z", txt):
        grid[int(y), int(x)] = 0
    img = Image.fromarray(grid).resize((px, px), Image.NEAREST).convert("RGB")
    dark = np.array(img)
    dark[(dark == 0).all(2)] = (15, 42, 51)
    return Image.fromarray(dark)


def qr_image_from_url(url, px, level="Q"):
    """直接從網址產生 QR Code 圖（每張名片不同的碼用）。"""
    from reportlab.graphics.barcode.qrencoder import QRCode, QRErrorCorrectLevel
    qr = QRCode(None, getattr(QRErrorCorrectLevel, level))
    qr.addData(url)
    qr.make()
    n = qr.getModuleCount()
    quiet = 2
    grid = np.full((n + 2 * quiet, n + 2 * quiet), 255, np.uint8)
    for r in range(n):
        for c in range(n):
            if qr.isDark(r, c):
                grid[r + quiet, c + quiet] = 0
    img = Image.fromarray(grid).resize((px, px), Image.NEAREST).convert("RGB")
    a = np.array(img)
    a[(a == 0).all(2)] = (15, 42, 51)
    return Image.fromarray(a)


def p(v):
    return round(v * S)


def front(qr_url=None, blank_qr=False):
    """qr_url：這張名片專屬的網址；blank_qr=True：QR 位置留白（編譯 AR 辨識檔用）。"""
    card = Image.new("RGB", (W, H), "#e9dcc4")
    src = Image.open(HERE / "portrait_source.png").convert("RGB")
    scale = max(W / src.width, H / src.height)
    rs = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left = (rs.width - W) // 2
    top = (rs.height - H) // 2
    card.paste(rs.crop((left, top, left + W, top + H)), (0, 0))

    d = ImageDraw.Draw(card)
    qr = p(72)
    pad = p(5)
    label_font = cjk("Bold", p(9))
    label = "掃描，跟我聊聊"
    lb = d.textbbox((0, 0), label, font=label_font)
    tile_w = qr + pad * 2
    tile_h = pad + qr + p(4) + (lb[3] - lb[1]) + p(5)
    x1, y1 = W - p(22), H - p(22)
    x0, y0 = x1 - tile_w, y1 - tile_h
    d.rounded_rectangle((x0, y0, x1, y1), radius=p(6), fill="white")
    if blank_qr:
        pass                                   # 留白：辨識檔不記這一塊
    elif qr_url:
        card.paste(qr_image_from_url(qr_url, qr), (x0 + pad, y0 + pad))
    else:
        card.paste(qr_image("qr-ar.svg", qr), (x0 + pad, y0 + pad))
    d.text((x0 + tile_w / 2, y0 + pad + qr + p(4)), label, font=label_font, fill="#10262d", anchor="mt")
    return card


# 背面配色：一般版（森林綠）與親友版（赤陶紅，加「親友專屬 · FAMILY」標籤）
VARIANTS = {
    "public": {"ground": "#1e3a2b", "accent": "#e7b75f", "badge": False},
    "family": {"ground": "#6e3322", "accent": "#f2c46d", "badge": True},
}


def back(variant="public"):
    v = VARIANTS[variant]
    ground, text, sub, accent = v["ground"], "#f3e7d3", "#d9cbb3", v["accent"]
    card = Image.new("RGB", (W, H), ground)
    d = ImageDraw.Draw(card)
    x = p(24)
    y = p(26)
    if v["badge"]:
        bf = cjk("Bold", p(9))
        label = "親友專屬 · FAMILY"
        bb = d.textbbox((0, 0), label, font=bf)
        bw, bh = bb[2] - bb[0] + p(14), bb[3] - bb[1] + p(6)
        d.rounded_rectangle((x, y, x + bw, y + bh), radius=bh // 2, outline=accent, width=max(1, p(1)))
        d.text((x + bw / 2, y + bh / 2), label, font=bf, fill=accent, anchor="mm")
        y += bh + p(10)
    name_f = cjk("Bold", p(21))
    d.text((x, y), "司順瑋", font=name_f, fill=text, anchor="la")
    nb = d.textbbox((x, y), "司順瑋", font=name_f, anchor="la")
    d.text((nb[2] + p(7), nb[3]), "Bernie", font=latin("SemiBold", p(14)), fill=accent, anchor="ls")
    y = nb[3] + p(6)
    d.text((x, y), "互動體驗 × AI 應用開發", font=cjk("Medium", p(10)), fill=sub, anchor="la")
    y += p(10 * 1.3) + p(14)
    d.rectangle((x, y, x + p(28), y + p(2)), fill=accent)
    y += p(2) + p(14)

    url_f = latin("Medium", p(9.5))
    rows = [
        ("qr-linkedin.svg", "linkedin.png", ["linkedin.com/in/", "jpking7055"], False),
        ("qr-site.svg", "jpk-lab.png", ["jpking7055.github.io/", "mySite"], True),
    ]
    for qr_svg, icon, lines, chip in rows:
        q = p(62)
        card.paste(qr_image(qr_svg, q), (x, y))
        tx = x + q + p(10)
        ic = Image.open(HERE / icon).convert("RGBA")
        if chip:
            iw, ih = p(42), p(14)
            ic = ic.resize((iw, ih), Image.LANCZOS)
            chip_box = (tx, 0, tx + iw + p(8), ih + p(4))
            block_h = chip_box[3] + p(5) + p(9.5 * 1.3) * 2
            top = y + (q - block_h) // 2
            d.rounded_rectangle((tx, top, tx + iw + p(8), top + ih + p(4)), radius=p(3), fill="white")
            card.paste(ic, (tx + p(4), top + p(2)), ic)
            ty = top + ih + p(4) + p(5)
        else:
            iw, ih = p(17), p(16)
            ic = ic.resize((iw, ih), Image.LANCZOS)
            block_h = ih + p(5) + p(9.5 * 1.3) * 2
            top = y + (q - block_h) // 2
            card.paste(ic, (tx, top), ic)
            ty = top + ih + p(5)
        for line in lines:
            d.text((tx, ty), line, font=url_f, fill=text, anchor="la")
            ty += p(9.5 * 1.3)
        y += q + p(12)

    tag_f = cjk("Medium", p(10))
    lh = p(10 * 1.55) + p(2)
    yb = H - p(24) - lh * 2
    d.text((x, yb), "用遊戲設計的思維，", font=tag_f, fill=text, anchor="la")
    d.text((x + p(20), yb + lh), "打造會回應你的 AI 互動體驗", font=tag_f, fill=text, anchor="la")
    return card


def crop_marks(c, x, y, w, h):
    """Trim marks at the 54x90 mm trim box, outside the bleed area."""
    c.setLineWidth(0.25)
    c.setStrokeColorRGB(0, 0, 0)
    b = BLEED_MM * mm
    tx0, ty0, tx1, ty1 = x + b, y + b, x + w - b, y + h - b
    L, gap = 5 * mm, 1 * mm
    for X in (tx0, tx1):
        c.line(X, y - gap, X, y - gap - L)
        c.line(X, y + h + gap, X, y + h + gap + L)
    for Y in (ty0, ty1):
        c.line(x - gap, Y, x - gap - L, Y)
        c.line(x + w + gap, Y, x + w + gap + L, Y)


def main():
    f, b = front(), back("public")
    back("family").save(HERE / "card_back_family_print.png", dpi=(DPI, DPI))
    f.save(HERE / "card_front_print.jpg", quality=94, dpi=(DPI, DPI))
    b.save(HERE / "card_back_print.png", dpi=(DPI, DPI))
    # MindAR 辨識圖：裁掉出血 = 裁切後名片看到的範圍
    bl = round(BLEED_MM / 25.4 * DPI)
    # QR 位置留白：一般版、親友版（每張不同 QR）都能用同一個辨識檔
    front(blank_qr=True).crop((bl, bl, W - bl, H - bl)).resize((600, 1000), Image.LANCZOS).save(
        HERE / "mindar_target_front.png", optimize=True)
    # QR self-check on the rendered card
    det = cv2.QRCodeDetector()
    for name in ("card_front_print.jpg", "card_back_print.png"):
        img = cv2.imread(str(HERE / name))
        ok, decoded, _, _ = det.detectAndDecodeMulti(img)
        print(name, list(decoded) if ok else "no QR found")

    out = HERE / "card_print_A4.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)
    pw, ph = A4
    w, h = CARD_W_MM * mm, CARD_H_MM * mm
    c.setFont("Helvetica", 8)
    c.drawString(15 * mm, ph - 12 * mm, "Business card test print - A4, print at 100% / no scaling. Trim at the marks: 54 x 90 mm.")
    # scale check bar: exactly 50 mm
    c.setLineWidth(0.8)
    c.line(15 * mm, ph - 18 * mm, 65 * mm, ph - 18 * mm)
    for xx in (15, 65):
        c.line(xx * mm, ph - 16.5 * mm, xx * mm, ph - 19.5 * mm)
    c.drawString(68 * mm, ph - 19 * mm, "<- this line should measure 5.0 cm")
    top = ph - 30 * mm - h
    xs = [(pw - 2 * w - 20 * mm) / 2, (pw - 2 * w - 20 * mm) / 2 + w + 20 * mm]
    # row 1: two fronts; row 2: two backs
    for i, xx in enumerate(xs):
        c.drawImage(str(HERE / "card_front_print.jpg"), xx, top, w, h)
        crop_marks(c, xx, top, w, h)
        c.drawImage(str(HERE / "card_back_print.png"), xx, top - h - 22 * mm, w, h)
        crop_marks(c, xx, top - h - 22 * mm, w, h)
    c.save()
    print("wrote", out)


if __name__ == "__main__":
    main()
