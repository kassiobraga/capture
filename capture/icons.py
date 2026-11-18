"""Icones de linha desenhados com cairo e os botoes da interface."""
import math

import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk  # noqa: E402

def _linhas(cr, *segs):
    for s in segs:
        cr.move_to(s[0], s[1])
        for i in range(2, len(s), 2):
            cr.line_to(s[i], s[i + 1])
    cr.stroke()


def _ret(cr, x, y, w, h, r=1.5):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def ic_mais(cr):
    cr.set_line_width(1.6)
    _linhas(cr, (8, 3, 8, 13), (3, 8, 13, 8))


def ic_ret(cr):
    cr.set_dash([2.6, 1.8])
    _ret(cr, 2.5, 3.5, 11, 9)
    cr.stroke()


def ic_janela(cr):
    _ret(cr, 2.5, 3, 11, 10)
    cr.stroke()
    _linhas(cr, (2.5, 6, 13.5, 6))


def ic_tela(cr):
    _linhas(cr, (2.5, 6, 2.5, 2.5, 6, 2.5), (10, 2.5, 13.5, 2.5, 13.5, 6),
            (13.5, 10, 13.5, 13.5, 10, 13.5), (6, 13.5, 2.5, 13.5, 2.5, 10))


def ic_livre(cr):
    cr.set_dash([2.6, 1.8])
    cr.move_to(3, 9)
    cr.curve_to(2, 5, 5, 3, 8.5, 3)
    cr.curve_to(12, 3, 14.5, 6, 12.5, 9.5)
    cr.curve_to(11, 12.5, 7, 13.5, 5, 12.5)
    cr.curve_to(3.8, 12, 3.3, 10.5, 3, 9)
    cr.stroke()


def ic_capturar(cr):
    cr.set_dash([2.4, 1.8])
    _ret(cr, 2.2, 2.2, 11.6, 11.6, 2.5)
    cr.stroke()
    cr.set_dash([])
    cr.arc(8, 8, 1.7, 0, 2 * math.pi)
    cr.fill()


def ic_relogio(cr):
    cr.arc(8, 8, 5.5, 0, 2 * math.pi)
    cr.stroke()
    _linhas(cr, (8, 5, 8, 8.2, 10, 9.5))


def ic_x(cr):
    _linhas(cr, (4, 4, 12, 12), (12, 4, 4, 12))


def ic_caneta(cr):
    _linhas(cr, (3, 13, 3.7, 10, 10.5, 3.2, 12.6, 5.3, 5.8, 12, 3, 13))


def ic_marca(cr):
    _linhas(cr, (5, 10, 10, 4, 13, 6.5, 8, 12.5, 5, 10), (5, 10, 3.5, 13.5, 6.5, 13.5))


def ic_borracha(cr):
    _linhas(cr, (6, 13, 3, 10, 9.5, 3.5, 13.5, 7.5, 8, 13, 6, 13), (6, 13, 13, 13))


def ic_formas(cr):
    _ret(cr, 2.5, 6, 7, 7, 1)
    cr.stroke()
    cr.arc(10.5, 6, 3.5, 0, 2 * math.pi)
    cr.stroke()


def ic_f_ret(cr):
    _ret(cr, 2.5, 4, 11, 8, 1)
    cr.stroke()


def ic_f_elipse(cr):
    cr.save()
    cr.translate(8, 8)
    cr.scale(5.5, 4)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()
    cr.stroke()


def ic_f_linha(cr):
    _linhas(cr, (3, 13, 13, 3))


def ic_f_seta(cr):
    _linhas(cr, (3, 13, 13, 3), (8, 3, 13, 3, 13, 8))


def ic_cortar(cr):
    _linhas(cr, (4.5, 2, 4.5, 11.5, 14, 11.5), (2, 4.5, 11.5, 4.5, 11.5, 14))


def ic_texto(cr):
    _linhas(cr, (3.5, 4.5, 3.5, 3.5, 12.5, 3.5, 12.5, 4.5), (8, 3.5, 8, 12.5), (6.5, 12.5, 9.5, 12.5))


def ic_desfazer(cr):
    _linhas(cr, (5.5, 4, 3, 6.5, 5.5, 9))
    cr.move_to(3, 6.5)
    cr.line_to(9.5, 6.5)
    cr.arc(9.5, 9.5, 3, -math.pi / 2, math.pi / 2)
    cr.line_to(7, 12.5)
    cr.stroke()


def ic_refazer(cr):
    cr.translate(16, 0)
    cr.scale(-1, 1)
    ic_desfazer(cr)


def ic_copiar(cr):
    _ret(cr, 5.5, 5.5, 8, 8)
    cr.stroke()
    _linhas(cr, (10.5, 3.5, 10.5, 2.5, 2.5, 2.5, 2.5, 10.5, 3.5, 10.5))


def ic_salvar(cr):
    _linhas(cr, (3, 3, 11, 3, 13, 5, 13, 13, 3, 13, 3, 3), (5.5, 3, 5.5, 6.5, 9.5, 6.5, 9.5, 3),
            (5.5, 13, 5.5, 9.5, 10.5, 9.5, 10.5, 13))


def ic_pixelar(cr):
    _ret(cr, 2.5, 2.5, 11, 11)
    cr.stroke()
    for x, y in ((4.5, 4.5), (9, 4.5), (6.75, 6.75), (4.5, 9), (9, 9)):
        cr.rectangle(x, y, 2.5, 2.5)
    cr.fill()


