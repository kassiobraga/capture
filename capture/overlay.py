"""Captura: recorte, sobreposicao de selecao por monitor e sessao de captura."""
import os
import subprocess
import sys
import tempfile

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402

from . import MODOS
from .icons import _ret, botao
from .tema import ESCURO, rgb
from . import teste
from . import x11
from .x11 import listar_janelas


def interseccao(x, y, w, h, largura, altura):
    """Interseccao do retangulo com a imagem: (x, y, w, h) inteiros, ou None se vazia."""
    x0, y0 = int(x), int(y)
    x1, y1 = x0 + max(1, int(w)), y0 + max(1, int(h))
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(largura, x1), min(altura, y1)
    if x1 <= x0 or y1 <= y0:
        return None
    return x0, y0, x1 - x0, y1 - y0


def recortar(img, x, y, w, h, poligono=None):
    """Recorta img no retangulo (x, y, w, h), limitado aos contornos da imagem.

    Devolve None se o retangulo nao toca a imagem. Com `poligono` (pontos na
    mesma escala da imagem), o que fica fora dele sai transparente.
    """
    caixa = interseccao(x, y, w, h, img.get_width(), img.get_height())
    if caixa is None:
        return None
    x, y, w, h = caixa
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    if poligono:
        cr.move_to(poligono[0][0] - x, poligono[0][1] - y)
        for px_, py_ in poligono[1:]:
            cr.line_to(px_ - x, py_ - y)
        cr.close_path()
        cr.clip()
    cr.set_source_surface(img, -x, -y)
    cr.paint()
    return out


def ponto_na_captura(gx, gy, esc, x, y):
    """Ponto local de um monitor (gx, gy, escala esc) -> pixel da captura inteira."""
    return (gx + x) * esc, (gy + y) * esc


def janela_em(janelas, x, y):
    """Retangulo da janela mais acima que contem o pixel (x, y), ou None."""
    for r in reversed(janelas):
        if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]:
            return r
    return None


def alvo_janela(janelas, gx, gy, gw, gh, esc, x, y):
    """Alvo do modo janela sob o ponto local (x, y); sem janela, o monitor inteiro."""
    px_, py_ = ponto_na_captura(gx, gy, esc, x, y)
    return janela_em(janelas, px_, py_) or (gx * esc, gy * esc, gw * esc, gh * esc)


def caixa_selecao(modo, ini, fim, caminho, gw, gh):
    """Caixa (x0, y0, x1, y1) da selecao em coordenadas locais, presa ao monitor."""
    if modo == "livre" and caminho:
        xs = [p[0] for p in caminho]
        ys = [p[1] for p in caminho]
        return max(0, min(xs)), max(0, min(ys)), min(gw, max(xs)), min(gh, max(ys))
    x0, x1 = sorted((ini[0], fim[0]))
    y0, y1 = sorted((ini[1], fim[1]))
    return max(0, x0), max(0, y0), min(gw, x1), min(gh, y1)


MODOS_GRAVAR = [("ret", "Retângulo"), ("janela", "Janela"), ("tela", "Tela cheia")]
# Modos da selecao de captura imediata: a rolavel nao entra aqui, ela abre a sessao so com area.
MODOS_CAPTURA = [m for m in MODOS if m[0] != "rolavel"]
ICONES_MODO = {"ret": "ret", "janela": "janela", "tela": "tela", "livre": "livre", "rolavel": "rolavel"}
DICAS = {"ret": "Arraste para selecionar  ·  Esc cancela",
         "janela": "Clique em uma janela  ·  Esc cancela",
         "livre": "Desenhe em volta da área  ·  Esc cancela"}
DICAS_GRAVAR = {"ret": "Arraste a região para gravar  ·  Esc cancela",
                "janela": "Clique em uma janela para gravar  ·  Esc cancela"}
DICAS_ROLAR = {"ret": "Arraste a área para rolar e capturar  ·  Esc cancela",
               "janela": "Clique na janela para rolar e capturar  ·  Esc cancela"}
