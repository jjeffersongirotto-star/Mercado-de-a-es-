"""Coleta de notícias (scripts/fetch_noticias.py): empresas citadas e RSS. Uso: python tests/test_noticias.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import fetch_noticias as F

ROWS = [{"ticker": "PETR4", "k1": 1}, {"ticker": "PETR3"}, {"ticker": "VALE3", "k1": 1}, {"ticker": "ITUB4", "k1": 1}, {"ticker": "WEGE3", "k1": 1}]
POP = {"PETR": "Petrobras", "VALE": "Vale", "ITUB": {"n": "Itaú", "aliases": ["itau unibanco"]}, "WEGE": "WEG"}


def test_empresas_citadas():
    tk, nomes = F.empresas(ROWS, POP)
    m = lambda s: F.marcar(s, tk, nomes)
    assert m("Petrobras anuncia recompra") == ["PETR4"]  # um ticker por empresa (o do universo do site)
    assert m("Ação da Vale cai") == [] and m("VALE3 lidera alta") == ["VALE3"]  # nome que é palavra comum: só com o código
    assert m("Itaú tem lucro recorde") == ["ITUB4"] and m("o itaú caiu") == []  # nome curto: grafia exata
    assert m("WEG e Petrobras sobem") == ["PETR4", "WEGE3"] and m("PETR3 sobe") == ["PETR3"]


def test_rss():
    x = ('<rss><channel><item><title><![CDATA[Ibovespa sobe]]></title><link>https://a/1</link><pubDate>Mon, 13 Oct 2026 10:00:00 -0300</pubDate>'
         '<description><![CDATA[<p>Bolsa &amp; dólar</p>]]></description><media:content url="https://img/1.jpg"/></item></channel></rss>')
    (t, u, dt, d, im), = F.itens_rss(x)
    assert (t, u, d, im) == ("Ibovespa sobe", "https://a/1", "Bolsa & dólar", "https://img/1.jpg") and dt.timestamp() == 1791896400
    assert F.chave("Ibovespa sobe 2%!") == F.chave("IBOVESPA SOBE 2%")


if __name__ == "__main__":
    fs = [f for k, f in dict(globals()).items() if k.startswith("test_")]
    for f in fs: f()
    print(f"{len(fs)} testes ok")