def ic_imagem(cr):
    _ret(cr, 2.5, 3.5, 11, 9)
    cr.stroke()
    _linhas(cr, (2.5, 11, 6, 7.5, 8.5, 10, 10, 8.5, 13.5, 12))
    cr.arc(10.5, 6.2, 1, 0, 2 * math.pi)
    cr.fill()


def ic_girar_dir(cr):
    cr.arc_negative(8, 8.5, 5, -math.pi / 2, -math.pi * 0.2)
    cr.stroke()
    _linhas(cr, (5.8, 1.4, 8, 3.5, 5.8, 5.6))


def ic_girar_esq(cr):
    cr.translate(16, 0)
    cr.scale(-1, 1)
    ic_girar_dir(cr)


def ic_redimensionar(cr):
    _linhas(cr, (3, 13, 13, 3), (8.5, 3, 13, 3, 13, 7.5), (3, 8.5, 3, 13, 7.5, 13))


def ic_pdf(cr):
    _linhas(cr, (3.5, 2.5, 9.5, 2.5, 12.5, 5.5, 12.5, 13.5, 3.5, 13.5, 3.5, 2.5), (9.5, 2.5, 9.5, 5.5, 12.5, 5.5))
    _linhas(cr, (5.5, 8.5, 10.5, 8.5), (5.5, 11, 9, 11))


def ic_historico(cr):
    cr.arc(8, 8, 5.3, -0.72 * math.pi, 0.95 * math.pi)
    cr.stroke()
    _linhas(cr, (3.8, 2.2, 3.8, 5.2, 6.8, 5.2), (8, 5.2, 8, 8.2, 10.2, 9.5))


def ic_anonimo(cr):
    _linhas(cr, (2, 7.2, 14, 7.2), (4.5, 7.2, 5.8, 3.2, 8, 3.9, 10.2, 3.2, 11.5, 7.2), (7.4, 11, 8.6, 11))
    cr.arc(5.2, 11, 2.1, 0, 2 * math.pi)
    cr.stroke()
    cr.arc(10.8, 11, 2.1, 0, 2 * math.pi)
    cr.stroke()


def ic_abrir(cr):
    _linhas(cr, (7, 3.5, 3, 3.5, 3, 13, 12.5, 13, 12.5, 9), (7.5, 8.5, 13, 3), (9.5, 3, 13, 3, 13, 6.5))


def ic_pasta(cr):
    _linhas(cr, (2.5, 4.5, 6.3, 4.5, 7.8, 6, 13.5, 6, 13.5, 12.5, 2.5, 12.5, 2.5, 4.5))


def ic_lixeira(cr):
    _linhas(cr, (3, 4.5, 13, 4.5), (6, 4.5, 6, 3, 10, 3, 10, 4.5),
            (4.5, 4.5, 5.2, 13, 10.8, 13, 11.5, 4.5), (6.8, 7, 6.8, 10.8), (9.2, 7, 9.2, 10.8))


def ic_gravar(cr):
    cr.arc(8, 8, 5.5, 0, 2 * math.pi)
    cr.stroke()
    cr.arc(8, 8, 2.6, 0, 2 * math.pi)
    cr.fill()


def ic_parar(cr):
    _ret(cr, 4.0, 4.0, 8.0, 8.0, 1.5)
    cr.fill()


def ic_video(cr):
    _ret(cr, 2.2, 3.2, 11.6, 9.6, 1.8)
    cr.stroke()
    cr.move_to(6.6, 5.6)
    cr.line_to(10.6, 8.0)
    cr.line_to(6.6, 10.4)
    cr.close_path()
    cr.fill()


ICONES = {k[3:]: v for k, v in globals().items() if k.startswith("ic_")}


class Icone(Gtk.DrawingArea):
    """Icone de linha desenhado com cairo na cor do texto do widget."""

    def __init__(self, nome, tam=16, cor=None):
        super().__init__()
        self.nome, self.cor = nome, cor
        self.set_content_width(tam)
        self.set_content_height(tam)
        self.set_valign(Gtk.Align.CENTER)
        self.set_halign(Gtk.Align.CENTER)
        self.set_draw_func(self._desenha)

    def _desenha(self, _a, cr, w, h):
        if self.nome == "cor":
            cr.arc(w / 2, h / 2, w / 2 - 1, 0, 2 * math.pi)
            cr.set_source_rgb(*self.cor())
            cr.fill_preserve()
            c = self.get_color()
            cr.set_source_rgba(c.red, c.green, c.blue, 0.5)
            cr.set_line_width(1)
            cr.stroke()
            return
        c = self.get_color()
        cr.set_source_rgba(c.red, c.green, c.blue, c.alpha)
        cr.scale(w / 16, h / 16)
        cr.set_line_width(1.6)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        ICONES[self.nome](cr)


def botao(icone, dica, texto=None, alternar=False, plano=True):
    b = Gtk.ToggleButton() if alternar else Gtk.Button()
    if texto:
        cx = Gtk.Box(spacing=7)
        cx.append(Icone(icone))
        cx.append(Gtk.Label(label=texto))
        b.set_child(cx)
    else:
        b.set_child(Icone(icone))
    b.set_tooltip_text(dica)
    if plano:
        b.add_css_class("flat")
    return b
