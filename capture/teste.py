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
        botoes = {"capturar": jan.b_capturar, "gravar": jan.b_gravar,
                  "formato_gravacao": jan.mb_formato,
                  "copiar": jan.b_copiar, "salvar": jan.b_salvar,
                  "atraso": jan.mb_atraso, "formas": jan.mb_formas, "cor": jan.mb_cor,
                  "desfazer": jan.b_desf, "refazer": jan.b_refz,
                  "historico": jan.b_historico, "anonimo": jan.b_anonimo,
                  "hist_retencao": jan.mb_retencao, "hist_limpar": jan.b_limpar_hist}
        if jan.divisao.get_show_sidebar():
            for idx, info in enumerate(jan.itens_hist[:5]):
                for ch in ("abrir", "copiar", "pasta", "remover"):
                    botoes["hist_%s_%d" % (ch, idx)] = info[ch]
        botoes.update({"modo_" + k: b for k, b in jan.b_modo.items()})
        botoes.update({"cartao_" + k: b for k, b in jan.cartoes.items()})
        botoes.update(jan.ferrs)
        dados = {
            "xid": xid,
            "janela": [jan.get_width(), jan.get_height()],
            "transform": list(jan.get_surface_transform()),
            "botoes": {k: _caixa(b, jan) for k, b in botoes.items() if b.get_mapped()},
            "estado": {"abas": jan.abas.get_n_pages(), "modo": jan.modo, "atraso": jan.atraso, "atraso_rotulo": jan.lb_atraso.get_label(), "tela": jan.pilha.get_visible_child_name(),
                       "chip": jan.chip.get_label() if jan.chip.get_mapped() else None,
                       "dock": jan.dock.get_mapped(), "avisos": jan.n_avisos,
                       "faixa_avisos": _caixa(jan.toasts, jan), "faixa_alvo": jan.toasts.get_can_target(),
                       "historico_aberto": jan.divisao.get_show_sidebar(),
                       "historico_itens": len(jan.itens_hist),
                       "anonimo": jan.hist.anonimo,
                       "retencao": jan.hist.retencao,
                       "formato_gravacao": jan.hist.formato_gravacao,
                       "gravando": jan.barra_grav is not None},
            "editor": {"caixa": _caixa(ed, jan), "zoom": ed.zoom, "ox": ed.ox, "oy": ed.oy,
                       "imagem": [ed.base.get_width(), ed.base.get_height()] if ed.base else None,
                       "itens": len(ed.itens), "tipos": [i["t"] for i in ed.itens]},
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


def grava_overlay(ov):
    """Posicao dos botoes da barra de modos da sobreposicao (arquivo CAPTURE_TEST_GEOM + .ov<x>x<y>)."""
    base = os.environ.get("CAPTURE_TEST_GEOM")
    if not base:
        return
    arq = "%s.ov%dx%d" % (base, ov.gx, ov.gy)

    def grava():
        try:
            xid = None
            try:
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11  # noqa: F401
                xid = ov.get_surface().get_xid()
            except Exception:
                pass
            dados = {"xid": xid, "transform": list(ov.get_surface_transform()),
                     "botoes": {k: _caixa(b, ov) for k, b in ov.bts.items() if b.get_mapped()},
                     "dica": _caixa(ov.dica, ov) if ov.dica.get_mapped() else None}
            tmp = arq + ".tmp"
            with open(tmp, "w") as f:
                json.dump(dados, f)
            os.replace(tmp, arq)
        except Exception:
            traceback.print_exc()
        return ov.get_visible()

    GLib.timeout_add(300, grava)


def grava_barra_gravacao(barra):
    """Posicao e estado da barra flutuante de gravacao (arquivo CAPTURE_TEST_GEOM + .grav)."""
    base = os.environ.get("CAPTURE_TEST_GEOM")
    if not base:
        return
    arq = base + ".grav"

    def grava():
        if not barra.get_visible():
            try:
                os.unlink(arq)
            except OSError:
                pass
            return False
        try:
            xid = None
            try:
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11  # noqa: F401
                if barra.get_surface() is not None:
                    xid = barra.get_surface().get_xid()
            except Exception:
                pass
            dados = {
                "xid": xid,
                "janela": [barra.get_width(), barra.get_height()],
                "transform": list(barra.get_surface_transform()),
                "pos_x11": list(barra.pos_x11),
                "area_gravada": list(barra.area_px),
                "tempo": barra.lb_tempo.get_label(),
                "formato": barra.lb_fmt.get_label(),
                "botoes": {"parar": _caixa(barra.b_parar, barra)} if barra.b_parar.get_mapped() else {},
            }
            tmp = arq + ".tmp"
            with open(tmp, "w") as f:
                json.dump(dados, f)
            os.replace(tmp, arq)
        except Exception:
            traceback.print_exc()
        return True

    GLib.timeout_add(200, grava)
