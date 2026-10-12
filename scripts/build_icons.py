#!/usr/bin/env python3
"""Gera os ícones do app instalável em static/icons/ (fonte única do desenho do ícone).
Uso: python scripts/build_icons.py   (requer Pillow). Fonte: Montserrat Italic (scripts/fonts/, licença OFL).
Desenho: fundo escuro inteiro, "JG Investing" em branco com o pingo do "i" em laranja, linha fina de alta com área sombreada."""
import os
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "static", "icons")
FONTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "Montserrat-Italic.ttf")
MARCA, SUB = "JG", "Investing"
BG = (2, 6, 23)            # fundo do site (theme-color)
AREA = (22, 34, 52)        # área sob a linha
BRANCO = (248, 250, 252)
LINHA = (52, 211, 153)     # verde do site
PINGO = (249, 115, 22)     # laranja de destaque (pingo do "i")


def fonte(peso, px):
    f = ImageFont.truetype(FONTE, int(px))
    f.set_variation_by_axes([peso])  # fonte variável: peso 100–900
    return f


def arte(S, z=1.0):
    """Desenho S×S. z < 1 encolhe texto e gráfico para o centro (área segura do ícone maskable); o fundo e a área
    sombreada continuam indo até as bordas."""
    im = Image.new("RGBA", (S, S), BG); d = ImageDraw.Draw(im)
    o = S * (1 - z) / 2; X = lambda x: o + x * S * z  # coordenadas 0–1 dentro da área útil
    # linha de alta (fina, sem ponto final) com área sombreada até a base; sai pelas bordas
    pts = [(0.0, 0.88), (0.22, 0.73), (0.38, 0.80), (0.60, 0.60), (0.74, 0.67), (1.0, 0.42)]
    P = [(X(x), X(y)) for x, y in pts]
    ext = lambda a, b, x: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))  # prolonga o segmento a→b até x
    P = [ext(P[0], P[1], -0.02 * S)] + P + [ext(P[-2], P[-1], 1.02 * S)]  # linha e área até as bordas, na mesma inclinação
    d.polygon(P + [(1.02 * S, 1.02 * S), (-0.02 * S, 1.02 * S)], fill=AREA)
    d.line(P, fill=LINHA, width=max(2, int(S * z * 0.022)), joint="curve")
    # marca: JG + Investing, o "i" sem pingo (ı) e o pingo desenhado em laranja no lugar do original
    S0 = S; S = S * z
    tx, ty = X(0.11), X(0.10)
    fm = fonte(800, S * 0.25)
    d.text((tx, ty), MARCA, font=fm, fill=BRANCO)
    by = d.textbbox((tx, ty), MARCA, font=fm)[3] + S * 0.015
    fs = fonte(700, S * 0.135)
    k = SUB.index("i")  # primeira letra "i" minúscula
    sub = SUB[:k] + "ı" + SUB[k + 1:]
    d.text((tx, by), sub, font=fs, fill=BRANCO)
    xi = tx + d.textlength(SUB[:k], font=fs)
    com, sem = Image.new("L", (S0, S0)), Image.new("L", (S0, S0))
    ImageDraw.Draw(com).text((xi, by), "i", font=fs, fill=255)
    ImageDraw.Draw(sem).text((xi, by), "ı", font=fs, fill=255)
    bx0, by0, bx1, by1 = ImageChops.subtract(com, sem).getbbox()  # onde fica o pingo original
    cx, cy, r = (bx0 + bx1) / 2, (by0 + by1) / 2, max(bx1 - bx0, by1 - by0) * 0.62  # um pouco maior que o original
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINGO)
    return im


def icone(size, maskable=False):
    S = 4 * size  # desenha em 4x e reduz: bordas suaves
    if maskable:  # Android recorta em círculo/forma própria: conteúdo dentro da área segura (80%)
        im = arte(S, 0.8)
    else:
        im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        mask = Image.new("L", (S, S)); ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=S * 0.22, fill=255)
        im.paste(arte(S), (0, 0), mask)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for nome, size, mask in (("icon-192.png", 192, False), ("icon-512.png", 512, False),
                             ("maskable-512.png", 512, True), ("apple-touch-icon.png", 180, True)):
        icone(size, mask).save(os.path.join(OUT, nome), optimize=True)
        print(nome)
