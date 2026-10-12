#!/usr/bin/env python3
"""Gera os ícones do app instalável em static/icons/ a partir da arte "JG Investing" (scripts/icon-source.jpg,
fonte única do desenho). Uso: python scripts/build_icons.py   (requer Pillow).
Para trocar o ícone: substitua scripts/icon-source.jpg (botão quadrado sobre fundo escuro) e ajuste BOTAO se o recorte mudar."""
import os
from PIL import Image, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "icon-source.jpg")
OUT = os.path.join(AQUI, "..", "static", "icons")
BOTAO = (206, 102, 1305, 1201)   # caixa do botão dentro da imagem (x0, y0, x1, y1)
RAIO = 0.14                       # raio dos cantos do botão (fração do lado)
MOLDURA = 35                      # espessura da moldura clara do botão (px na arte), removida quando o celular recorta o ícone
FUNDO = (3, 12, 34)               # cor escura do interior do botão (fundo dos ícones que o celular recorta)


def botao():
    return Image.open(FONTE).convert("RGB").crop(BOTAO)


def cheio(size, k):
    """Interior do botão (sem a moldura) para o celular aplicar a própria forma: o desenho fica em k do lado
    (área segura), com cantos suavizados, sobre a cor escura do próprio botão."""
    b = botao(); L = b.size[0]; inner = b.crop((MOLDURA, MOLDURA, L - MOLDURA, L - MOLDURA))
    C = size * 4; fundo = Image.new("RGB", (C, C), FUNDO)
    n = int(C * k); arte = inner.resize((n, n), Image.LANCZOS); o = (C - n) // 2
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).rounded_rectangle([n * 0.03, n * 0.03, n * 0.97, n * 0.97], radius=n * RAIO, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(n * 0.025))  # passagem suave do desenho para o fundo
    fundo.paste(arte, (o, o), m)
    return fundo.resize((size, size), Image.LANCZOS)


def icone(size, maskable=False, k=0.8):
    if maskable:
        return cheio(size, k)
    b = botao(); L = b.size[0]
    m = Image.new("L", (L, L)); ImageDraw.Draw(m).rounded_rectangle([0, 0, L - 1, L - 1], radius=L * RAIO, fill=255)
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0)); im.paste(b, (0, 0), m)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # maskable: Android recorta em círculo (área segura = 80%); Apple: iOS arredonda os cantos (cabe 92%)
    for nome, size, mask, k in (("icon-192.png", 192, False, 0), ("icon-512.png", 512, False, 0),
                                ("maskable-512.png", 512, True, 0.8), ("apple-touch-icon.png", 180, True, 0.92)):
        icone(size, mask, k).save(os.path.join(OUT, nome), optimize=True)
        print(nome)
