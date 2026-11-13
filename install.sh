#!/bin/sh
# Instala o Capture so para o usuario atual (~/.local). Nao usa sudo e pode ser repetido.
set -eu

APP_ID=io.github.kassiobraga.Capture
MARCA_LANCADOR="# capture-launcher: $APP_ID"
MARCA_DESKTOP="# capture-install-marker: $APP_ID"

AQUI=$(cd "$(dirname "$0")" && pwd)
DADOS=${XDG_DATA_HOME:-$HOME/.local/share}
BIN_DIR=$HOME/.local/bin
DESTINO=$DADOS/$APP_ID
LANCADOR=$BIN_DIR/capture
DESKTOP=$DADOS/applications/$APP_ID.desktop
ICONES=$DADOS/icons/hicolor
VINCULAR=0

uso() {
    cat <<'TXT'
Uso: ./install.sh [--bind-print]

  --bind-print   no Cinnamon, vincula a tecla Print a "capture --novo"
                 (cria ou atualiza so a entrada do Capture)
  -h, --help     mostra esta ajuda
TXT
}

for a in "$@"; do
    case $a in
        --bind-print) VINCULAR=1 ;;
        -h | --help) uso; exit 0 ;;
        *) echo "opcao desconhecida: $a" >&2; uso >&2; exit 2 ;;
    esac
done

# Os caminhos vao para o lancador, o .desktop e o atalho; aceitamos so caracteres simples.
for c in "$HOME" "$DADOS" "$AQUI"; do
    case $c in
        *[!A-Za-z0-9_./+@,:=%-]*)
            echo "Erro: o caminho '$c' tem espacos ou caracteres especiais, que o instalador nao trata." >&2
            echo "Use um HOME/XDG_DATA_HOME e uma copia do projeto em caminhos sem eles." >&2
            exit 1 ;;
    esac
done

# ---- dependencias
faltam=
if ! command -v python3 >/dev/null 2>&1; then
    faltam="$faltam python3"
else
    set +e
    versao=$(python3 - 2>&1 <<'PY'
import sys
if sys.version_info < (3, 10):
    print("Python 3.10 ou mais novo e necessario (encontrado %d.%d)." % sys.version_info[:2])
    sys.exit(3)
try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Adw, Gtk, PangoCairo
    import cairo
    gi.require_foreign("cairo")
except Exception:
    sys.exit(2)
if Gtk.get_minor_version() < 12:
    print("GTK 4.12 ou mais novo e necessario (encontrado 4.%d)." % Gtk.get_minor_version())
    sys.exit(3)
if Adw.get_minor_version() < 4:
    print("libadwaita 1.4 ou mais nova e necessaria (encontrada 1.%d)." % Adw.get_minor_version())
    sys.exit(3)
PY
    )
    rc=$?
    set -e
    case $rc in
        0) ;;
        3) echo "Erro: $versao" >&2
           echo "Atualize o sistema (ou use uma distribuicao mais nova) e rode o instalador de novo." >&2
           exit 1 ;;
        *) faltam="$faltam python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-pango-1.0" ;;
    esac
fi
command -v maim >/dev/null 2>&1 || faltam="$faltam maim"
command -v xclip >/dev/null 2>&1 || faltam="$faltam xclip"
if [ -n "$faltam" ]; then
    echo "Faltam dependencias. No Debian/Ubuntu/Mint:" >&2
    echo "  sudo apt install$faltam" >&2
    exit 1
fi
if ! command -v xprop >/dev/null 2>&1 || ! command -v xwininfo >/dev/null 2>&1; then
    echo "aviso: sem xprop/xwininfo (pacote x11-utils) o modo 'janela' nao encontra janelas." >&2
fi
if [ "${XDG_SESSION_TYPE:-x11}" = wayland ]; then
    echo "aviso: sessao Wayland detectada. O Capture so funciona em X11 por enquanto." >&2
fi

# ---- nao sobrescreve arquivos que nao sao nossos
if [ -e "$LANCADOR" ] && ! grep -qxF "$MARCA_LANCADOR" "$LANCADOR" 2>/dev/null; then
    echo "Erro: $LANCADOR ja existe e nao foi criado pelo Capture; nada foi alterado." >&2
    echo "Mova ou apague esse arquivo e rode o instalador de novo." >&2
    exit 1
fi
if [ -e "$DESKTOP" ] && ! grep -qxF "$MARCA_DESKTOP" "$DESKTOP" 2>/dev/null; then
    echo "Erro: $DESKTOP ja existe e nao foi criado pelo Capture; nada foi alterado." >&2
    exit 1
fi

# ---- pacote e lancador
mkdir -p "$DADOS" "$BIN_DIR" "$DADOS/applications"
rm -rf "$DESTINO/capture"
mkdir -p "$DESTINO"
cp -R "$AQUI/capture" "$DESTINO/capture"
find "$DESTINO/capture" -name __pycache__ -type d -prune -exec rm -rf {} +

cat > "$LANCADOR" <<EOT
#!/bin/sh
$MARCA_LANCADOR
PYTHONPATH="$DESTINO\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m capture "\$@"
EOT
chmod 755 "$LANCADOR"

# ---- menu de aplicativos
sed "s|@BIN@|$LANCADOR|g" "$AQUI/data/capture.desktop" > "$DESKTOP"
chmod 644 "$DESKTOP"

# ---- icones
mkdir -p "$ICONES/scalable/apps"
cp "$AQUI/data/capture.svg" "$ICONES/scalable/apps/$APP_ID.svg"
if command -v rsvg-convert >/dev/null 2>&1; then
    for t in 48 64 128 256; do
        mkdir -p "$ICONES/${t}x${t}/apps"
        rsvg-convert -w "$t" -h "$t" "$AQUI/data/capture.svg" -o "$ICONES/${t}x${t}/apps/$APP_ID.png"
    done
else
    echo "aviso: sem rsvg-convert (pacote librsvg2-bin); so o icone SVG foi instalado." >&2
fi

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$DADOS/applications" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -f -t "$ICONES" || true

echo "Capture instalado em $DESTINO"
echo "Comando: $LANCADOR"

# ---- tecla Print (Cinnamon)
. "$AQUI/scripts/cinnamon.sh"
if cin_disponivel; then
    if [ "$VINCULAR" = 0 ] && [ -t 0 ] && [ -t 1 ]; then
        printf 'Vincular a tecla Print ao Capture? [s/N] '
        read -r r || r=
        case $r in s | S | y | Y) VINCULAR=1 ;; esac
    fi
    if [ "$VINCULAR" = 1 ]; then
        cin_vincula_print "$LANCADOR"
    else
        echo "Para usar a tecla Print no Cinnamon: ./install.sh --bind-print"
    fi
elif [ "$VINCULAR" = 1 ]; then
    echo "aviso: --bind-print so funciona no Cinnamon; configure a tecla no seu ambiente com o comando:" >&2
    echo "  $LANCADOR --novo" >&2
fi
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "aviso: $BIN_DIR nao esta no PATH." >&2 ;;
esac
