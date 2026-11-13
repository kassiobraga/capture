"""Editor de marcacao: itens desenhaveis, desfazer/refazer, corte e exportacao."""
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from . import CORES
from .icons import _ret
from .overlay import interseccao, recortar


def _layout_texto(cr, it):
    lay = PangoCairo.create_layout(cr)
    lay.set_font_description(Pango.FontDescription("Sans Bold %dpx" % it["tam"]))
    lay.set_text(it["txt"])
    return lay


def _prepara(cr, it):
    t = it["t"]
    cr.set_source_rgba(*it["cor"], 0.4 if t == "marca" else 1)
    cr.set_line_width(it["esp"])
    cr.set_line_cap(cairo.LINE_CAP_SQUARE if t == "marca" else cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)


def _caminho(cr, it):
    """Monta no contexto o caminho a traçar do item. False se nao ha nada a tracar."""
    t = it["t"]
    if t in ("caneta", "marca"):
        p = it["pts"]
        cr.move_to(*p[0])
        if len(p) == 1:
            cr.line_to(p[0][0] + 0.1, p[0][1])
        for q in p[1:]:
            cr.line_to(*q)
        return True
    (x0, y0), (x1, y1) = it["a"], it["b"]
    if t == "f_ret":
        _ret(cr, min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0), min(6, abs(x1 - x0) / 2, abs(y1 - y0) / 2))
    elif t == "f_elipse":
        if abs(x1 - x0) < 1 or abs(y1 - y0) < 1:
            return False
        cr.save()
        cr.translate((x0 + x1) / 2, (y0 + y1) / 2)
        cr.scale(abs(x1 - x0) / 2, abs(y1 - y0) / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
    else:
        cr.move_to(x0, y0)
        cr.line_to(x1, y1)
        if t == "f_seta":
            ang = math.atan2(y1 - y0, x1 - x0)
            c = max(10, it["esp"] * 4)
            for d in (2.6, -2.6):
                cr.move_to(x1, y1)
                cr.line_to(x1 + c * math.cos(ang + d), y1 + c * math.sin(ang + d))
    return True


def desenha_item(cr, it):
    _prepara(cr, it)
    if it["t"] == "texto":
        lay = _layout_texto(cr, it)
        cr.move_to(*it["a"])
        PangoCairo.show_layout(cr, lay)
        return
    if _caminho(cr, it):
        cr.stroke()


def item_vazio(it):
    """Forma arrastada por menos de ~2 px (um simples clique): nao vale guardar."""
    if "a" in it and "b" in it and it["t"].startswith("f_"):
        return abs(it["b"][0] - it["a"][0]) < 2 and abs(it["b"][1] - it["a"][1]) < 2
    return False


def acerta_item(it, p, tol=6):
    """O ponto p (coordenadas da imagem) cai sobre o desenho do item, com folga `tol`?"""
    cr = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
    if it["t"] == "texto":
        lay = _layout_texto(cr, it)
        ink = lay.get_pixel_extents()[0]
        x0, y0 = it["a"][0] + ink.x, it["a"][1] + ink.y
        return x0 - tol <= p[0] <= x0 + ink.width + tol and y0 - tol <= p[1] <= y0 + ink.height + tol
    cr.set_line_cap(cairo.LINE_CAP_SQUARE if it["t"] == "marca" else cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.set_line_width(it["esp"] + 2 * tol)
    if not _caminho(cr, it):
        return False
    return cr.in_stroke(*p)


def vista(w, h, iw, ih, margem=20):
    """Zoom e deslocamento (ox, oy) para exibir uma imagem iw x ih numa area w x h."""
    zoom = min(1, (w - 2 * margem) / iw, (h - 2 * margem) / ih)
    zoom = max(zoom, 0.02)
    return zoom, (w - iw * zoom) / 2, (h - ih * zoom) / 2


def para_imagem(x, y, zoom, ox, oy):
    """Ponto da area de desenho -> ponto da imagem."""
    return (x - ox) / zoom, (y - oy) / zoom


def caixa_item(it):
    if "pts" in it:
        xs = [p[0] for p in it["pts"]]
        ys = [p[1] for p in it["pts"]]
        return min(xs), min(ys), max(xs), max(ys)
    if it["t"] == "texto":
        return it["a"][0], it["a"][1], it["a"][0] + len(it["txt"]) * it["tam"] * 0.62, it["a"][1] + it["tam"] * 1.3
    (x0, y0), (x1, y1) = it["a"], it["b"]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


class Modelo:
    """Estado do documento (imagem base e marcacoes), sem nada de GTK.

    Quem herda define `mudou` (aviso de alteracao) e `redesenha`.
    """

    def _inicia_modelo(self, mudou):
        self.mudou = mudou
        self.base = None
        self.itens, self.desf, self.refz = [], [], []
        self._apagou = False

    def redesenha(self):
        pass

    def definir_imagem(self, img):
        self.base, self.itens, self.desf, self.refz = img, [], [], []
        self.redesenha()

    def _guarda(self):
        self.desf.append((self.base, list(self.itens)))
        self.refz = []

    def desfazer(self):
        if self.desf:
            self.refz.append((self.base, list(self.itens)))
            self.base, self.itens = self.desf.pop()
            self.redesenha()
            self.mudou()

    def refazer(self):
        if self.refz:
            self.desf.append((self.base, list(self.itens)))
            self.base, self.itens = self.refz.pop()
            self.redesenha()
            self.mudou()

    def exportar(self):
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.base.get_width(), self.base.get_height())
        cr = cairo.Context(out)
        cr.set_source_surface(self.base, 0, 0)
        cr.paint()
        for it in self.itens:
            desenha_item(cr, it)
        return out

    def adiciona(self, it):
        """Guarda um item novo (um passo de desfazer). False se o item for vazio."""
        if item_vazio(it):
            return False
        self._guarda()
        self.itens.append(it)
        return True

    def corta(self, x0, y0, x1, y1):
        """Corta a imagem (com as marcacoes aplicadas).

        False, sem alterar nada, se a area dentro da imagem tiver 8 px ou menos
        em algum lado (ou ficar toda fora dela).
        """
        base = self.base
        caixa = interseccao(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0),
                            base.get_width(), base.get_height())
        if caixa is None or caixa[2] <= 8 or caixa[3] <= 8:
            return False
        nova = recortar(self.exportar(), *caixa)
        self._guarda()
        self.base, self.itens = nova, []
        return True

    def apaga_arraste(self, p):
        """Um passo da borracha dentro de um arraste: so o primeiro acerto cria passo de desfazer."""
        achou = self.apaga_em(p, guarda=not self._apagou)
        if achou:
            self._apagou = True
        return achou

    def apaga_em(self, p, guarda=True):
        """Remove a marcacao mais acima sob o ponto p. Devolve True se removeu.

        Com guarda=False nao cria passo de desfazer (continuacao de um arraste).
        """
        for it in reversed(self.itens):
            if acerta_item(it, p):
                if guarda:
                    self._guarda()
                self.itens.remove(it)
                self.redesenha()
                self.mudou()
                return True
        return False


