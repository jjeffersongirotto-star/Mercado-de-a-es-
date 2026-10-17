#!/usr/bin/env python3
"""Gera os ícones do app instalável em static/icons/ e a marca do topo do site em static/brand/ a partir da arte "JG Investing"
(fonte única do desenho): scripts/icon-source.jpg (botão quadrado: ícones normais e iPhone), scripts/icon-source-round.jpg
(botão redondo: Android), scripts/brand-source.jpg (faixa horizontal: topo do site no celular) e
scripts/brand-source-wide.jpg (faixa comprida: topo do site no computador); da faixa do celular sai a marca do widget do app
(static/brand/jg-investing-widget.png → android ic_brand). Uso: python scripts/build_icons.py   (requer Pillow).
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
BRAND = os.path.join(AQUI, "..", "static", "brand")
RAIO_FAIXA = 0.19                 # raio dos cantos da faixa (fração da altura)
# faixas da marca: (arte, caixa da faixa dentro da arte, arquivo gerado, altura gerada em px)
MARCAS = ((os.path.join(AQUI, "brand-source.jpg"), (56, 54, 3404, 510), "jg-investing.webp", 126),
          (os.path.join(AQUI, "brand-source-wide.jpg"), (7, 390, 2118, 505), "jg-investing-wide.webp", 115))
# marca do widget do app (android/: ic_brand): faixa do celular com o gráfico encolhido, para caber no topo do widget
WIDGET = ("jg-investing.webp", 215, 190, "jg-investing-widget.png")  # (faixa de origem, px do nome "JG Investing", px do gráfico, arquivo)
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


def marca(fonte, caixa, altura):
    """Faixa "JG Investing" do topo do site, com os cantos arredondados transparentes."""
    b = Image.open(fonte).convert("RGB").crop(caixa); W, H = b.size
    m = Image.new("L", (W, H), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, W - 1, H - 1], radius=H * RAIO_FAIXA, fill=255)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); im.paste(b, (0, 0), m)
    return im.resize((round(W * altura / H), altura), Image.LANCZOS)


def icone(size, maskable=False, k=0.8):
    if maskable:
        return cheio(size, k)
    b = botao(); L = b.size[0]
    m = Image.new("L", (L, L)); ImageDraw.Draw(m).rounded_rectangle([0, 0, L - 1, L - 1], radius=L * RAIO, fill=255)
    im = Image.new("RGBA", (L, L), (0, 0, 0, 0)); im.paste(b, (0, 0), m)
    return im.resize((size, size), Image.LANCZOS)


def marca_widget(faixa):
    """Marca comprida do widget: o nome "JG Investing" como no site e o gráfico da faixa encolhido na horizontal (≈3,2 : 1)."""
    _, nome, graf, _ = WIDGET; W, H = faixa.size
    o = Image.new("RGBA", (nome + graf, H), (0, 0, 0, 0))
    o.paste(faixa.crop((0, 0, nome, H)), (0, 0)); o.paste(faixa.crop((nome, 0, W, H)).resize((graf, H), Image.LANCZOS), (nome, 0))
    return o


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    # Apple: iOS arredonda os cantos (cabe 92% do botão quadrado); Android (maskable): versão redonda em 90% (o texto fica dentro da área segura de 80%)
    for nome, size, mask, k in (("icon-192.png", 192, False, 0), ("icon-512.png", 512, False, 0),
                                ("apple-touch-icon.png", 180, True, 0.92)):
        icone(size, mask, k).save(os.path.join(OUT, nome), optimize=True); print(nome)
    redondo(512, 0.9).save(os.path.join(OUT, "maskable-512.png"), optimize=True); print("maskable-512.png")
    os.makedirs(BRAND, exist_ok=True)
    for fonte, caixa, nome, altura in MARCAS:
        m = marca(fonte, caixa, altura); m.save(os.path.join(BRAND, nome), quality=90, method=6); print(nome)
        if nome == WIDGET[0]: marca_widget(m).save(os.path.join(BRAND, WIDGET[3]), optimize=True); print(WIDGET[3])
