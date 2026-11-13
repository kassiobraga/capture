"""Ganchos para os testes de ponta a ponta. Nao fazem nada sem as variaveis CAPTURE_TEST_*.

CAPTURE_TEST_GEOM=arquivo   grava (a cada 0,5 s) as posicoes dos botoes e da area de desenho
                            da janela principal, em JSON, para o teste saber onde clicar.
CAPTURE_TEST_SALVAR=arquivo Ctrl+S grava a imagem exportada nesse arquivo, sem dialogo.
"""
import json
import os
import traceback

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib  # noqa: E402

_ativo = False


def _caixa(w, raiz):
    ok, r = w.compute_bounds(raiz)
    return [r.get_x(), r.get_y(), r.get_width(), r.get_height()] if ok else None


def _grava(jan, arq):
    try:
        xid = None
        try:
            gi.require_version("GdkX11", "4.0")
            from gi.repository import GdkX11  # noqa: F401
            xid = jan.get_surface().get_xid()
        except Exception:
            pass
        ed = jan.editor
        botoes = {"novo": jan.b_novo, "formas": jan.mb_formas, "cor": jan.mb_cor,
                  "desfazer": jan.b_desf, "refazer": jan.b_refz}
        botoes.update(jan.ferrs)
        dados = {
            "xid": xid,
            "janela": [jan.get_width(), jan.get_height()],
            "transform": list(jan.get_surface_transform()),
            "botoes": {k: _caixa(b, jan) for k, b in botoes.items() if b.get_mapped()},
            "editor": {"caixa": _caixa(ed, jan), "zoom": ed.zoom, "ox": ed.ox, "oy": ed.oy,
                       "imagem": [ed.base.get_width(), ed.base.get_height()] if ed.base else None,
                       "itens": len(ed.itens)},
        }
        tmp = arq + ".tmp"
        with open(tmp, "w") as f:
            json.dump(dados, f)
        os.replace(tmp, arq)
    except Exception:
        traceback.print_exc()
    return True


def grava_geometria(jan):
    global _ativo
    arq = os.environ.get("CAPTURE_TEST_GEOM")
    if arq and not _ativo:
        _ativo = True
        GLib.timeout_add(500, _grava, jan, arq)