class Editor(Modelo, Gtk.DrawingArea):
    def __init__(self, mudou):
        super().__init__(hexpand=True, vexpand=True)
        self._inicia_modelo(mudou)
        self.ferr = "caneta"
        self.cores = {"caneta": CORES[1], "marca": CORES[2], "forma": CORES[0], "texto": CORES[1]}
        self.esp = {"caneta": 4, "marca": 18, "forma": 4, "texto": 6}
        self.atual = None
        self._p0 = (0, 0)
        self.zoom, self.ox, self.oy = 1, 0, 0
        self.set_draw_func(self._desenha)
        arr = Gtk.GestureDrag()
        arr.connect("drag-begin", self._ini)
        arr.connect("drag-update", self._mov)
        arr.connect("drag-end", self._fim)
        self.add_controller(arr)

    def redesenha(self):
        self.queue_draw()

    def definir_imagem(self, img):
        self.atual = None
        super().definir_imagem(img)

    # estado
    def grupo(self):
        return "forma" if self.ferr.startswith("f_") else self.ferr

    def cor(self):
        return self.cores.get(self.grupo(), CORES[1])

    # desenho
    def _desenha(self, _a, cr, w, h):
        if not self.base:
            return
        iw, ih = self.base.get_width(), self.base.get_height()
        self.zoom, self.ox, self.oy = vista(w, h, iw, ih)
        cr.translate(self.ox, self.oy)
        cr.scale(self.zoom, self.zoom)
        cr.rectangle(-1, -1, iw + 2, ih + 2)
        cr.set_source_rgba(0, 0, 0, 0.25)
        cr.fill()
        cr.rectangle(0, 0, iw, ih)
        cr.clip()
        cr.set_source_surface(self.base, 0, 0)
        cr.paint()
        for it in self.itens:
            desenha_item(cr, it)
        if self.atual:
            if self.atual["t"] == "cortar":
                (x0, y0), (x1, y1) = self.atual["a"], self.atual["b"]
                cr.set_source_rgba(0, 0, 0, 0.5)
                cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
                cr.rectangle(0, 0, iw, ih)
                cr.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                cr.fill()
                cr.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
                cr.set_source_rgb(1, 1, 1)
                cr.set_line_width(2 / self.zoom)
                cr.set_dash([6 / self.zoom, 4 / self.zoom])
                cr.stroke()
            else:
                desenha_item(cr, self.atual)

    def _img(self, x, y):
        return para_imagem(x, y, self.zoom, self.ox, self.oy)

    # gestos
    def _ini(self, _g, x, y):
        if not self.base:
            return
        p = self._img(x, y)
        self._p0 = p
        f = self.ferr
        if f in ("caneta", "marca"):
            self.atual = {"t": f, "cor": self.cor(), "esp": self.esp[f], "pts": [p]}
        elif f.startswith("f_"):
            self.atual = {"t": f, "cor": self.cor(), "esp": self.esp["forma"], "a": p, "b": p}
        elif f == "cortar":
            self.atual = {"t": "cortar", "a": p, "b": p}
        elif f == "borracha":
            self._apagou = False
            self._apaga(p)
        elif f == "texto":
            self._pede_texto(x, y, p)
        self.queue_draw()

    def _mov(self, _g, dx, dy):
        if not self.base:
            return
        p = (self._p0[0] + dx / self.zoom, self._p0[1] + dy / self.zoom)
        if self.ferr == "borracha":
            self._apaga(p)
        elif self.atual:
            if "pts" in self.atual:
                self.atual["pts"].append(p)
            else:
                self.atual["b"] = p
        self.queue_draw()

    def _fim(self, _g, dx, dy):
        it, self.atual = self.atual, None
        if not it:
            return
        if it["t"] == "cortar":
            (x0, y0), (x1, y1) = it["a"], it["b"]
            self.corta(x0, y0, x1, y1)
        else:
            self.adiciona(it)
        self.queue_draw()
        self.mudou()

    def _apaga(self, p):
        self.apaga_arraste(p)  # um arraste da borracha e um unico passo de desfazer

    def _pede_texto(self, x, y, p):
        pop = Gtk.Popover()
        pop.set_parent(self)
        r = Gdk.Rectangle()
        r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
        pop.set_pointing_to(r)
        ent = Gtk.Entry(placeholder_text="Texto", width_chars=22)
        pop.set_child(ent)

        def ok(*_):
            txt = ent.get_text().strip()
            pop.popdown()
            if txt:
                self.adiciona({"t": "texto", "cor": self.cor(), "txt": txt, "a": p,
                              "tam": 10 + self.esp["texto"] * 3, "esp": 2})
                self.queue_draw()
                self.mudou()

        ent.connect("activate", ok)
        pop.connect("closed", lambda *_: GLib.idle_add(pop.unparent))
        pop.popup()
        ent.grab_focus()
