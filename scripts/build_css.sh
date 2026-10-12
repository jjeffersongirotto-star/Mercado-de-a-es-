#!/bin/bash
# Gera static/tw.css (Tailwind v3, as mesmas classes do CDN) a partir das classes usadas em index.html e *.js.
# Roda no build do Render. Se falhar, o site continua usando o Tailwind do CDN (server.py só troca quando o arquivo existe).
cd "$(dirname "$0")/.." || exit 0
V=3.4.17
BIN=".tw/tailwindcss-$V"
if [ ! -x "$BIN" ]; then
  mkdir -p .tw
  curl -sSfL --retry 3 --max-time 120 -o "$BIN" \
    "https://github.com/tailwindlabs/tailwindcss/releases/download/v$V/tailwindcss-linux-x64" && chmod +x "$BIN" \
    || { echo "AVISO: não baixou o Tailwind; o site usa o CDN"; rm -f "$BIN" static/tw.css; exit 0; }
fi
"$BIN" -c tailwind.config.js -i static/tw-in.css -o static/tw.css --minify \
  || { echo "AVISO: falhou ao gerar o CSS; o site usa o CDN"; rm -f static/tw.css; exit 0; }
echo "static/tw.css: $(wc -c < static/tw.css) bytes"
