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


RESERVA_DOCK = 92   # px livres embaixo para o dock flutuante
RAIO_IMAGEM = 6


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


def bloco_pixel(w, h):
    """Tamanho do bloco da pixelizacao: grande o bastante para tornar texto ilegivel."""
    return max(12, round(max(w, h) / 16))


def pixelar(img, x, y, w, h, bloco=None):
    """Recorte (x, y, w, h) da imagem em blocos, como uma superficie w x h."""
    b = bloco or bloco_pixel(w, h)
    pw, ph = max(1, math.ceil(w / b)), max(1, math.ceil(h / b))
    peq = cairo.ImageSurface(cairo.FORMAT_ARGB32, pw, ph)
    cr = cairo.Context(peq)
    cr.scale(pw / w, ph / h)
    cr.set_source_surface(img, -x, -y)
    cr.get_source().set_filter(cairo.FILTER_GOOD)  # media da area de cada bloco
    cr.paint()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.scale(w / pw, h / ph)
    cr.set_source_surface(peq, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_NEAREST)
    cr.paint()
    return out


def girar(img, sentido):
    """Imagem girada 90 graus: sentido 1 = horario, -1 = anti-horario."""
    w, h = img.get_width(), img.get_height()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, h, w)
    cr = cairo.Context(out)
    if sentido > 0:
        cr.translate(h, 0)
        cr.rotate(math.pi / 2)
    else:
        cr.translate(0, w)
        cr.rotate(-math.pi / 2)
    cr.set_source_surface(img, 0, 0)
    cr.paint()
    return out


def redimensionar(img, w, h):
    """Imagem em novo tamanho w x h (px), com filtro de boa qualidade."""
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.scale(w / img.get_width(), h / img.get_height())
    cr.set_source_surface(img, 0, 0)
    cr.get_source().set_filter(cairo.FILTER_BEST)
    cr.get_source().set_extend(cairo.EXTEND_PAD)  # bordas sem halo transparente
    cr.paint()
    return out


def proporcional(w0, h0, w=None, h=None):
    """Completa (w, h) mantendo a proporcao de w0 x h0; minimo de 1 px."""
    if w is not None:
        return max(1, round(w)), max(1, round(w * h0 / w0))
    return max(1, round(h * w0 / h0)), max(1, round(h))


def desenha_item(cr, it):
    if it["t"] == "pixelar":
        x, y = it["pos"]
        cr.set_source_surface(it["patch"], x, y)
        cr.rectangle(x, y, it["patch"].get_width(), it["patch"].get_height())
        cr.fill()
        return
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
    if it["t"] == "pixelar":
        x0, y0, x1, y1 = caixa_item(it)
        return x0 - tol <= p[0] <= x1 + tol and y0 - tol <= p[1] <= y1 + tol
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


def vista(w, h, iw, ih, margem=20, reserva=0):
    """Zoom e deslocamento (ox, oy) para exibir uma imagem iw x ih numa area w x h.

    `reserva` e a faixa de baixo ocupada pelo dock flutuante: a imagem nunca entra nela.
    """
    util = h - reserva
    zoom = min(1, (w - 2 * margem) / iw, (util - 2 * margem) / ih)
    zoom = max(zoom, 0.02)
    return zoom, (w - iw * zoom) / 2, (util - ih * zoom) / 2


def raio_cantos(iw, ih, zoom, raio=RAIO_IMAGEM):
    """Raio dos cantos arredondados em coordenadas da imagem, limitado a metade do menor lado."""
    return max(0.0, min(raio / zoom, iw / 2, ih / 2))


def para_imagem(x, y, zoom, ox, oy):
    """Ponto da area de desenho -> ponto da imagem."""
    return (x - ox) / zoom, (y - oy) / zoom


