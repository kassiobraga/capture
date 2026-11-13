#!/bin/sh
# Remove o Capture instalado por install.sh. Nao apaga as capturas salvas nem
# arquivos que nao tenham sido criados pelo Capture.
set -eu

APP_ID=io.github.kassiobraga.Capture
MARCA_LANCADOR="# capture-launcher: $APP_ID"
MARCA_DESKTOP="# capture-install-marker: $APP_ID"

AQUI=$(cd "$(dirname "$0")" && pwd)
DADOS=${XDG_DATA_HOME:-$HOME/.local/share}
LANCADOR=$HOME/.local/bin/capture
DESKTOP=$DADOS/applications/$APP_ID.desktop
ICONES=$DADOS/icons/hicolor

for c in "$HOME" "$DADOS"; do
    case $c in
        *[!A-Za-z0-9_./+@,:=%-]*)
            echo "Erro: o caminho '$c' tem espacos ou caracteres especiais, que o desinstalador nao trata." >&2
            exit 1 ;;
    esac
done

# O atalho sai mesmo se o lancador ja foi apagado a mao: so a entrada com o nome unico
# e o comando exato "<lancador> --novo" e removida; as outras nao sao tocadas.
. "$AQUI/scripts/cinnamon.sh"
if cin_disponivel; then
    cin_desvincula "$LANCADOR"
fi
if [ -e "$LANCADOR" ] && grep -qxF "$MARCA_LANCADOR" "$LANCADOR" 2>/dev/null; then
    rm -f "$LANCADOR"
elif [ -e "$LANCADOR" ]; then
    echo "aviso: $LANCADOR nao foi criado pelo Capture; mantido." >&2
fi
if [ -e "$DESKTOP" ] && grep -qxF "$MARCA_DESKTOP" "$DESKTOP" 2>/dev/null; then
    rm -f "$DESKTOP"
fi

rm -rf "${DADOS:?}/$APP_ID"
rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/${APP_ID:?}"
rm -f "$ICONES/scalable/apps/$APP_ID.svg"
for t in 48 64 128 256; do
    rm -f "$ICONES/${t}x${t}/apps/$APP_ID.png"
done

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DADOS/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t "$ICONES" || true

echo "Capture removido. As capturas salvas foram mantidas."
