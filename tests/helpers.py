"""Utilidades de teste: superficies cairo e leitura de pixels, sem display."""
import os
import sys

import cairo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def superficie(w, h, cor=None):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    if cor:
        cr = cairo.Context(s)
        cr.set_source_rgba(*cor)
        cr.paint()
    return s


def pixel(s, x, y):
    """(r, g, b, a) de 0 a 255, ja desfeito o alfa pre-multiplicado."""
    s.flush()
    d = s.get_data()
    o = y * s.get_stride() + x * 4
    b, g, r, a = d[o], d[o + 1], d[o + 2], d[o + 3]  # little endian: BGRA
    if a:
        r, g, b = (min(255, round(c * 255 / a)) for c in (r, g, b))
    return r, g, b, a


def transparente(s, x, y):
    return pixel(s, x, y)[3] == 0


def desenha(it, w=100, h=100, fundo=None):
    from capture.editor import desenha_item
    s = superficie(w, h, fundo)
    desenha_item(cairo.Context(s), it)
    return s


def perto(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def novo_doc(img):
    """Modelo do editor sem GTK, com contagem de avisos em .avisos."""
    from capture.editor import Modelo

    class Doc(Modelo):
        def __init__(self, img):
            self.avisos = 0
            self._inicia_modelo(self._aviso)
            self.definir_imagem(img)

        def _aviso(self):
            self.avisos += 1

    return Doc(img)


GSETTINGS_FALSO = r"""#!/bin/sh
# gsettings falso: guarda cada chave em um arquivo de $STUB_DIR
d=$STUB_DIR
cmd=$1; shift
arq() { printf '%s/%s' "$d" "$(printf '%s' "$1|$2" | tr '/:|' '___')"; }
case $cmd in
    list-keys) exit 0 ;;
    get)
        f=$(arq "$1" "$2")
        if [ -f "$f" ]; then cat "$f"; else
            case $2 in custom-list|binding|screenshot) echo "@as []" ;; *) echo "''" ;; esac
        fi ;;
    set)
        printf '%s\n' "$3" > "$(arq "$1" "$2")"
        if [ "$2" = custom-list ]; then printf '%s\n' "$3" >> "$d/historico"; fi ;;
    reset) rm -f "$(arq "$1" "$2")" ;;
esac
"""