# a sobreposicao e sempre escura (a tela e escurecida): usa a paleta escura do tema
ACENTO = rgb(ESCURO["accent"])
FUNDO_ESCURO = (0.0, 0.0, 0.0)   # escurecimento neutro
SUPERFICIE = rgb(ESCURO["surface"])


def colchetes(cr, x, y, w, h, c=10):
    """Cantos em L (so tracado, sem pintar) nos quatro cantos do retangulo."""
    c = max(2, min(c, w / 2, h / 2))
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1), (x + w, y + h, -1, -1), (x, y + h, 1, -1)):
        cr.move_to(cx + dx * c, cy)
        cr.line_to(cx, cy)
        cr.line_to(cx, cy + dy * c)


class Sobreposicao(Gtk.Window):
    """Janela em tela cheia de um monitor, com a tela congelada e a selecao."""

    def __init__(self, sessao, monitor):
        super().__init__(application=sessao.app, decorated=False)
        self.s = sessao
        g = monitor.get_geometry()
        self.gx, self.gy, self.gw, self.gh = g.x, g.y, g.width, g.height
        self.esc = monitor.get_scale_factor()
        self.ini = self.fim = None
        self.caminho = []
        self.alvo = None
        self.add_css_class("sobre")

        self.area = Gtk.DrawingArea(hexpand=True, vexpand=True)
        self.area.set_draw_func(self._desenha)
        self.area.set_cursor(Gdk.Cursor.new_from_name("crosshair"))
        arr = Gtk.GestureDrag()
        arr.connect("drag-begin", self._ini)
        arr.connect("drag-update", self._mov)
        arr.connect("drag-end", self._fim)
        self.area.add_controller(arr)
        mov = Gtk.EventControllerMotion()
        mov.connect("motion", self._passa)
        self.area.add_controller(mov)

        self.pill = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=44)
        self.pill.add_css_class("vidro")
        self.pill.add_css_class("pill")
        self.dica = Gtk.Label(halign=Gtk.Align.CENTER, valign=Gtk.Align.START, margin_top=28)
        self.dica.add_css_class("vidro")
        self.dica.add_css_class("dica")
        self.dica.set_can_target(False)   # decorativa: o arraste ou clique que comeca embaixo dela vale
        self.bts = {}
        grupo = None
        for cod, nome in (MODOS_GRAVAR if sessao.apenas_area else MODOS_CAPTURA):
            b = botao(ICONES_MODO[cod], nome, alternar=True)
            if grupo:
                b.set_group(grupo)
            grupo = grupo or b
            b.connect("toggled", self._modo, cod)
            self.bts[cod] = b
            self.pill.append(b)
        self.pill.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4, margin_end=4))
        fechar = botao("x", "Cancelar (Esc)")
        fechar.connect("clicked", lambda *_: self.s.cancelar())
        self.pill.append(fechar)

        ov = Gtk.Overlay()
        ov.set_child(self.area)
        ov.add_overlay(self.pill)
        ov.add_overlay(self.dica)
        self.set_child(ov)
        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)
        self.connect("close-request", self._fechando)
        self.sincroniza()
        self.fullscreen_on_monitor(monitor)
        teste.grava_overlay(self)

    def _mostra_dica(self):
        """A dica aparece e some sozinha 2 s depois (continua nao-alvo do ponteiro)."""
        self.dica.remove_css_class("some")
        if getattr(self, "_t_dica", None):
            GLib.source_remove(self._t_dica)
        self._t_dica = GLib.timeout_add(2000, self._some_dica)

    def _some_dica(self):
        self._t_dica = None
        self.dica.add_css_class("some")
        return False

    def sincroniza(self):
        self._trava = True
        self.bts[self.s.modo].set_active(True)
        self._trava = False
        dicas = DICAS_ROLAR if self.s.rolar else (DICAS_GRAVAR if self.s.apenas_area else DICAS)
        self.dica.set_label(dicas.get(self.s.modo, ""))
        self.pill.set_visible(True)
        self.dica.set_visible(True)
        self._mostra_dica()
        self.ini = self.fim = self.alvo = None
        self.caminho = []
        self.area.queue_draw()

    def _modo(self, b, cod):
        if b.get_active() and not self._trava:
            self.s.definir_modo(cod)

    def _fechando(self, _janela):
        # Alt+F4 ou fechar pelo gerenciador de janelas: cancela a sessao inteira
        self.s.cancelar()
        return True

    def _tecla(self, _c, tecla, *_):
        if tecla == Gdk.KEY_Escape:
            self.s.cancelar()
            return True
        return False

    def _px(self, x, y):  # ponto local -> pixel da captura
        return ponto_na_captura(self.gx, self.gy, self.esc, x, y)

    def _passa(self, _c, x, y):
        if self.s.modo != "janela":
            return
        alvo = alvo_janela(self.s.janelas, self.gx, self.gy, self.gw, self.gh, self.esc, x, y)
        if alvo != self.alvo:
            self.alvo = alvo
            self.area.queue_draw()

    def _ini(self, _g, x, y):
        self.ini = self.fim = (x, y)
        self.caminho = [(x, y)]
        self.pill.set_visible(False)
        self.dica.set_visible(False)

    def _mov(self, g, dx, dy):
        if not self.ini:
            return
        self.fim = (self.ini[0] + dx, self.ini[1] + dy)
        self.caminho.append(self.fim)
        self.area.queue_draw()

    def _fim(self, g, dx, dy):
        modo = self.s.modo
        if modo == "janela":
            if self.alvo is None and self.ini:
                self._passa(None, *self.ini)
            if self.alvo:
                self.s.concluir(*self.alvo)
            return
        if not self.ini:
            return
        self.fim = (self.ini[0] + dx, self.ini[1] + dy)
        x0, y0, x1, y1 = self._caixa()
        if x1 - x0 < 5 or y1 - y0 < 5:
            self.ini = self.fim = None
            self.caminho = []
            self.pill.set_visible(True)
            self.dica.set_visible(True)
            self._mostra_dica()
            self.area.queue_draw()
            return
        a, b = self._px(x0, y0)
        c, d = self._px(x1, y1)
        if modo == "livre":
            self.s.concluir(a, b, c - a, d - b, [self._px(*p) for p in self.caminho])
        else:
            self.s.concluir(a, b, c - a, d - b)

    def _caixa(self):
        return caixa_selecao(self.s.modo, self.ini, self.fim, self.caminho, self.gw, self.gh)

    def _tela(self, cr):
        cr.save()
        cr.scale(1 / self.esc, 1 / self.esc)
        cr.set_source_surface(self.s.img, -self.gx * self.esc, -self.gy * self.esc)
        cr.paint()
        cr.restore()

    def _desenha(self, _a, cr, w, h):
        self._tela(cr)
        cr.set_source_rgba(*FUNDO_ESCURO, 0.45)
        cr.paint()
        modo = self.s.modo
        caixa = None
        if modo == "janela" and self.alvo:
            x, y, ww, hh = self.alvo
            caixa = (x / self.esc - self.gx, y / self.esc - self.gy, ww / self.esc, hh / self.esc)
            cr.rectangle(*caixa)
        elif modo == "livre" and len(self.caminho) > 1:
            cr.move_to(*self.caminho[0])
            for p in self.caminho[1:]:
                cr.line_to(*p)
            cr.close_path()
        elif modo == "ret" and self.ini and self.fim:
            x0, y0, x1, y1 = self._caixa()
            caixa = (x0, y0, x1 - x0, y1 - y0)
            cr.rectangle(*caixa)
        else:
            return
        caminho = cr.copy_path()
        cr.save()
        cr.clip()
        self._tela(cr)
        cr.restore()
        cr.append_path(caminho)
        cr.set_source_rgb(*ACENTO)
        cr.set_line_width(1.5)
        cr.set_line_join(cairo.LINE_JOIN_MITER)
        cr.stroke()
        if caixa and caixa[2] > 0:
            cr.set_line_width(2)
            cr.set_line_cap(cairo.LINE_CAP_SQUARE)
            colchetes(cr, *caixa)
            cr.stroke()
            txt = "%d × %d" % (round(caixa[2] * self.esc), round(caixa[3] * self.esc))
            lay = PangoCairo.create_layout(cr)
            lay.set_font_description(Pango.FontDescription("Sans Bold 9"))
            lay.set_text(txt)
            tw, th = lay.get_pixel_size()
            bx = min(max(4, caixa[0] + caixa[2] - tw - 20), w - tw - 24)
            by = caixa[1] + caixa[3] + 10
            if by + th + 12 > h:
                by = caixa[1] + caixa[3] - th - 20
            _ret(cr, bx, by, tw + 20, th + 10, 9)
            cr.set_source_rgba(*SUPERFICIE, 0.9)
            cr.fill_preserve()
            cr.set_source_rgba(1, 1, 1, 0.12)
            cr.set_line_width(1)
            cr.stroke()
            cr.set_source_rgb(*rgb(ESCURO["text"]))
            cr.move_to(bx + 10, by + 5)
            PangoCairo.show_layout(cr, lay)


