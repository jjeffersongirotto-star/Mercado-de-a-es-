#!/usr/bin/env python3
"""Baixa a tabela de indicadores de TODAS as ações do Fundamentus (1 requisição) e salva em CSV.
Uso: python indicadores_fundamentus.py [--so-liquidas]"""
import io, sys, time, argparse
import requests, pandas as pd

URL = "https://www.fundamentus.com.br/resultado.php"  # http:// deu timeout nos testes; usar https
OUT = "/workspace/b3-api/indicadores_b3.csv"
HDRS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

def baixar(tent=5):
    espera = 3
    for i in range(1, tent + 1):
        try:
            r = requests.get(URL, headers=HDRS, timeout=(10, 60))
            if r.status_code == 200 and "Papel" in r.text:
                return r.content.decode("latin-1")
            print(f"HTTP {r.status_code}, tentativa {i}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"{type(e).__name__}, tentativa {i}", file=sys.stderr)
        time.sleep(espera); espera = min(espera * 2, 60)
    raise RuntimeError("Fundamentus indisponível")

def pct(s):
    return pd.to_numeric(s.astype(str).str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
                         .str.rstrip("%"), errors="coerce")

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--so-liquidas", action="store_true",
                                                    help="só papéis com Liq.2meses > 0")
    a = ap.parse_args()
    df = pd.read_html(io.StringIO(baixar()), decimal=",", thousands=".")[0]
    for c in df.columns:
        if c == "Papel" or pd.api.types.is_numeric_dtype(df[c]):
            continue
        if df[c].astype(str).str.contains("%").any():
            df[c] = pct(df[c])  # colunas em % viram número (ex.: 7,12% -> 7.12)
        else:
            df[c] = pd.to_numeric(df[c], errors="coerce")  # read_html já converteu decimal
    # derivados: LPA = preço / (P/L), VPA = preço / (P/VP) (só quando o múltiplo != 0)
    df["LPA"] = (df["Cotação"] / df["P/L"]).where(df["P/L"] != 0).round(4)
    df["VPA"] = (df["Cotação"] / df["P/VP"]).where(df["P/VP"] != 0).round(4)
    if a.so_liquidas:
        df = df[df["Liq.2meses"] > 0]
    df.to_csv(OUT, index=False)
    print(f"OK: {len(df)} papéis, {len(df.columns)} colunas -> {OUT}")

if __name__ == "__main__":
    main()
