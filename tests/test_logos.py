"""Testes dos logos das empresas (scripts/build_logos.py) e do nome curto do widget (snapshots.nome_curto). Rodar: python tests/test_logos.py"""
import io, json, os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
from PIL import Image
import snapshots, build_logos as bl

def test_nome_curto():
    c = snapshots.nome_curto
    assert c("ITAU UNIBANCO HOLDING S.A.") == "Itau Unibanco"
    assert c("BB SEGURIDADE PARTICIPAÇÕES S.A.") == "BB Seguridade"
    assert c("B3 S.A. - BRASIL, BOLSA, BALCAO") == "B3"
    assert c("SAO MARTINHO S.A.") == "São Martinho"
    assert c("SAO CARLOS EMPREEND E PARTICIPACOES S.A.") == "São Carlos Empreend"
    assert c("TRANSMISSORA ALIANÇA DE ENERGIA ELÉTRICA S.A.") == "Transmissora Aliança de Energia Elétrica"
    assert c("WEG S.A.") == "WEG" and c("Itaúsa S.A.") == "Itaúsa" and c(None) == ""

def test_fit_keeps_shape():
    im = Image.new("RGBA", (200, 50), (255, 0, 0, 255))           # retângulo deitado
    big = Image.new("RGBA", (300, 300), (0, 0, 0, 0)); big.alpha_composite(im, (50, 125))
    f = bl.fit(big)
    assert f.size == (64, 64)
    a = f.getchannel("A")
    assert a.getpixel((32, 32)) == 255 and a.getpixel((32, 2)) == 0  # sem distorcer: faixa no meio, transparente em cima
    bb = a.getbbox(); assert bb[2] - bb[0] == 64 and 14 <= bb[3] - bb[1] <= 18  # margem transparente cortada

def test_tile_and_backing():
    sq = Image.new("RGBA", (56, 56), (1, 32, 123, 255))
    t = bl.tile(sq)
    assert t.getchannel("A").getpixel((0, 0)) == 0 and t.getchannel("A").getpixel((32, 32)) == 255  # cantos arredondados
    dark = Image.new("RGBA", (40, 40), (0, 0, 0, 255))
    b = bl.backing(dark)
    assert b.getpixel((3, 32))[:3] == bl.LIGHT[:3]                  # borda clara
    assert b.getpixel((32, 32))[:3] == (0, 0, 0) and b.getchannel("A").getpixel((0, 0)) == 0

def test_helpers_and_override():
    assert bl.dom("www.ri.caixaseguridade.com.br") == "caixaseguridade.com.br"
    assert bl.dom("www.multilaser.com.br / www.ri.multilaser.com.br") == "multilaser.com.br"
    assert bl.dom("http://ri.weg.net") == "weg.net" and bl.dom("") is None
    assert bl.is_placeholder("https://icons.brapi.dev/icons/BRAPI.svg") and not bl.is_placeholder("https://icons.brapi.dev/icons/MGLU3.svg")
    ovr = json.load(open(os.path.join(bl.OVR_DIR, "override.json"), encoding="utf-8"))
    assert bl.ovr_files(ovr) == ["PRIO"] and os.path.exists(os.path.join(bl.OVR_DIR, ovr["PRIO"]["file"]))
    assert all(len(h) == 12 for h in ovr["_generic"])
    im = bl.open_img(open(os.path.join(bl.OVR_DIR, "PRIO.png"), "rb").read())
    assert im is not None and bl.big_enough(im)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56"><path fill="#01207B" d="M0 0h56v56H0z"/></svg>'
    try:
        import resvg_py  # noqa: F401
        s = bl.open_img(svg); assert s is not None and s.getpixel((10, 10))[:3] == (1, 32, 123)
    except ImportError:
        pass

def test_too_dark_foreign():
    from PIL import Image
    import build_logos as bl
    dark = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(16, 48):
        for y in range(16, 48): dark.putpixel((x, y), (10, 10, 10, 255))
    light = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    for x in range(16, 48):
        for y in range(16, 48): light.putpixel((x, y), (240, 200, 40, 255))
    square = Image.new("RGBA", (64, 64), (10, 10, 10, 255))  # quadrado preto com letra branca: aparece
    for x in range(20, 44):
        for y in range(20, 44): square.putpixel((x, y), (255, 255, 255, 255))
    assert bl.too_dark(dark) and not bl.too_dark(light) and not bl.too_dark(square)

if __name__ == "__main__":
    n = 0
    for k, f in list(globals().items()):
        if k.startswith("test_"): f(); n += 1
    print(f"{n} testes ok")
