"""產生名片上的三個 QR Code（SVG）到 design/qr/。

用法：python tools/make_qr.py
需要：pip install reportlab
"""
from pathlib import Path

from reportlab.graphics.barcode.qrencoder import QRCode, QRErrorCorrectLevel

OUT = Path(__file__).resolve().parent.parent / "design" / "qr"

CODES = {
    # 正面：先到 mySite 的轉址頁，AR 網址換了只要改 card.html，名片不用重印
    "qr-ar.svg": ("https://jpking7055.github.io/mySite/card.html", QRErrorCorrectLevel.Q),
    "qr-linkedin.svg": ("https://www.linkedin.com/in/jpking7055/", QRErrorCorrectLevel.M),
    "qr-site.svg": ("https://jpking7055.github.io/mySite/index.html", QRErrorCorrectLevel.M),
}
COLOR = "#0f2a33"
QUIET = 2   # 外圍留白（格數）；名片上另有白底


def write_svg(data, level, path):
    qr = QRCode(None, level)
    qr.addData(data)
    qr.make()
    n = qr.getModuleCount()
    cells = "".join(
        f"M{c + QUIET} {r + QUIET}h1v1h-1z"
        for r in range(n) for c in range(n) if qr.isDark(r, c)
    )
    size = n + 2 * QUIET
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" shape-rendering="crispEdges">'
        f'<rect width="100%" height="100%" fill="#fff"/><path fill="{COLOR}" d="{cells}"/></svg>'
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, (url, level) in CODES.items():
        write_svg(url, level, OUT / name)
        print("wrote", OUT / name, "->", url)


if __name__ == "__main__":
    main()
