#!/usr/bin/env python3
"""Gera os ícones do app instalável em static/icons/ e a marca do topo do site em static/brand/ a partir da arte "JG Investing"
(fonte única do desenho): scripts/icon-source.jpg (botão quadrado: ícones normais e iPhone), scripts/icon-source-round.jpg
(botão redondo: Android) e scripts/brand-source.jpg (faixa horizontal: topo do site). Uso: python scripts/build_icons.py   (requer Pillow).
Para trocar o ícone: substitua scripts/icon-source.jpg (botão quadrado sobre fundo escuro) e ajuste BOTAO se o recorte mudar."""
import os
from PIL import Image, ImageDraw, ImageFilter

AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "icon-source.jpg")
FONTE_REDONDA = os.path.join(AQUI, "icon-source-round.jpg")
CIRCULO = (139, 132, 1274, 1269)  # caixa do botão redondo dentro da imagem redonda
OUT = os.path.join(AQUI, "..", "static", "icons")
BOTAO = (206, 102, 1305, 1201)   # caixa do botão dentro da imagem (x0, y0, x1, y1)
RAIO = 0.14                       # raio dos cantos do botão (fração do lado)
MOLDURA = 35                      # espessura da moldura clara do botão (px na arte), removida quando o celular recorta o ícone
FONTE_MARCA = os.path.join(AQUI, "brand-source.jpg")
FAIXA = (144, 100, 1980, 786)     # caixa da faixa horizontal dentro da imagem da marca
MARCA = os.path.join(AQUI, "..", "static", "brand", "jg-investing.png")
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


def redondo(size, k=0.8):
    """Android (maskable): botão redondo inteiro dentro da área segura (k do lado), sobre o fundo escuro do botão.
    Em celulares de ícone redondo ele aparece como está; nos de outra forma, fica um círculo sobre o fundo escuro."""
    b = Image.open(FONTE_REDONDA).convert("RGB").crop(CIRCULO); L = b.size[0]
    C = size * 4; im = Image.new("RGB", (C, C), FUNDO)
    n = int(C * k); arte = b.resize((n, n), Image.LANCZOS)
    m = Image.new("L", (n, n), 0); ImageDraw.Draw(m).ellipse([0, 0, n - 1, n - 1], fill=255)
    im.paste(arte, ((C - n) // 2, (C - n) // 2), m.filter(ImageFilter.GaussianBlur(n * 0.004)))
    return im.resize((size, size), Image.LANCZOS)


def marca(altura=120):
    """Faixa "JG Investing" do topo do site, com os cantos arredondados transparentes (altura em px; exibida a 1/3)."""
    b = Image.open(FONTE_MARCA).convert("RGB").crop(FAIXA); W, H = b.size
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, W - 1, H - 1], radius=H * 0.2, fill=255)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.paste(b, (0, 0), m)
    return im.resize((round(W * altura / H), altura), Image.LANCZOS)


def icone(size, maskable=False, k=0.8):
    if maskable:
        return cheio(size, k)
    b = botao(); L = b.size[0]
    m = Image.new("L", (L, L)); ImageDraw.Draw(m).rounded_rectangle([0, 0, L - 1, L - 1], radius=L * RAIO, fill=255)
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0)); im.paste(b, (0, 0), m)
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # Apple: iOS arredonda os cantos (cabe 92% do botão quadrado); Android (maskable): versão redonda em 90% (o texto fica dentro da área segura de 80%)
    for nome, size, mask, k in (("icon-192.png", 192, False, 0), ("icon-512.png", 512, False, 0),
                                ("apple-touch-icon.png", 180, True, 0.92)):
        icone(size, mask, k).save(os.path.join(OUT, nome), optimize=True); print(nome)
    redondo(512, 0.9).save(os.path.join(OUT, "maskable-512.png"), optimize=True); print("maskable-512.png")
    os.makedirs(os.path.dirname(MARCA), exist_ok=True); marca().save(MARCA, optimize=True); print(os.path.basename(MARCA))