def caixa_item(it):
    if it["t"] == "pixelar":
        x, y = it["pos"]
        return x, y, x + it["patch"].get_width(), y + it["patch"].get_height()
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
        self.alterado = False  # ha mudancas desde a ultima vez que foi salvo

    def redesenha(self):
        pass

    def definir_imagem(self, img):
        self.base, self.itens, self.desf, self.refz = img, [], [], []
        self.alterado = False
        self.redesenha()

    def _guarda(self):
        self.desf.append((self.base, list(self.itens)))
        self.refz = []
        self.alterado = True

    def desfazer(self):
        if self.desf:
            self.refz.append((self.base, list(self.itens)))
            self.base, self.itens = self.desf.pop()
            self.alterado = True
            self.redesenha()
            self.mudou()

    def refazer(self):
        if self.refz:
            self.desf.append((self.base, list(self.itens)))
            self.base, self.itens = self.refz.pop()
            self.alterado = True
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

    def pixela(self, x0, y0, x1, y1):
        """Pixeliza a area (imagem e marcacoes por baixo), como uma marcacao apagavel.

        False, sem alterar nada, se a area dentro da imagem tiver 4 px ou menos em algum lado.
        """
        base = self.base
        caixa = interseccao(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0),
                            base.get_width(), base.get_height())
        if caixa is None or caixa[2] <= 4 or caixa[3] <= 4:
            return False
        x, y, w, h = caixa
        self._guarda()
        self.itens.append({"t": "pixelar", "pos": (x, y), "patch": pixelar(self.exportar(), x, y, w, h)})
        self.redesenha()
        return True

    def gira(self, sentido):
        """Gira 90 graus (1 = horario, -1 = anti-horario), com as marcacoes aplicadas."""
        nova = girar(self.exportar(), sentido)
        self._guarda()
        self.base, self.itens = nova, []
        self.redesenha()
        self.mudou()

    def redimensiona(self, w, h):
        """Muda o tamanho em px, com as marcacoes aplicadas. False se nada muda ou o tamanho e invalido."""
        w, h = int(w), int(h)
        if w < 1 or h < 1 or (w, h) == (self.base.get_width(), self.base.get_height()):
            return False
        nova = redimensionar(self.exportar(), w, h)
        self._guarda()
        self.base, self.itens = nova, []
        self.redesenha()
        self.mudou()
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


def cores_padrao():
    return {"caneta": CORES[1], "marca": CORES[2], "forma": CORES[0], "texto": CORES[1]}


def espessuras_padrao():
    return {"caneta": 4, "marca": 18, "forma": 4, "texto": 6}


class Editor(Modelo, Gtk.DrawingArea):
    def __init__(self, mudou, cores=None, esp=None):
        """`cores` e `esp` podem ser compartilhados entre editores (uma aba por captura)."""
        super().__init__(hexpand=True, vexpand=True)
        self._inicia_modelo(mudou)
        self.ferr = "caneta"
        self.cores = cores if cores is not None else cores_padrao()
        self.esp = esp if esp is not None else espessuras_padrao()
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
        self.zoom, self.ox, self.oy = vista(w, h, iw, ih, reserva=RESERVA_DOCK)
        cr.translate(self.ox, self.oy)
        cr.scale(self.zoom, self.zoom)
        raio = raio_cantos(iw, ih, self.zoom)
        for i in range(1, 9):   # sombra suave: camadas translucidas crescentes
            g = i * 2.2 / self.zoom
            _ret(cr, -g, -g + 5 / self.zoom, iw + 2 * g, ih + 2 * g, raio + g)
            cr.set_source_rgba(0, 0, 0, 0.018)   # leve, para funcionar no tema claro
            cr.fill()
        cr.save()
        _ret(cr, 0, 0, iw, ih, raio)   # so a imagem tem cantos arredondados
        cr.clip()
        cr.set_source_surface(self.base, 0, 0)
        cr.paint()
        cr.restore()
        cr.rectangle(0, 0, iw, ih)     # marcacoes e previa do corte vao ate o canto
        cr.clip()
        for it in self.itens:
            desenha_item(cr, it)
        if self.atual:
            if self.atual["t"] in ("area_cortar", "area_pixelar"):
                (x0, y0), (x1, y1) = self.atual["a"], self.atual["b"]
                if self.atual["t"] == "area_cortar":  # escurece o que vai sair
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
        elif f in ("cortar", "pixelar"):
            self.atual = {"t": "area_" + f, "a": p, "b": p}
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
        if it["t"] == "area_cortar":
            (x0, y0), (x1, y1) = it["a"], it["b"]
            self.corta(x0, y0, x1, y1)
        elif it["t"] == "area_pixelar":
            (x0, y0), (x1, y1) = it["a"], it["b"]
            self.pixela(x0, y0, x1, y1)
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