def foto():
    """Foto da tela inteira: python-xlib (dentro do Flatpak) ou, sem ele, o maim."""
    erro_xlib = None
    if x11.tem_captura():
        try:
            return x11.foto_da_tela()
        except Exception as e:
            erro_xlib = e
            print("python-xlib nao capturou a tela:", e, file=sys.stderr)
    arq = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    try:
        subprocess.run(["maim", "-u", arq], check=True, timeout=10)
        return cairo.ImageSurface.create_from_png(arq)
    except FileNotFoundError:
        if erro_xlib:
            raise RuntimeError("Não foi possível capturar a tela (%s)." % erro_xlib)
        raise RuntimeError("O programa maim não foi encontrado. Instale o pacote maim.")
    except Exception as e:
        raise RuntimeError("O maim não conseguiu capturar a tela (%s)." % e)
    finally:
        if os.path.exists(arq):
            os.unlink(arq)


class Sessao:
    """Uma captura ou selecao de area: tira a foto da tela e, se preciso, abre a selecao."""

    def __init__(self, app, modo, atraso, pronto, apenas_area=False, rolar=False):
        self.apenas_area = bool(apenas_area)
        self.rolar = bool(rolar)
        if self.apenas_area and modo in ("livre", "rolavel"):
            modo = "ret"
        self.app, self.modo, self.pronto = app, modo, pronto
        self.img, self.janelas, self.sobre = None, [], []
        self.encerrada = False
        GLib.timeout_add(int(280 + atraso * 1000), self._fotografa)

    def _area_tela_cheia(self):
        return (0, 0, self.img.get_width(), self.img.get_height())

    def _fotografa(self):
        try:
            self.img = foto()
        except Exception as e:
            print("falha na captura:", e, file=sys.stderr)
            self._termina(None, str(e))
            return False
        if self.modo == "tela":
            self._termina(self._area_tela_cheia() if self.apenas_area else self.img)
            return False
        self.janelas = listar_janelas()
        mons = Gdk.Display.get_default().get_monitors()
        for i in range(mons.get_n_items()):
            o = Sobreposicao(self, mons.get_item(i))
            self.sobre.append(o)
            o.present()
        return False

    def definir_modo(self, modo):
        self.modo = modo
        if modo == "tela":
            self._termina(self._area_tela_cheia() if self.apenas_area else self.img)
            return
        for o in self.sobre:
            o.sincroniza()

    def _fecha(self):
        sobre, self.sobre = self.sobre, []
        for o in sobre:
            o.destroy()

    def _termina(self, resultado, erro=None):
        """Encerra a sessao uma unica vez: fecha as sobreposicoes e avisa quem pediu."""
        if self.encerrada:
            return
        self.encerrada = True
        self._fecha()
        if erro:
            self.pronto(None, erro)
        else:
            self.pronto(resultado)

    def cancelar(self):
        self._termina(None)

    def concluir(self, x, y, w, h, poligono=None):
        if self.apenas_area:
            caixa = interseccao(x, y, w, h, self.img.get_width(), self.img.get_height())
            if caixa is None:
                self._termina(None, "A seleção ficou fora da área da tela.")
            else:
                self._termina(caixa)
            return
        img = recortar(self.img, x, y, w, h, poligono)
        if img is None:
            self._termina(None, "A seleção ficou fora da imagem capturada.")
        else:
            self._termina(img)
