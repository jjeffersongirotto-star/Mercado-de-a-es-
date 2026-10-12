#!/usr/bin/env python3
"""Gera os ícones do app instalável em static/icons/ (fonte única do desenho do ícone).
Uso: python scripts/build_icons.py   (requer Pillow e a fonte Inter instalada; ajuste FONT_DIR se preciso)."""
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "static", "icons")
FONT_DIR = os.environ.get("FONT_DIR", "/usr/share/fonts/opentype/inter")
MARCA, SUB = "JG", "INVESTINDO"
# cores do site (design system do index.html): fundo, cartão, borda, verde; dourado e cinza-claro para a marca
BG, CARD, BORDA = (2, 6, 23), (15, 23, 42), (51, 65, 85)
VERDE, VERDE2, BARRA = (52, 211, 153), (16, 185, 129), (6, 78, 59)
OURO, CINZA = (251, 191, 36), (203, 213, 225)


def fonte(nome, px):
    return ImageFont.truetype(os.path.join(FONT_DIR, nome), int(px))


def icone(size, maskable=False):
    S = 4 * size  # desenha em 4x e reduz: bordas suaves
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    if maskable:  # Android recorta o ícone em círculo/forma própria: conteúdo dentro da área segura
        d.rectangle([0, 0, S, S], fill=BG); pad = S * 0.20
    else:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S * 0.22, fill=BG); pad = S * 0.14
    w = S - 2 * pad
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=w * 0.12, fill=CARD, outline=BORDA, width=int(S * 0.012))
    x0, y0, x1, y1 = pad + w * 0.14, pad + w * 0.14, S - pad - w * 0.14, S - pad - w * 0.16
    # barras de volume
    bw = (x1 - x0) / 9
    for i, h in enumerate([0.25, 0.4, 0.32, 0.55, 0.48, 0.7, 0.62, 0.85, 1.0]):
        bx = x0 + i * bw; top = y1 - (y1 - y0) * h * 0.45
        d.rounded_rectangle([bx + bw * 0.18, top, bx + bw * 0.82, y1], radius=bw * 0.15, fill=BARRA)
    # linha de alta
    pts = [(x0, y1 - (y1 - y0) * 0.30), (x0 + (x1 - x0) * 0.28, y1 - (y1 - y0) * 0.52), (x0 + (x1 - x0) * 0.48, y1 - (y1 - y0) * 0.42),
           (x0 + (x1 - x0) * 0.72, y1 - (y1 - y0) * 0.75), (x1, y0 + (y1 - y0) * 0.02)]
    d.line(pts, fill=VERDE, width=int(S * 0.045), joint="curve")
    r = S * 0.04; ex, ey = pts[-1]; d.ellipse([ex - r, ey - r, ex + r, ey + r], fill=VERDE2)
    # marca no canto superior esquerdo (espaço livre acima da linha)
    tx, ty = pad + w * 0.10, pad + w * 0.07
    fm = fonte("Inter-ExtraBold.otf", w * 0.21)
    d.text((tx, ty), MARCA, font=fm, fill=OURO)
    hm = d.textbbox((tx, ty), MARCA, font=fm)
    fs = fonte("Inter-SemiBold.otf", w * 0.054)
    sx, sy = tx + w * 0.006, hm[3] + w * 0.025
    for ch in SUB:  # letras espaçadas
        d.text((sx, sy), ch, font=fs, fill=CINZA); sx += d.textlength(ch, font=fs) + w * 0.007
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for nome, size, mask in (("icon-192.png", 192, False), ("icon-512.png", 512, False),
                             ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)):
        icone(size, mask).save(os.path.join(OUT, nome), optimize=True)
        print(nome)
