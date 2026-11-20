"""Janela principal e aplicacao."""
import datetime
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, ATRASOS, CORES, ICONE, MODOS, NOME, PRGNAME
from .arquivos import nome_captura, nome_gravacao, nome_livre, pasta_capturas, pasta_para_exibir
from . import exportar
from .editor import Editor, cores_padrao, espessuras_padrao, proporcional
from .gravar import FORMATOS_GRAVACAO, Gravador, formatar_duracao, posicionar_barra, tem_ffmpeg
from .historico import RETENCOES, Registro, rotulo_data
from .icons import Icone, botao
from .overlay import Sessao
from . import area, teste, x11
from .tema import CLARO, ESCURO, tokens_css

# Identidade: cinzas grafite neutros, um unico acento verde-agua e paineis solidos
# (preenchimento translucido + borda clara de 1 px + sombra suave + raio generoso).
# Os tokens sao definidos uma vez por tema; o resto deriva deles.
CSS_BASE = """
@define-color window_bg_color @cap_surface;   @define-color window_fg_color @cap_text;
@define-color view_bg_color @cap_surface;     @define-color view_fg_color @cap_text;
@define-color headerbar_bg_color @cap_surface; @define-color headerbar_fg_color @cap_text;
@define-color popover_bg_color @cap_raised;   @define-color popover_fg_color @cap_text;
@define-color card_bg_color @cap_raised;      @define-color card_fg_color @cap_text;
@define-color dialog_bg_color @cap_raised;    @define-color dialog_fg_color @cap_text;
@define-color accent_bg_color @cap_accent;    @define-color accent_color @cap_accent;
@define-color accent_fg_color @cap_accent_fg;

headerbar { background: @cap_surface; color: @cap_text; box-shadow: none;
            border-bottom: 1px solid @cap_edge; min-height: 48px; }
.titulo-app { font-weight: 700; letter-spacing: 0.3px; padding: 0 6px; }
.mudo { color: alpha(@cap_text, 0.65); }
.vazio { background: @cap_surface; }
.tela { background: @cap_canvas; }

.vidro { background: @cap_raised; border: 1px solid @cap_edge; border-radius: 12px;
         box-shadow: 0 2px 8px alpha(black, 0.18); }
.dock, .pill { padding: 6px 8px; }
.dock button, .dock menubutton > button, .pill button, .modos button, .atraso > button {
        min-width: 34px; min-height: 34px; padding: 0; border-radius: 10px;
        background: none; box-shadow: none; border: none; color: @cap_text; }
.dock button:hover, .dock menubutton > button:hover, .pill button:hover, .modos button:hover,
.atraso > button:hover { background: alpha(@cap_text, 0.08); }
.dock button:checked, .dock menubutton.on > button, .pill button:checked, .modos button:checked {
        background: alpha(@cap_accent, 0.18); color: @cap_accent; }
.dock separator { background: @cap_edge; min-width: 1px; margin: 6px 4px; }
.chip { padding: 5px 12px; border-radius: 10px; font-size: 0.86em; margin: 0 0 18px 18px; }
.dica { padding: 7px 16px; border-radius: 12px; font-size: 0.92em; transition: opacity 400ms ease; }
.dica.some { opacity: 0; }

.modos { background: none; padding: 0; }
.modos button { min-width: 38px; min-height: 32px; margin-top: 8px; margin-bottom: 8px; }
.atraso > button { min-width: 0; padding: 0 10px; min-height: 32px;
                   margin-top: 8px; margin-bottom: 8px; background: none; }
.atraso label { font-weight: 600; font-size: 0.92em; }
button.capturar { background: @cap_accent; color: @cap_accent_fg; border-radius: 10px; font-weight: 700;
                  min-height: 32px; margin-top: 8px; margin-bottom: 8px;
                  padding: 0 10px; box-shadow: none; border: none; }
button.capturar:hover { background: shade(@cap_accent, 1.08); }
headerbar separator { background: @cap_edge; min-width: 1px; }
button.gravar { min-width: 38px; min-height: 28px; padding: 0; border-radius: 10px;
                background: none; box-shadow: none; border: none; color: @cap_text; }
button.gravar:hover { background: alpha(#EF4444, 0.14); }
button.gravar:disabled { opacity: 0.35; }
headerbar button.discreto { min-width: 34px; min-height: 32px; margin-top: 8px; margin-bottom: 8px;
                            padding: 0; border-radius: 10px; background: none;
                            box-shadow: none; color: @cap_text; }
headerbar button.discreto:hover { background: alpha(@cap_text, 0.08); }
headerbar button.discreto:checked { background: alpha(@cap_accent, 0.18); color: @cap_accent; }
headerbar button.discreto:disabled { opacity: 0.35; }

headerbar windowcontrols > button, headerbar windowcontrols > button.close { background: none; background-image: none; color: @cap_text; box-shadow: none; }
headerbar windowcontrols > button:hover { background: alpha(@cap_text, 0.08); }
.cartao { background: none; border: 1px solid @cap_edge; border-radius: 10px;
          padding: 10px 14px; min-width: 84px; box-shadow: none; color: @cap_text; }
.cartao:hover { border-color: alpha(@cap_text, 0.35); background: alpha(@cap_text, 0.04); }
.cartao label { font-weight: 500; font-size: 0.92em; }
.amostra { min-width: 26px; min-height: 26px; padding: 0; border-radius: 13px; }
.sobre { background: @cap_canvas; }
tabbar .box { background: @cap_surface; border-bottom: 1px solid @cap_edge; box-shadow: none; }
tabbar separator { background: none; }
tabbar tab { min-height: 32px; min-width: 110px;
             margin-top: 4px; margin-bottom: 4px; margin-left: 1px; margin-right: 1px;
             border-radius: 8px; background: none; border: none; box-shadow: none;
             color: @cap_text; padding: 0 6px; }
tabbar tab:hover { background: alpha(@cap_text, 0.08); }
tabbar tab:selected { background: alpha(@cap_accent, 0.14); color: @cap_text; }
tabbar tab:selected:hover { background: alpha(@cap_accent, 0.20); }
tabbar tab button, tabbar tab button.close { min-width: 20px; min-height: 20px; padding: 0; margin: 0;
                                            border-radius: 6px; background: none; border: none;
                                            box-shadow: none; color: alpha(@cap_text, 0.70); }
tabbar tab button:hover, tabbar tab button.close:hover { background: alpha(@cap_text, 0.12); color: @cap_text; }
.menu-imagem button { padding: 6px 10px; }

.painel-hist { background: @cap_surface; border-right: 1px solid @cap_edge; }
.topo-hist { padding: 10px 10px 8px; border-bottom: 1px solid @cap_edge; }
.titulo-hist { font-weight: 700; font-size: 0.95em; }
.retencao > button { padding: 4px 8px; min-height: 28px; border-radius: 8px;
                     background: alpha(@cap_text, 0.05); border: 1px solid @cap_edge;
                     box-shadow: none; color: @cap_text; }
.retencao > button:hover { background: alpha(@cap_text, 0.10); }
.retencao label { font-size: 0.85em; font-weight: 500; }
.aviso-anon { background: alpha(@cap_accent, 0.12); border: 1px solid alpha(@cap_accent, 0.28);
              border-radius: 8px; padding: 6px 8px; font-size: 0.82em; }
.item-hist { background: @cap_raised; border: 1px solid @cap_edge; border-radius: 10px; padding: 7px; }
.item-hist button.abrir-item { padding: 4px; border-radius: 8px; background: none; border: none;
                               box-shadow: none; color: @cap_text; }
.item-hist button.abrir-item:hover { background: alpha(@cap_text, 0.06); }
.mini-quadro { background: @cap_canvas; border: 1px solid @cap_edge; border-radius: 6px;
               min-width: 72px; min-height: 48px; }
.data-hist { font-weight: 600; font-size: 0.88em; }
.sub-hist { font-size: 0.80em; }
.acoes-hist button { min-width: 28px; min-height: 28px; padding: 0; border-radius: 8px; }

.barra-gravacao { background: @cap_raised; border: 1px solid @cap_edge; padding: 6px 10px; }
.ponto-grav { background: #EF4444; border-radius: 5px; min-width: 10px; min-height: 10px; }
.tempo-grav { font-weight: 700; font-size: 0.95em; font-variant-numeric: tabular-nums; padding: 0 2px; }
.fmt-grav { font-size: 0.75em; font-weight: 700; padding: 2px 6px; border-radius: 6px;
            background: alpha(@cap_text, 0.08); color: alpha(@cap_text, 0.80); }
button.parar-grav { background: #EF4444; color: #FFFFFF; border-radius: 8px; font-weight: 700;
                    min-height: 28px; padding: 0 10px; border: none; box-shadow: none; }
button.parar-grav:hover { background: #DC2626; }
button.parar-grav:disabled { opacity: 0.55; }
"""


ATALHOS_FERRAMENTAS = {Gdk.KEY_p: "caneta", Gdk.KEY_h: "marca", Gdk.KEY_e: "borracha", Gdk.KEY_r: "f_ret",
                       Gdk.KEY_o: "f_elipse", Gdk.KEY_l: "f_linha", Gdk.KEY_a: "f_seta", Gdk.KEY_t: "texto",
                       Gdk.KEY_x: "cortar", Gdk.KEY_b: "pixelar"}


def tema_escuro(esquema="org.cinnamon.desktop.interface", chave="gtk-theme"):
    """True/False conforme o tema GTK do ambiente; None se o esquema nao existe.

    Gio.Settings.new() aborta o processo (nao levanta excecao) quando o esquema
    nao esta instalado, entao ele e consultado antes.
    """
    try:
        fonte = Gio.SettingsSchemaSource.get_default()
        sch = fonte.lookup(esquema, True) if fonte else None
        if sch is None or not sch.has_key(chave):
            return None
        return "dark" in Gio.Settings.new(esquema).get_string(chave).lower()
    except Exception:
        return None


def nome_de_tema_escuro(nome):
    """True se o nome de um tema GTK indica variante escura (Mint-Y-Dark-Blue, Adwaita-dark...)."""
    return "dark" in (nome or "").lower()


def tema_escuro_do_portal():
    """True/False conforme o tema GTK informado pelo portal de configuracoes; None se indisponivel.

    No Flatpak o esquema do Cinnamon nao existe, mas o portal repassa o gtk-theme do
    desktop. O libadwaita troca o gtk-theme-name interno por "Adwaita-empty" ao
    iniciar, entao o valor e lido direto do portal.
    """
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Settings", None)
        r = proxy.call_sync("Read", GLib.Variant("(ss)", ("org.gnome.desktop.interface", "gtk-theme")),
                            Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        while isinstance(r, (tuple, list)) and r:
            r = r[0]
        return nome_de_tema_escuro(r) if isinstance(r, str) and r else None
    except Exception:
        return None


def decodifica_caminho(v):
    """Valor de uma opcao FILENAME (bytestring, lista de bytes ou str) -> str."""
    if isinstance(v, (list, tuple)):
        v = bytes(v)
    if isinstance(v, bytes):
        v = os.fsdecode(v.rstrip(b"\0"))
    return v


class BarraGravacao(Gtk.Window):
    """Barra compacta com contador e botao Parar, posicionada fora da area gravada."""

    def __init__(self, jan, area_px, formato):
        super().__init__(application=jan.get_application(), title="Gravando: " + NOME,
                         decorated=False, resizable=False)
        self.jan = jan
        self.area_px = tuple(area_px)
        self.pos_x11 = (0, 0)

        caixa = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        caixa.add_css_class("barra-gravacao")

        self.ponto = Gtk.Box(valign=Gtk.Align.CENTER)
        self.ponto.add_css_class("ponto-grav")
        caixa.append(self.ponto)

        self.lb_tempo = Gtk.Label(label="00:00", valign=Gtk.Align.CENTER)
        self.lb_tempo.add_css_class("tempo-grav")
        caixa.append(self.lb_tempo)

        self.lb_fmt = Gtk.Label(label=(formato or "mp4").upper(), valign=Gtk.Align.CENTER)
        self.lb_fmt.add_css_class("fmt-grav")
        caixa.append(self.lb_fmt)

        self.lb_parar = Gtk.Label(label="Parar")
        cx_p = Gtk.Box(spacing=6)
        cx_p.append(Icone("parar", 14))
        cx_p.append(self.lb_parar)
        self.b_parar = Gtk.Button(child=cx_p, tooltip_text="Parar e salvar gravação")
        self.b_parar.add_css_class("parar-grav")
        self.b_parar.connect("clicked", lambda *_: self.jan.parar_gravacao())
        caixa.append(self.b_parar)

        self.set_child(caixa)
        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)
        self.connect("close-request", self._fechando)

    def _tecla(self, _c, tecla, *_):
        if tecla == Gdk.KEY_Escape:
            self.jan.parar_gravacao(cancelar=self.jan.gravador is None)
            return True
        return False

    def _fechando(self, _jan):
        self.jan.parar_gravacao(cancelar=self.jan.gravador is None)
        return True

    def posicionar_fora(self):
        """Move esta barra no X11 para fora da area gravada."""
        mons = []
        esc_padrao = 1
        ms = Gdk.Display.get_default().get_monitors()
        for i in range(ms.get_n_items()):
            m = ms.get_item(i)
            g = m.get_geometry()
            esc = m.get_scale_factor()
            if i == 0:
                esc_padrao = esc
            mons.append((g.x * esc, g.y * esc, g.width * esc, g.height * esc))
        surf = self.get_surface()
        esc = surf.get_scale_factor() if surf is not None else esc_padrao
        bw = max(210, self.get_width() * esc) if self.get_width() > 20 else 236 * esc
        bh = max(40, self.get_height() * esc) if self.get_height() > 10 else 46 * esc
        bx, by = posicionar_barra(self.area_px, mons, bw, bh)
        self.pos_x11 = (bx, by)
        if surf is not None:
            try:
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11  # noqa: F401
                x11.posicionar_janela_x11(surf.get_xid(), bx, by, acima=True)
            except Exception:
                pass
        return False

    def atualizar_tempo(self, segundos):
        self.lb_tempo.set_label(formatar_duracao(segundos))

    def modo_salvando(self):
        self.b_parar.set_sensitive(False)
        self.lb_parar.set_label("Salvando…")


class BarraRolagem(Gtk.Window):
    """Barra compacta com 'Rolando...' e botao Parar, fora da area rolada."""

    def __init__(self, jan, area_px):
        super().__init__(application=jan.get_application(), title="Rolando: " + NOME,
                         decorated=False, resizable=False)
        self.jan = jan
        self.area_px = tuple(area_px)
        self.pos_x11 = (0, 0)

        caixa = Gtk.Box(spacing=8, valign=Gtk.Align.CENTER)
        caixa.add_css_class("barra-gravacao")

        lb = Gtk.Label(label="Rolando…", valign=Gtk.Align.CENTER)
        lb.add_css_class("tempo-grav")
        caixa.append(lb)

        cx_p = Gtk.Box(spacing=6)
        cx_p.append(Icone("parar", 14))
        cx_p.append(Gtk.Label(label="Parar"))
        b_parar = Gtk.Button(child=cx_p, tooltip_text="Parar rolagem (Esc)")
        b_parar.add_css_class("parar-grav")
        b_parar.connect("clicked", lambda *_: self.jan.parar_rolagem())
        caixa.append(b_parar)

        self.set_child(caixa)
        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)
        self.connect("close-request", self._fechando)

    def _tecla(self, _c, tecla, *_):
        if tecla == Gdk.KEY_Escape:
            self.jan.parar_rolagem()
            return True
        return False

    def _fechando(self, _jan):
        self.jan.parar_rolagem()
        return True

    def posicionar_fora(self):
        """Move esta barra no X11 para fora da area rolada."""
        mons = []
        esc_padrao = 1
        ms = Gdk.Display.get_default().get_monitors()
        for i in range(ms.get_n_items()):
            m = ms.get_item(i)
            g = m.get_geometry()
            esc = m.get_scale_factor()
            if i == 0:
                esc_padrao = esc
            mons.append((g.x * esc, g.y * esc, g.width * esc, g.height * esc))
        surf = self.get_surface()
        esc = surf.get_scale_factor() if surf is not None else esc_padrao
        bw = max(180, self.get_width() * esc) if self.get_width() > 20 else 200 * esc
        bh = max(40, self.get_height() * esc) if self.get_height() > 10 else 46 * esc
        bx, by = posicionar_barra(self.area_px, mons, bw, bh)
        self.pos_x11 = (bx, by)
        if surf is not None:
            try:
                gi.require_version("GdkX11", "4.0")
                from gi.repository import GdkX11  # noqa: F401
                x11.posicionar_janela_x11(surf.get_xid(), bx, by, acima=True)
            except Exception:
                pass
        return False


class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=NOME, default_width=840, default_height=560)
        self.sessao = None
        self.barra_grav = None
        self.barra_rol = None
        self._cancelar_rolagem = False
        self.gravador = None
        self._cap_grav = None
        self._timer_grav = None
        self._timer_contagem = None
        self._finalizando_grav = False
        self.salvo_em = None
        self.modo = MODOS[0][0]
        self.atraso = ATRASOS[0][0]
        self.ferr = "caneta"
        self.n_capturas = 0  # numera as abas: Captura 1, Captura 2...
        # cores e espessuras valem para todas as abas
        self.cores, self.esp = cores_padrao(), espessuras_padrao()
        # editor sem imagem, fora da tela, usado enquanto nao ha nenhuma aba
        self._sem_aba = Editor(self._mudou, self.cores, self.esp)
        self.editor = self._sem_aba
        self.hist = Registro()
        self.itens_hist = []
        self._sinc_hist = False
        self._sinc_anon = False

        # ---- cabecalho: historico, titulo, anonimo | modos + atraso | copiar, salvar, gravar, capturar
        cab = Adw.HeaderBar()
        self.b_historico = botao("historico", "Histórico de capturas (Ctrl+H)", alternar=True)
        self.b_historico.add_css_class("discreto")
        self.b_historico.set_valign(Gtk.Align.CENTER)
        self.b_historico.connect("toggled", self._alternar_historico)
        cab.pack_start(self.b_historico)
        t = Gtk.Label(label=NOME)
        t.add_css_class("titulo-app")
        t.set_valign(Gtk.Align.CENTER)
        cab.pack_start(t)
        self.b_anonimo = botao("anonimo", "Modo anônimo: não salva em disco nem registra no histórico",
                               alternar=True)
        self.b_anonimo.add_css_class("discreto")
        self.b_anonimo.set_valign(Gtk.Align.CENTER)
        self._sinc_anon = True
        self.b_anonimo.set_active(self.hist.anonimo)
        self._sinc_anon = False
        self.b_anonimo.connect("toggled", self._anonimo_trocado)
        cab.pack_start(self.b_anonimo)

        centro = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
        modos = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
        modos.add_css_class("modos")
        self.b_modo = {}
        grupo = None
        for cod, nome in MODOS:
            b = botao(cod, nome, alternar=True, plano=False)
            b.set_valign(Gtk.Align.CENTER)
            if grupo:
                b.set_group(grupo)
            grupo = grupo or b
            b.connect("toggled", self._modo_escolhido, cod)
            self.b_modo[cod] = b
            modos.append(b)
        self.b_modo[self.modo].set_active(True)
        centro.append(modos)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_top=8, margin_bottom=8)
        centro.append(sep)

        self.b_gravar = botao("gravar", "Gravar a tela (Ctrl+G)", plano=False)
        self.b_gravar.add_css_class("gravar")
        pop_fmt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                          margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        self.b_formato = {}
        gr_f = None
        rotulos_fmt = {"mp4": "Vídeo MP4", "gif": "Animação GIF"}
        for cod_f, _ in FORMATOS_GRAVACAO:
            bf = Gtk.ToggleButton(label=rotulos_fmt.get(cod_f, cod_f.upper()))
            bf.add_css_class("flat")
            if gr_f:
                bf.set_group(gr_f)
            gr_f = gr_f or bf
            bf.connect("clicked", self._formato_grav_escolhido, cod_f)
            self.b_formato[cod_f] = bf
            pop_fmt.append(bf)
        self.b_formato[self.hist.formato_gravacao].set_active(True)
        self.pop_gravar = Gtk.Popover(child=pop_fmt)
        self.pop_gravar.set_parent(self.b_gravar)
        self.b_gravar.connect("destroy", lambda *_: self.pop_gravar.unparent())
        self.b_gravar.connect("clicked", lambda *_: self.pop_gravar.popup())
        self.b_gravar.get_popover = lambda: self.pop_gravar
        self.b_gravar.popup = self.pop_gravar.popup
        self.b_gravar.popdown = self.pop_gravar.popdown
        if not tem_ffmpeg():
            self.b_gravar.set_sensitive(False)
            self.b_gravar.set_tooltip_text("O FFmpeg não foi encontrado no sistema para gravar a tela.")
        centro.append(self.b_gravar)

        self.lb_atraso = Gtk.Label(label="0s")
        cx = Gtk.Box(spacing=6)
        cx.append(Icone("relogio"))
        cx.append(self.lb_atraso)
        self.mb_atraso = Gtk.MenuButton(tooltip_text="Atraso antes de capturar ou gravar")
        self.mb_atraso.add_css_class("atraso")
        self.mb_atraso.set_valign(Gtk.Align.CENTER)
        self.mb_atraso.set_child(cx)
        lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=4, margin_bottom=4,
                        margin_start=4, margin_end=4)
        self.b_atraso = {}
        gr = None
        for seg, nome in ATRASOS:
            b = Gtk.ToggleButton(label=nome)
            b.add_css_class("flat")
            if gr:
                b.set_group(gr)
            gr = gr or b
            b.connect("clicked", self._atraso_escolhido, seg)
            self.b_atraso[seg] = b
            lista.append(b)
        self.b_atraso[self.atraso].set_active(True)
        self.mb_atraso.set_popover(Gtk.Popover(child=lista))
        centro.append(self.mb_atraso)
        cab.set_title_widget(centro)

        self.b_capturar = botao("capturar", "Nova captura (Ctrl+N)", "Capturar", plano=False)
        self.b_capturar.add_css_class("capturar")
        self.b_capturar.set_valign(Gtk.Align.CENTER)
        self.b_capturar.connect("clicked", lambda *_: self.nova_captura())
        cab.pack_end(self.b_capturar)

        self.b_salvar = botao("salvar", "Salvar como (Ctrl+S)")
        self.b_salvar.add_css_class("discreto")
        self.b_salvar.set_valign(Gtk.Align.CENTER)
        self.b_salvar.connect("clicked", lambda *_: self.salvar_como())
        cab.pack_end(self.b_salvar)
        self.b_copiar = botao("copiar", "Copiar (Ctrl+C)")
        self.b_copiar.add_css_class("discreto")
        self.b_copiar.set_valign(Gtk.Align.CENTER)
        self.b_copiar.connect("clicked", lambda *_: self.copiar())
        cab.pack_end(self.b_copiar)
        self.b_pdf = botao("pdf", "Juntar todas as abas num PDF")
        self.b_pdf.add_css_class("discreto")
        self.b_pdf.set_valign(Gtk.Align.CENTER)
        self.b_pdf.connect("clicked", lambda *_: self.juntar_pdf())
        cab.pack_end(self.b_pdf)
        self.b_pdf.set_visible(False)
        self.b_copiar.set_sensitive(False)
        self.b_salvar.set_sensitive(False)

        # ---- dock flutuante de ferramentas
        self.dock = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=18)
        self.dock.add_css_class("vidro")
        self.dock.add_css_class("dock")
        self.ferrs = {}
        grupo = None

        def alterna(cod, icone, dica, onde):
            nonlocal grupo
            b = botao(icone, dica, alternar=True)
            if grupo:
                b.set_group(grupo)
            grupo = grupo or b
            b.connect("toggled", self._ferr, cod)
            self.ferrs[cod] = b
            onde.append(b)
            return b

        alterna("caneta", "caneta", "Caneta (P)", self.dock)
        alterna("marca", "marca", "Marca-texto (H)", self.dock)
        alterna("borracha", "borracha", "Borracha (E): apaga a marcação clicada", self.dock)
        self.mb_formas = Gtk.MenuButton(tooltip_text="Formas")
        self.mb_formas.set_child(Icone("formas"))
        cx = Gtk.Box(spacing=2, margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        for cod, dica in (("f_ret", "Retângulo (R)"), ("f_elipse", "Elipse (O)"), ("f_linha", "Linha (L)"),
                          ("f_seta", "Seta (A)")):
            alterna(cod, cod, dica, cx).connect("clicked", lambda *_: self.mb_formas.popdown())
        self.mb_formas.set_popover(Gtk.Popover(child=cx))
        self.dock.append(self.mb_formas)
        alterna("texto", "texto", "Texto (T)", self.dock)
        alterna("cortar", "cortar", "Cortar a imagem (X)", self.dock)
        alterna("pixelar", "pixelar", "Pixelar (B): esconde uma área, como senhas e nomes", self.dock)
        self.mb_imagem = Gtk.MenuButton(tooltip_text="Girar e redimensionar")
        self.mb_imagem.set_child(Icone("imagem"))
        mi = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_top=4, margin_bottom=4,
                     margin_start=4, margin_end=4)
        mi.add_css_class("menu-imagem")
        for ic, rot, acao in (("girar_esq", "Girar para a esquerda", lambda: self.editor.gira(-1)),
                              ("girar_dir", "Girar para a direita", lambda: self.editor.gira(1)),
                              ("redimensionar", "Redimensionar…", self.pede_tamanho)):
            b = botao(ic, rot, rot)
            b.get_child().set_halign(Gtk.Align.START)
            b.connect("clicked", lambda _b, a=acao: (self.mb_imagem.popdown(), a()))
            mi.append(b)
        self.mb_imagem.set_popover(Gtk.Popover(child=mi))
        self.dock.append(self.mb_imagem)
        self.dock.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self.ic_cor = Icone("cor", 18, lambda: self.editor.cor())
        self.mb_cor = Gtk.MenuButton(tooltip_text="Cor e espessura")
        self.mb_cor.set_child(self.ic_cor)
        pc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=8, margin_bottom=8,
                     margin_start=8, margin_end=8)
        linha = Gtk.Box(spacing=6)
        for c in CORES:
            b = Gtk.Button()
            b.add_css_class("amostra")
            b.add_css_class("flat")
            b.set_child(Icone("cor", 22, lambda c=c: c))
            b.connect("clicked", self._cor, c)
            linha.append(b)
        pc.append(linha)
        self.esc_esp = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 30, 1)
        self.esc_esp.set_value(4)
        self.esc_esp.connect("value-changed", self._esp)
        pc.append(self.esc_esp)
        self.mb_cor.set_popover(Gtk.Popover(child=pc))
        self.dock.append(self.mb_cor)
        self.dock.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.b_desf = botao("desfazer", "Desfazer (Ctrl+Z)")
        self.b_desf.connect("clicked", lambda *_: self.editor.desfazer())  # sempre a aba atual
        self.b_refz = botao("refazer", "Refazer (Ctrl+Y)")
        self.b_refz.connect("clicked", lambda *_: self.editor.refazer())
        self.dock.append(self.b_desf)
        self.dock.append(self.b_refz)

        # ---- chip de informacao (tamanho da imagem)
        self.chip = Gtk.Label(halign=Gtk.Align.START, valign=Gtk.Align.END)
        self.chip.add_css_class("vidro")
        self.chip.add_css_class("chip")

        # ---- estado vazio: icone, titulo, ajuda e um cartao por modo
        vazio = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER,
                        valign=Gtk.Align.CENTER)
        vazio.add_css_class("vazio")
        vazio.append(Gtk.Image(icon_name=ICONE, pixel_size=96))
        tt = Gtk.Label(label=NOME)
        tt.add_css_class("title-1")
        vazio.append(tt)
        aj = Gtk.Label(label="Pressione Print para capturar, escolha um modo ou clique em Gravar.\n"
                             "As capturas e gravações são salvas automaticamente.", justify=Gtk.Justification.CENTER)
        aj.add_css_class("mudo")
        vazio.append(aj)
        cartoes = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER, margin_top=12)
        self.cartoes = {}
        for cod, nome in MODOS:
            b = Gtk.Button()
            b.add_css_class("cartao")
            b.add_css_class("flat")
            cv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, halign=Gtk.Align.CENTER)
            cv.append(Icone(cod, 22))
            cv.append(Gtk.Label(label=nome))
            b.set_child(cv)
            b.set_tooltip_text("Capturar: " + nome)
            b.connect("clicked", lambda _b, c=cod: self.nova_captura(c))
            self.cartoes[cod] = b
            cartoes.append(b)
        vazio.append(cartoes)

        self.abas = Adw.TabView(vexpand=True)
        self.abas.connect("notify::selected-page", self._aba_trocada)
        self.abas.connect("notify::n-pages", self._abas_mudaram)
        self.abas.connect("close-page", self._fechar_aba)
        # barra de abas logo abaixo do cabecalho, fora da area dos avisos
        self.barra_abas = Adw.TabBar(view=self.abas, autohide=False, expand_tabs=False)
        self.barra_abas.set_visible(False)

        self.pilha = Gtk.Stack()
        self.pilha.add_named(vazio, "vazio")
        self.pilha.add_named(self.abas, "editor")
        ov = Gtk.Overlay()
        ov.set_child(self.pilha)
        ov.add_overlay(self.dock)
        ov.add_overlay(self.chip)
        self.dock.set_visible(False)
        self.chip.set_visible(False)
        # avisos no alto da tela: nunca cobrem o dock nem o selo de tamanho, que ficam embaixo
        # A faixa so recebe cliques enquanto ha um aviso na tela (para o botao de fechar do aviso
        # funcionar); fora disso nao captura nada e nao atrapalha o desenho no alto da imagem.
        self.toasts = Adw.ToastOverlay(valign=Gtk.Align.START, halign=Gtk.Align.CENTER)
        self.toasts.set_size_request(460, 88)
        self.toasts.set_can_target(False)
        self.n_avisos = 0
        ov.add_overlay(self.toasts)

        self.divisao = Adw.OverlaySplitView(show_sidebar=False, min_sidebar_width=248, max_sidebar_width=276)
        self.divisao.set_sidebar(self._monta_painel_historico())
        self.divisao.set_content(ov)
        self.divisao.connect("notify::show-sidebar", self._painel_mudou)
        self.connect("notify::is-active", self._foco_janela)

        tv = Adw.ToolbarView()
        tv.add_top_bar(cab)
        tv.add_top_bar(self.barra_abas)
        tv.set_content(self.divisao)
        self.set_content(tv)
        self.ferrs["caneta"].set_active(True)
        self._atualiza_historico()

        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)
        teste.grava_geometria(self)

    # ---- modo, atraso e formato de gravacao
    def _modo_escolhido(self, b, cod):
        if b.get_active():
            self.modo = cod

    def _define_modo(self, cod):
        if cod in self.b_modo:
            self.b_modo[cod].set_active(True)

    def _atraso_escolhido(self, b, seg):
        # "clicked" (e nao "toggled") para fechar o menu tambem ao reescolher a opcao atual
        self.atraso = seg
        self.lb_atraso.set_label("%ds" % seg)
        b.set_active(True)
        self.mb_atraso.popdown()

    def _formato_grav_escolhido(self, b, fmt):
        self._define_formato_gravacao(fmt)
        b.set_active(True)
        self.pop_gravar.popdown()
        self.nova_gravacao(formato=fmt)

    def _define_formato_gravacao(self, fmt):
        cod = (fmt or "").lower()
        if cod in dict(FORMATOS_GRAVACAO):
            self.hist.definir_formato_gravacao(cod)
            if hasattr(self, "b_formato") and cod in self.b_formato:
                self.b_formato[cod].set_active(True)

    # ---- ferramentas
    def _ferr(self, b, cod):
        if not b.get_active():
            return
        self.ferr = cod
        self.editor.ferr = cod
        if cod.startswith("f_"):
            self.mb_formas.add_css_class("on")
        else:
            self.mb_formas.remove_css_class("on")
        self.esc_esp.set_value(self.editor.esp.get(self.editor.grupo(), 4))
        self.ic_cor.queue_draw()
        self._cursor()

    def _cursor(self):
        self.editor.set_cursor(Gdk.Cursor.new_from_name("text" if self.ferr == "texto" else "crosshair"))

    def _cor(self, _b, c):
        self.editor.cores[self.editor.grupo()] = c
        self.ic_cor.queue_draw()
        self.mb_cor.popdown()

    def _esp(self, s):
        g = self.editor.grupo()
        if g in self.editor.esp:
            self.editor.esp[g] = s.get_value()

    def _tecla(self, _c, tecla, _cod, estado):
        if isinstance(self.get_focus(), Gtk.Text):
            return False
        ctrl = estado & Gdk.ModifierType.CONTROL_MASK
        shift = estado & Gdk.ModifierType.SHIFT_MASK
        t = Gdk.keyval_to_lower(tecla)
        if ctrl and t == Gdk.KEY_n:
            self.nova_captura()
        elif ctrl and t == Gdk.KEY_g:
            if self.barra_grav is not None:
                self.parar_gravacao()
            elif not tem_ffmpeg():
                self.present()
                self.mostra_erro("O FFmpeg não foi encontrado no sistema para gravar a tela.")
            else:
                self.pop_gravar.popup()
        elif ctrl and t == Gdk.KEY_h:
            self.b_historico.set_active(not self.b_historico.get_active())
        elif ctrl and t == Gdk.KEY_c and self.editor.base:
            self.copiar()
        elif ctrl and t == Gdk.KEY_s and self.editor.base:
            self.salvar_como()
        elif ctrl and t == Gdk.KEY_w and self.abas.get_selected_page():
            self.abas.close_page(self.abas.get_selected_page())
        elif ctrl and (t == Gdk.KEY_y or (t == Gdk.KEY_z and shift)):
            self.editor.refazer()
        elif ctrl and t == Gdk.KEY_z:
            self.editor.desfazer()
        elif not ctrl and not (estado & Gdk.ModifierType.ALT_MASK) and t in ATALHOS_FERRAMENTAS:
            self.ferrs[ATALHOS_FERRAMENTAS[t]].set_active(True)
        else:
            return False
        return True

    # ---- captura e gravacao
    def nova_captura(self, modo=None, atraso=None):
        if self.sessao or self.barra_grav or self.barra_rol:
            return
        if modo in dict(MODOS):
            self._define_modo(modo)
        modo = self.modo
        if modo == "rolavel":
            self.nova_rolagem(atraso=atraso)
            return
        if atraso is None:
            atraso = self.atraso
        self._visivel = self.get_visible()
        self.set_visible(False)
        if self._visivel:
            atraso += 0.35  # tempo para o Cinnamon terminar de esconder a janela antes da foto
        self.sessao = Sessao(self.get_application(), modo, atraso, self._capturou)

    def _capturou(self, img, erro=None):
        modo = self.sessao.modo if self.sessao else None
        self.sessao = None
        if modo in dict(MODOS):
            self._define_modo(modo)
        if erro:
            ficou = self._visivel or self.abas.get_n_pages()
            self.present()
            self.mostra_erro(erro, None if ficou else self.get_application().quit)
            return
        if img is None:
            if self._visivel or self.abas.get_n_pages():
                self.present()
            else:
                self.get_application().quit()
            return
        self.abrir(img, novo=True)

    def nova_rolagem(self, atraso=None):
        if self.sessao or self.barra_grav or self.barra_rol:
            return
        self._define_modo("rolavel")
        self._cancelar_rolagem = False
        self._visivel = self.get_visible()
        self.set_visible(False)
        espera_jan = 0.35 if self._visivel else 0.0
        self.sessao = Sessao(self.get_application(), "ret", espera_jan,
                             self._area_rolagem_escolhida, apenas_area=True, rolar=True)

    def parar_rolagem(self):
        self._cancelar_rolagem = True

    def _area_rolagem_escolhida(self, area_px, erro=None):
        self.sessao = None
        if erro:
            ficou = self._visivel or self.abas.get_n_pages()
            self.present()
            self.mostra_erro(erro, None if ficou else self.get_application().quit)
            return
        if area_px is None:
            if self._visivel or self.abas.get_n_pages():
                self.present()
            else:
                self.get_application().quit()
            return
        self.barra_rol = BarraRolagem(self, area_px)
        self.barra_rol.present()
        self.barra_rol.posicionar_fora()
        GLib.timeout_add(50, self.barra_rol.posicionar_fora)
        GLib.timeout_add(350, lambda: self._iniciar_thread_rolagem(area_px))

    def _iniciar_thread_rolagem(self, area_px):
        if self.barra_rol is None or self._cancelar_rolagem:
            self._finalizar_rolagem(None)
            return False
        from .rolagem import rolar_regiao

        def worker():
            res = rolar_regiao(*area_px, cancelado=lambda: self._cancelar_rolagem)
            GLib.idle_add(self._finalizar_rolagem, res)

        threading.Thread(target=worker, name="capture-rolagem", daemon=True).start()
        return False

    def _finalizar_rolagem(self, resultado):
        if self.barra_rol is not None:
            self.barra_rol.destroy()
            self.barra_rol = None
        self.present()
        if resultado is None:
            return
        if resultado.quadros <= 1 and resultado.motivo == "cancelado" and not resultado.linhas:
            return
        img = resultado.superficie()
        self.abrir(img, novo=True)
        mensagens = {
            "fim": "Página inteira capturada",
            "limite_altura": "Parou no limite de 30000 px",
            "limite_quadros": "Parou no limite de quadros",
            "sem_sobreposicao": "Não foi possível emendar: o conteúdo mudou durante a rolagem. Mostrando o que foi capturado",
            "cancelado": "Rolagem interrompida"
        }
        aviso = mensagens.get(resultado.motivo)
        if aviso and resultado.quadros > 1:
            self._status(aviso)

    def nova_gravacao(self, modo=None, formato=None, atraso=None):
        if self.barra_grav is not None:
            self.parar_gravacao()
            return
        if self.sessao:
            return
        if formato:
            self._define_formato_gravacao(formato)
        if not tem_ffmpeg():
            self.present()
            self.mostra_erro("O FFmpeg não foi encontrado no sistema para gravar a tela.")
            return
        if modo in dict(MODOS):
            self._define_modo(modo)
        modo_grav = self.modo if self.modo not in ("livre", "rolavel") else "ret"
        atraso_grav = self.atraso if atraso is None else atraso
        self._visivel = self.get_visible()
        self.set_visible(False)
        espera_jan = 0.35 if self._visivel else 0.0
        if modo_grav == "tela":
            self._contagem_restante = 0
            self.sessao = Sessao(self.get_application(), "tela", espera_jan + atraso_grav,
                                 self._area_gravacao_escolhida, apenas_area=True)
        else:
            self._contagem_restante = int(atraso_grav)
            self.sessao = Sessao(self.get_application(), modo_grav, espera_jan,
                                 self._area_gravacao_escolhida, apenas_area=True)

    def _area_gravacao_escolhida(self, area_px, erro=None):
        modo = self.sessao.modo if self.sessao else None
        self.sessao = None
        if modo in dict(MODOS):
            self._define_modo(modo)
        if erro:
            ficou = self._visivel or self.abas.get_n_pages()
            self.present()
            self.mostra_erro(erro, None if ficou else self.get_application().quit)
            return
        if area_px is None:
            if self._visivel or self.abas.get_n_pages():
                self.present()
            else:
                self.get_application().quit()
            return
        self._finalizando_grav = False
        self.barra_grav = BarraGravacao(self, area_px, self.hist.formato_gravacao)
        self.barra_grav.present()
        self.barra_grav.posicionar_fora()
        GLib.timeout_add(50, self.barra_grav.posicionar_fora)
        teste.grava_barra_gravacao(self.barra_grav)
        if self._contagem_restante > 0:
            self.barra_grav.lb_tempo.set_label("%ds…" % self._contagem_restante)
            self._timer_contagem = GLib.timeout_add(1000, self._passo_contagem_grav)
        else:
            GLib.timeout_add(180, self._inicia_gravador)

    def _passo_contagem_grav(self):
        if self.barra_grav is None or self._finalizando_grav:
            self._timer_contagem = None
            return False
        self._contagem_restante -= 1
        if self._contagem_restante > 0:
            self.barra_grav.lb_tempo.set_label("%ds…" % self._contagem_restante)
            return True
        self._timer_contagem = None
        self.barra_grav.lb_tempo.set_label("00:00")
        self._inicia_gravador()
        return False

    def _inicia_gravador(self):
        if self.barra_grav is None or self._finalizando_grav:
            return False
        self.barra_grav.posicionar_fora()
        fmt = self.hist.formato_gravacao
        era_anon = self.hist.anonimo
        pasta_anon = tempfile.mkdtemp(prefix="capture-grav-anon-") if era_anon else None
        destino = nome_gravacao(pasta_anon if era_anon else pasta_capturas(), fmt)
        self._era_anon_grav = era_anon
        self._pasta_anon_grav = pasta_anon
        try:
            cap = x11.CapturadorRegiao(*self.barra_grav.area_px)
            grav = Gravador(cap.w, cap.h, destino, formato=fmt,
                            fonte_quadros=cap.quadro, para_superficie=cap.para_superficie)
            grav.iniciar()
        except Exception as e:
            if "cap" in locals():
                cap.fechar()
            if pasta_anon:
                shutil.rmtree(pasta_anon, ignore_errors=True)
            self.barra_grav.destroy()
            self.barra_grav = None
            ficou = self._visivel or self.abas.get_n_pages()
            self.present()
            self.mostra_erro("Não foi possível iniciar a gravação:\n%s" % e,
                             None if ficou else self.get_application().quit)
            return False
        self._cap_grav = cap
        self.gravador = grav
        self._timer_grav = GLib.timeout_add(250, self._tick_gravacao)
        return False

    def _tick_gravacao(self):
        if self.barra_grav is None or self.gravador is None or self._finalizando_grav:
            self._timer_grav = None
            return False
        self.barra_grav.atualizar_tempo(self.gravador.duracao())
        return True

    def parar_gravacao(self, cancelar=False):
        if self._finalizando_grav or self.barra_grav is None:
            return
        self._finalizando_grav = True
        if self._timer_contagem:
            GLib.source_remove(self._timer_contagem)
            self._timer_contagem = None
        if self._timer_grav:
            GLib.source_remove(self._timer_grav)
            self._timer_grav = None
        if self.gravador is None:
            self.barra_grav.destroy()
            self.barra_grav = None
            self._finalizando_grav = False
            if self._visivel or self.abas.get_n_pages():
                self.present()
            else:
                self.get_application().quit()
            return
        self.barra_grav.modo_salvando()
        grav, cap = self.gravador, self._cap_grav
        self.gravador = self._cap_grav = None
        era_anon = getattr(self, "_era_anon_grav", False)
        pasta_anon = getattr(self, "_pasta_anon_grav", None)
        self._pasta_anon_grav = None

        def finaliza():
            info, erro = None, None
            try:
                info = grav.parar(cancelar=cancelar)
            except Exception as e:
                erro = str(e)
            finally:
                if cap is not None:
                    cap.fechar()
            GLib.idle_add(self._gravacao_concluida, info, erro, cancelar, era_anon, pasta_anon)

        threading.Thread(target=finaliza, name="capture-fim-grav", daemon=True).start()

    def _gravacao_concluida(self, info, erro, cancelar, era_anon, pasta_anon):
        if self.barra_grav is not None:
            self.barra_grav.destroy()
            self.barra_grav = None
        self._finalizando_grav = False
        if erro:
            if pasta_anon:
                shutil.rmtree(pasta_anon, ignore_errors=True)
            ficou = self._visivel or self.abas.get_n_pages()
            self.present()
            self.mostra_erro("Não foi possível concluir a gravação:\n%s" % erro,
                             None if ficou else self.get_application().quit)
            return False
        if cancelar or info is None:
            if pasta_anon:
                shutil.rmtree(pasta_anon, ignore_errors=True)
            if self._visivel or self.abas.get_n_pages():
                self.present()
            else:
                self.get_application().quit()
            return False
        if era_anon:
            self.present()
            self._salva_gravacao_anonima(info, pasta_anon)
            return False
        self.hist.adicionar(info["caminho"], info["miniatura_img"],
                            tipo=info["formato"], duracao=info["duracao"])
        self._atualiza_historico()
        if self.abas.get_n_pages() == 0 and not self.divisao.get_show_sidebar():
            self.b_historico.set_active(True)
        self.present()
        self._status("Gravação salva em " + pasta_para_exibir(info["caminho"]))
        teste.grava_geometria(self)
        return False

    def _salva_gravacao_anonima(self, info, pasta_anon):
        origem = info["caminho"]
        fmt = info["formato"]
        direto = os.environ.get("CAPTURE_TEST_SALVAR")
        if direto:
            try:
                shutil.move(origem, direto)
                self._status("Modo anônimo  ·  Salvo em " + pasta_para_exibir(direto))
            finally:
                if pasta_anon:
                    shutil.rmtree(pasta_anon, ignore_errors=True)
            return
        pasta = pasta_capturas()
        filtro = (("Vídeo MP4", "*.mp4"),) if fmt == "mp4" else (("Animação GIF", "*.gif"),)
        dlg = self._dialogo_salvar("Salvar gravação (modo anônimo)", os.path.basename(origem), pasta, filtro)

        def feito(d, res):
            try:
                arq = d.save_finish(res).get_path()
            except GLib.Error:
                if pasta_anon:
                    shutil.rmtree(pasta_anon, ignore_errors=True)
                self._status("Gravação anônima descartada")
                return
            if not arq.lower().endswith("." + fmt):
                arq = nome_livre(arq + "." + fmt)
            try:
                os.makedirs(os.path.dirname(os.path.abspath(arq)), exist_ok=True)
                shutil.move(origem, arq)
                self._status("Modo anônimo  ·  Salvo em " + pasta_para_exibir(arq))
            except Exception as e:
                self._status("Não foi possível salvar: %s" % e)
            finally:
                if pasta_anon:
                    shutil.rmtree(pasta_anon, ignore_errors=True)

        dlg.save(self, None, feito)

    def mostra_erro(self, msg, depois=None):
        dlg = Adw.MessageDialog(transient_for=self, heading=NOME, body=msg)
        dlg.add_response("ok", "OK")
        if depois:
            dlg.connect("response", lambda *_: depois())
        dlg.present()

    def abrir_arquivo(self, caminho):
        try:
            img = cairo.ImageSurface.create_from_png(caminho)
        except Exception as e:
            print("não foi possível abrir:", e, file=sys.stderr)
            self.present()
            self.mostra_erro("Não foi possível abrir %s.\nSó arquivos PNG são aceitos." % caminho)
            return
        self.abrir(img, titulo=os.path.basename(caminho))

    def _dimensiona(self, iw, ih, so_crescer=False):
        """Tamanho da janela para a imagem, limitado ao monitor.

        Com so_crescer, a janela so aumenta (uma aba nova menor nao a encolhe).
        """
        lim_w, lim_h = 1280, 820
        display = Gdk.Display.get_default()
        mon = None
        surf = self.get_surface()
        if surf is not None:
            mon = display.get_monitor_at_surface(surf)  # o monitor em que a janela esta
        if mon is None:
            mons = display.get_monitors()
            mon = mons.get_item(0) if mons.get_n_items() else None
        if mon is not None:
            g = mon.get_geometry()
            lim_w, lim_h = min(lim_w, g.width - 80), min(lim_h, g.height - 100)
        # altura: cabecalho, barra de abas e o dock flutuante embaixo da imagem
        extra_w = 260 if self.divisao.get_show_sidebar() else 0
        w, h = int(min(max(iw + 60 + extra_w, 780), lim_w)), int(min(max(ih + 240, 480), lim_h))
        if so_crescer:
            aw, ah = self.get_width(), self.get_height()
            if w <= aw and h <= ah:
                return
            w, h = max(w, aw), max(h, ah)
        if self.get_mapped():
            # GTK 4 ignora set_default_size com a janela visivel: esconde e mostra de novo
            self.set_visible(False)
        self.set_default_size(w, h)

    def abrir(self, img, novo=False, titulo=None):
        """Abre a imagem numa aba nova (e a seleciona)."""
        ed = Editor(self._mudou, self.cores, self.esp)
        ed.add_css_class("tela")
        ed.definir_imagem(img)
        ed.ferr = self.ferr
        dica = titulo
        if titulo is None:
            self.n_capturas += 1
            titulo = "Captura %d" % self.n_capturas
            dica = "Capturada às %s" % datetime.datetime.now().strftime("%H:%M:%S")
        ed.titulo = titulo
        primeira = self.abas.get_n_pages() == 0
        pag = self.abas.append(ed)
        pag.set_title(titulo)
        pag.set_tooltip(dica)
        self.editor = ed
        self.abas.set_selected_page(pag)
        self.pilha.set_visible_child_name("editor")
        self.dock.set_visible(True)
        self.chip.set_visible(True)
        self.b_copiar.set_sensitive(True)
        self.b_salvar.set_sensitive(True)
        self._dimensiona(img.get_width(), img.get_height(), so_crescer=not primeira)
        self.salvo_em = None
        partes = []
        if novo:
            if self.copiar(quieto=True):
                partes.append("Copiado para a área de transferência")
            if self.hist.anonimo:
                ed.alterado = False
                partes.append("Modo anônimo (não salvo)")
            else:
                self.salvo_em = self._salva_auto()
                if self.salvo_em:
                    ed.alterado = False
                    self.hist.adicionar(self.salvo_em, img)
                    self._atualiza_historico()
                    partes.append("Salvo em " + pasta_para_exibir(self.salvo_em))
        self._status(*partes)
        self.present()
        teste.grava_geometria(self)

    # ---- historico e modo anonimo
    def _monta_painel_historico(self):
        painel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        painel.add_css_class("painel-hist")

        topo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        topo.add_css_class("topo-hist")

        cab = Gtk.Box(spacing=6)
        tit = Gtk.Label(label="Histórico", xalign=0, hexpand=True)
        tit.add_css_class("titulo-hist")
        cab.append(tit)
        self.b_limpar_hist = botao("lixeira", "Limpar a lista (mantém os arquivos salvos)")
        self.b_limpar_hist.connect("clicked", lambda *_: self._limpar_historico())
        cab.append(self.b_limpar_hist)
        topo.append(cab)

        self.lb_retencao = Gtk.Label(label=dict(RETENCOES)[self.hist.retencao], xalign=0, hexpand=True)
        cx_ret = Gtk.Box(spacing=6)
        cx_ret.append(Icone("relogio", 14))
        cx_ret.append(self.lb_retencao)
        self.mb_retencao = Gtk.MenuButton(
            tooltip_text="Quando limpar esta lista (os arquivos na pasta Capturas sempre ficam)")
        self.mb_retencao.add_css_class("retencao")
        self.mb_retencao.set_child(cx_ret)
        opcoes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                         margin_top=4, margin_bottom=4, margin_start=4, margin_end=4)
        self.b_retencao = {}
        gr = None
        for cod, nome in RETENCOES:
            b = Gtk.ToggleButton(label=nome)
            b.add_css_class("flat")
            if gr:
                b.set_group(gr)
            gr = gr or b
            b.connect("clicked", self._retencao_escolhida, cod)
            self.b_retencao[cod] = b
            opcoes.append(b)
        self.b_retencao[self.hist.retencao].set_active(True)
        self.mb_retencao.set_popover(Gtk.Popover(child=opcoes))
        topo.append(self.mb_retencao)

        self.aviso_anon = Gtk.Box(spacing=6)
        self.aviso_anon.add_css_class("aviso-anon")
        self.aviso_anon.append(Icone("anonimo", 15))
        lb_an = Gtk.Label(label="Modo anônimo ativo:\nnão salva nem registra.", xalign=0, wrap=True)
        self.aviso_anon.append(lb_an)
        self.aviso_anon.set_visible(self.hist.anonimo)
        topo.append(self.aviso_anon)
        painel.append(topo)

        self.pilha_hist = Gtk.Stack(vexpand=True)
        vz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                     halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                     margin_start=16, margin_end=16)
        lb_vz = Gtk.Label(label="Nenhuma captura ou gravação no histórico.\nOs próximos registros aparecerão aqui.",
                          justify=Gtk.Justification.CENTER, wrap=True)
        lb_vz.add_css_class("mudo")
        vz.append(lb_vz)
        self.pilha_hist.add_named(vz, "vazio")

        rolagem = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        self.lista_hist = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                  margin_top=10, margin_bottom=12, margin_start=10, margin_end=10)
        rolagem.set_child(self.lista_hist)
        self.pilha_hist.add_named(rolagem, "lista")
        painel.append(self.pilha_hist)
        return painel

    def _alternar_historico(self, b):
        if self._sinc_hist:
            return
        ativo = b.get_active()
        if ativo:
            self._atualiza_historico()
        self._sinc_hist = True
        self.divisao.set_show_sidebar(ativo)
        self._sinc_hist = False

    def _painel_mudou(self, *_):
        if self._sinc_hist:
            return
        aberto = self.divisao.get_show_sidebar()
        if aberto:
            self._atualiza_historico()
        self._sinc_hist = True
        self.b_historico.set_active(aberto)
        self._sinc_hist = False

    def _foco_janela(self, *_):
        if self.is_active() and self.divisao.get_show_sidebar():
            atuais = [w["item"]["id"] for w in self.itens_hist]
            novos = [it["id"] for it in self.hist.listar()]
            if atuais != novos:
                self._atualiza_historico()

    def _anonimo_trocado(self, b):
        if self._sinc_anon:
            return
        ativo = b.get_active()
        self.hist.definir_anonimo(ativo)
        self.aviso_anon.set_visible(ativo)
        self._status("Modo anônimo ativado: capturas não serão salvas nem entrarão no histórico"
                     if ativo else "Modo anônimo desativado")

    def _retencao_escolhida(self, b, cod):
        self.hist.definir_retencao(cod)
        self.lb_retencao.set_label(dict(RETENCOES)[cod])
        b.set_active(True)
        self.mb_retencao.popdown()
        self._atualiza_historico()

    def _limpar_historico(self):
        self.hist.limpar()
        self._atualiza_historico()
        self._status("Lista do histórico limpa  ·  Os arquivos salvos foram mantidos")

    def _atualiza_historico(self):
        filho = self.lista_hist.get_first_child()
        while filho is not None:
            prox = filho.get_next_sibling()
            self.lista_hist.remove(filho)
            filho = prox
        self.itens_hist = []
        itens = self.hist.listar()
        self.b_limpar_hist.set_sensitive(bool(itens))
        if not itens:
            self.pilha_hist.set_visible_child_name("vazio")
            return
        for it in itens:
            info = self._cria_item_historico(it)
            self.itens_hist.append(info)
            self.lista_hist.append(info["caixa"])
        self.pilha_hist.set_visible_child_name("lista")

    @staticmethod
    def _eh_gravacao(it):
        tipo = (it.get("tipo") or os.path.splitext(it.get("caminho", ""))[1].lstrip(".")).lower()
        return tipo in ("mp4", "gif"), (tipo or "png")

    def _cria_item_historico(self, it):
        eh_grav, tipo = self._eh_gravacao(it)
        dica_abrir = "Abrir gravação" if eh_grav else "Abrir numa aba nova"
        cartao = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        cartao.add_css_class("item-hist")
        cartao.set_tooltip_text(pasta_para_exibir(it["caminho"]))

        b_principal = Gtk.Button()
        b_principal.add_css_class("abrir-item")
        b_principal.set_tooltip_text(dica_abrir)
        b_principal.connect("clicked", lambda _b, item=it: self._hist_abrir(item))

        linha = Gtk.Box(spacing=8)
        quadro = Gtk.Box(valign=Gtk.Align.CENTER)
        quadro.add_css_class("mini-quadro")
        quadro.set_overflow(Gtk.Overflow.HIDDEN)
        quadro.set_size_request(72, 48)
        ic_padrao = "video" if eh_grav else "imagem"
        mini = self.hist.caminho_miniatura(it)
        if mini:
            try:
                pic = Gtk.Picture.new_for_paintable(Gdk.Texture.new_from_filename(mini))
                pic.set_content_fit(Gtk.ContentFit.COVER)
                pic.set_can_shrink(True)
                pic.set_hexpand(True)
                pic.set_vexpand(True)
                quadro.append(pic)
            except Exception:
                quadro.append(Icone(ic_padrao, 20))
        else:
            quadro.append(Icone(ic_padrao, 20))
        linha.append(quadro)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                         valign=Gtk.Align.CENTER, hexpand=True)
        lb_data = Gtk.Label(label=rotulo_data(it.get("criado_em")), xalign=0)
        lb_data.add_css_class("data-hist")
        textos.append(lb_data)
        w, h = it.get("largura", 0), it.get("altura", 0)
        if eh_grav:
            partes_sub = [tipo.upper()]
            if it.get("duracao") is not None:
                partes_sub.append(formatar_duracao(max(1, round(it["duracao"]))))
            if w and h:
                partes_sub.append("%d × %d" % (w, h))
            sub = " · ".join(partes_sub)
        else:
            sub = "%d × %d px" % (w, h) if w and h else os.path.basename(it["caminho"])
        lb_sub = Gtk.Label(label=sub, xalign=0)
        lb_sub.add_css_class("mudo")
        lb_sub.add_css_class("sub-hist")
        textos.append(lb_sub)
        linha.append(textos)
        b_principal.set_child(linha)
        cartao.append(b_principal)

        acoes = Gtk.Box(spacing=2)
        acoes.add_css_class("acoes-hist")
        b_abrir = botao("video" if eh_grav else "abrir", dica_abrir)
        b_abrir.connect("clicked", lambda _b, item=it: self._hist_abrir(item))
        b_copiar = botao("copiar", "Copiar arquivo" if eh_grav else "Copiar imagem")
        b_copiar.connect("clicked", lambda _b, item=it: self._hist_copiar(item))
        b_pasta = botao("pasta", "Abrir a pasta do arquivo")
        b_pasta.connect("clicked", lambda _b, item=it: self._hist_pasta(item))
        esp = Gtk.Box(hexpand=True)
        b_rem = botao("x", "Remover da lista (mantém o arquivo)")
        b_rem.connect("clicked", lambda _b, item=it: self._hist_remover(item))
        for wdg in (b_abrir, b_copiar, b_pasta, esp, b_rem):
            acoes.append(wdg)
        cartao.append(acoes)
        return {"item": it, "caixa": cartao, "abrir": b_abrir, "copiar": b_copiar,
                "pasta": b_pasta, "remover": b_rem}

    def _confere_item_hist(self, it):
        if os.path.isfile(it["caminho"]):
            return True
        self._atualiza_historico()
        self._status("O arquivo não existe mais e saiu da lista")
        return False

    def _hist_abrir(self, it):
        if not self._confere_item_hist(it):
            return
        eh_grav, _ = self._eh_gravacao(it)
        if not eh_grav:
            self.abrir_arquivo(it["caminho"])
            return
        arq = Gio.File.new_for_path(it["caminho"])
        lan = Gtk.FileLauncher.new(arq)

        def pronto(obj, res):
            try:
                obj.launch_finish(res)
            except Exception:
                try:
                    Gio.AppInfo.launch_default_for_uri(arq.get_uri(), None)
                except Exception:
                    self._status("Arquivo salvo em " + pasta_para_exibir(it["caminho"]))

        lan.launch(self, None, pronto)

    def _copia_uri_arquivo(self, caminho):
        uri = (Gio.File.new_for_path(caminho).get_uri() + "\r\n").encode("utf-8")
        ok = False
        try:
            if shutil.which("xclip") is None and x11.tem_xlib() and area.copiar(uri, tipo="text/uri-list"):
                ok = True
            elif shutil.which("xclip"):
                p = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-i"],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                p.stdin.write(uri)
                p.stdin.close()
                ok = p.wait(timeout=5) == 0
            else:
                prov = Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(uri))
                self.get_clipboard().set_content(prov)
                ok = True
        except Exception as e:
            print("falha ao copiar arquivo:", e, file=sys.stderr)
        self._status("Arquivo copiado para a área de transferência" if ok else "Não foi possível copiar")
        return ok

    def _hist_copiar(self, it):
        if not self._confere_item_hist(it):
            return
        eh_grav, _ = self._eh_gravacao(it)
        if eh_grav:
            self._copia_uri_arquivo(it["caminho"])
            return
        try:
            with open(it["caminho"], "rb") as f:
                dados = f.read()
        except OSError:
            self._atualiza_historico()
            self._status("Não foi possível ler o arquivo")
            return
        self._copia_png_bytes(dados, quieto=False)

    def _hist_pasta(self, it):
        if not self._confere_item_hist(it):
            return
        arq = Gio.File.new_for_path(it["caminho"])
        lan = Gtk.FileLauncher.new(arq)

        def pronto(obj, res):
            try:
                obj.open_containing_folder_finish(res)
            except Exception:
                try:
                    pasta = Gio.File.new_for_path(os.path.dirname(it["caminho"])).get_uri()
                    Gio.AppInfo.launch_default_for_uri(pasta, None)
                except Exception:
                    self._status("Pasta: " + pasta_para_exibir(os.path.dirname(it["caminho"])))

        lan.open_containing_folder(self, None, pronto)

    def _hist_remover(self, it):
        self.hist.remover(it["id"])
        self._atualiza_historico()

    def _aba_trocada(self, *_):
        pag = self.abas.get_selected_page()
        self.editor = pag.get_child() if pag else self._sem_aba
        self.editor.ferr = self.ferr
        self._cursor()
        self.ic_cor.queue_draw()
        self._status()

    def _abas_mudaram(self, *_):
        n = self.abas.get_n_pages()
        self.b_pdf.set_visible(n >= 2)
        self.barra_abas.set_visible(n > 0)
        if n == 0:
            self.editor = self._sem_aba
            self.pilha.set_visible_child_name("vazio")
            self.dock.set_visible(False)
            self.chip.set_visible(False)
            self.b_copiar.set_sensitive(False)
            self.b_salvar.set_sensitive(False)

    def _titulo_aba(self, ed):
        pag = self.abas.get_page(ed)
        pag.set_title(ed.titulo + (" •" if ed.alterado else ""))

    def _fechar_aba(self, view, pag):
        ed = pag.get_child()
        if not ed.alterado:
            view.close_page_finish(pag, True)
            return True
        dlg = Adw.MessageDialog(transient_for=self, heading="Fechar sem salvar?",
                                body="As alterações em “%s” ainda não foram salvas." % ed.titulo)
        dlg.add_response("cancelar", "Cancelar")
        dlg.add_response("fechar", "Fechar sem salvar")
        dlg.set_response_appearance("fechar", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancelar")
        dlg.set_close_response("cancelar")
        respondeu = []

        def resposta(_d, r):
            if not respondeu:  # uma resposta por pedido de fechamento
                respondeu.append(r)
                view.close_page_finish(pag, r == "fechar")

        dlg.connect("response", resposta)
        dlg.present()
        return True

    def _status(self, *partes):
        """Atualiza o chip de tamanho e, se houver mensagens, mostra um aviso passageiro."""
        img = self.editor.base
        if img:
            self.chip.set_label("%d × %d px" % (img.get_width(), img.get_height()))
        if partes:
            t = Adw.Toast(title="  ·  ".join(partes), timeout=3)
            t.set_use_markup(False)
            t.connect("dismissed", self._aviso_fechado)
            self.n_avisos += 1
            self.toasts.set_can_target(True)
            self.toasts.add_toast(t)

    def _aviso_fechado(self, _toast):
        self.n_avisos = max(0, self.n_avisos - 1)
        if not self.n_avisos:
            self.toasts.set_can_target(False)

    def _mudou(self):
        if self.editor is not self._sem_aba and self.abas.get_n_pages():
            self._titulo_aba(self.editor)
        self._status()

    def _salva_auto(self):
        try:
            arq = nome_captura(pasta_capturas())
            self.editor.exportar().write_to_png(arq)
            return arq
        except Exception as e:
            print("falha ao salvar:", e, file=sys.stderr)
            return None

    def _copia_png_bytes(self, dados, quieto=False):
        ok = False
        try:
            if shutil.which("xclip") is None and x11.tem_xlib() and area.copiar(dados):
                ok = True  # sem xclip (Flatpak): processo proprio serve a selecao
            elif shutil.which("xclip"):
                # xclip fica em segundo plano servindo a selecao; nao esperamos por ele
                p = subprocess.Popen(["xclip", "-selection", "clipboard", "-t", "image/png", "-i"],
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                p.stdin.write(dados)
                p.stdin.close()
                ok = p.wait(timeout=5) == 0
            else:
                prov = Gdk.ContentProvider.new_for_bytes("image/png", GLib.Bytes.new(dados))
                self.get_clipboard().set_content(prov)
                ok = True
        except Exception as e:
            print("falha ao copiar:", e, file=sys.stderr)
        if not quieto:
            self._status("Copiado para a área de transferência" if ok else "Não foi possível copiar")
        return ok

    def copiar(self, quieto=False):
        if not self.editor.base:
            return False
        try:
            dados = io.BytesIO()
            self.editor.exportar().write_to_png(dados)
            return self._copia_png_bytes(dados.getvalue(), quieto=quieto)
        except Exception as e:
            print("falha ao copiar:", e, file=sys.stderr)
            if not quieto:
                self._status("Não foi possível copiar")
            return False

    def _grava(self, arq, ed=None):
        ed = ed or self.editor
        try:
            exportar.salvar(ed.exportar(), arq)
            ed.alterado = False
            if self.abas.get_n_pages():
                self._titulo_aba(ed)
            self._status("Salvo em " + pasta_para_exibir(arq))
        except Exception as e:
            self._status("Não foi possível salvar: %s" % e)

    def salvar_como(self):
        if not self.editor.base:
            return
        direto = os.environ.get("CAPTURE_TEST_SALVAR")  # gancho dos testes e2e: sem dialogo
        if direto:
            self._grava(direto)
            return
        pasta = pasta_capturas()
        ed = self.editor
        dlg = self._dialogo_salvar("Salvar captura: PNG, JPG ou PDF, conforme a extensão",
                                   os.path.basename(nome_captura(pasta)), pasta,
                                   (("Imagem PNG", "*.png"), ("Imagem JPEG", "*.jpg *.jpeg"),
                                    ("Documento PDF", "*.pdf")))

        def feito(d, res):
            try:
                arq = d.save_finish(res).get_path()
            except GLib.Error:
                return
            if not exportar.formato(arq):
                arq = nome_livre(exportar.com_extensao(arq))  # o dialogo confirmou "arq", nao "arq.png"
            self._grava(arq, ed)

        dlg.save(self, None, feito)

    def _dialogo_salvar(self, titulo, nome, pasta, filtros):
        dlg = Gtk.FileDialog(title=titulo, initial_name=nome)
        lista = Gio.ListStore.new(Gtk.FileFilter)
        for rot, padroes in filtros:
            f = Gtk.FileFilter(name=rot)
            for pd in padroes.split():
                f.add_pattern(pd)
                f.add_pattern(pd.upper())
            lista.append(f)
        dlg.set_filters(lista)
        try:
            os.makedirs(pasta, exist_ok=True)
            dlg.set_initial_folder(Gio.File.new_for_path(pasta))
        except Exception:
            pass
        return dlg

    def juntar_pdf(self):
        """Grava um PDF com uma pagina por aba, na ordem das abas."""
        n = self.abas.get_n_pages()
        if not n:
            return
        imagens = [self.abas.get_nth_page(i).get_child().exportar() for i in range(n)]

        def grava(arq):
            try:
                exportar.pdf(imagens, arq)
                self._status("PDF com %d páginas salvo em %s" % (n, pasta_para_exibir(arq)))
            except Exception as e:
                self._status("Não foi possível salvar o PDF: %s" % e)

        direto = os.environ.get("CAPTURE_TEST_PDF")  # gancho dos testes e2e: sem dialogo
        if direto:
            grava(direto)
            return
        pasta = pasta_capturas()
        nome = "Capturas %s.pdf" % datetime.datetime.now().strftime("%Y-%m-%d %H%M%S")
        dlg = self._dialogo_salvar("Juntar abas em PDF", nome, pasta, (("Documento PDF", "*.pdf"),))

        def feito(d, res):
            try:
                arq = d.save_finish(res).get_path()
            except GLib.Error:
                return
            if not arq.lower().endswith(".pdf"):
                arq = nome_livre(arq + ".pdf")
            grava(arq)

        dlg.save(self, None, feito)

    def pede_tamanho(self):
        """Dialogo de redimensionar: largura e altura em px, com proporcao travada."""
        img = self.editor.base
        if not img:
            return
        ed = self.editor
        w0, h0 = img.get_width(), img.get_height()
        dlg = Adw.MessageDialog(transient_for=self, heading="Redimensionar",
                                body="Tamanho atual: %d × %d px" % (w0, h0))
        grade = Gtk.Grid(column_spacing=10, row_spacing=10, halign=Gtk.Align.CENTER)
        sw = Gtk.SpinButton.new_with_range(1, 20000, 1)
        sh = Gtk.SpinButton.new_with_range(1, 20000, 1)
        sw.set_value(w0)
        sh.set_value(h0)
        trava = Gtk.CheckButton(label="Manter a proporção", active=True)
        grade.attach(Gtk.Label(label="Largura", xalign=0), 0, 0, 1, 1)
        grade.attach(sw, 1, 0, 1, 1)
        grade.attach(Gtk.Label(label="Altura", xalign=0), 0, 1, 1, 1)
        grade.attach(sh, 1, 1, 1, 1)
        grade.attach(trava, 0, 2, 2, 1)
        atalhos = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER)
        ocupado = [False]

        def muda(origem):
            if ocupado[0] or not trava.get_active():
                return
            ocupado[0] = True
            if origem is sw:
                sh.set_value(proporcional(w0, h0, w=sw.get_value())[1])
            else:
                sw.set_value(proporcional(w0, h0, h=sh.get_value())[0])
            ocupado[0] = False

        sw.connect("value-changed", muda)
        sh.connect("value-changed", muda)
        for pct in (25, 50, 75):
            b = Gtk.Button(label="%d%%" % pct)
            b.connect("clicked", lambda _b, p=pct: (trava.set_active(True), sw.set_value(round(w0 * p / 100))))
            atalhos.append(b)
        grade.attach(atalhos, 0, 3, 2, 1)
        dlg.set_extra_child(grade)
        dlg.add_response("cancelar", "Cancelar")
        dlg.add_response("aplicar", "Redimensionar")
        dlg.set_response_appearance("aplicar", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("aplicar")
        dlg.set_close_response("cancelar")

        def resposta(_d, r):
            if r == "aplicar" and ed.redimensiona(sw.get_value_as_int(), sh.get_value_as_int()):
                self._status("Redimensionado para %d × %d px" % (ed.base.get_width(), ed.base.get_height()))

        dlg.connect("response", resposta)
        dlg.present()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=os.environ.get("CAPTURE_APP_ID") or APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.jan = None
        self.add_main_option("novo", ord("n"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Inicia uma captura imediatamente", None)
        self.add_main_option("gravar", ord("g"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Inicia (ou encerra) uma gravação de tela", None)
        self.add_main_option("formato", ord("f"), GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "Formato da gravação: mp4 ou gif", "FORMATO")
        self.add_main_option("modo", ord("m"), GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "ret, janela, tela, livre ou rolavel", "MODO")
        self.add_main_option("abrir", ord("a"), GLib.OptionFlags.NONE, GLib.OptionArg.FILENAME,
                             "Abre um PNG no editor", "ARQUIVO")

    def do_startup(self):
        Adw.Application.do_startup(self)
        escolha = os.environ.get("CAPTURE_TEMA", "").strip().lower()
        if escolha in ("escuro", "dark"):
            escuro = True
        elif escolha in ("claro", "clean", "light"):
            escuro = False
        else:  # sistema
            escuro = tema_escuro()
        if escuro is None:  # sem o esquema do Cinnamon (ex.: Flatpak): usa o tema GTK do portal
            escuro = tema_escuro_do_portal()
        if escuro is None:  # nem isso: segue o padrao do sistema
            escuro = Adw.StyleManager.get_default().get_dark()
        else:
            Adw.StyleManager.get_default().set_color_scheme(
                Adw.ColorScheme.FORCE_DARK if escuro else Adw.ColorScheme.FORCE_LIGHT)
        css = Gtk.CssProvider()
        css.load_from_string(tokens_css(ESCURO if escuro else CLARO) + CSS_BASE)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.Window.set_default_icon_name(ICONE)

    def do_activate(self):
        if not self.jan:
            self.jan = Janela(self)
        self.jan.present()

    def do_command_line(self, cl):
        op = cl.get_options_dict().end().unpack()
        if not self.jan:
            self.jan = Janela(self)
        if "formato" in op:
            self.jan._define_formato_gravacao(op["formato"])
        if "abrir" in op:
            # relativo ao diretorio de quem chamou, nao ao da instancia ja aberta
            arq = cl.create_file_for_arg(decodifica_caminho(op["abrir"]))
            self.jan.abrir_arquivo(arq.get_path())
        elif "gravar" in op:
            self.jan.nova_gravacao(op.get("modo"), formato=op.get("formato"), atraso=0)
        elif "novo" in op or "modo" in op:
            self.jan.nova_captura(op.get("modo"), atraso=0 if "novo" in op else None)
        else:
            self.jan.present()
        return 0


def principal(argv=None):
    GLib.set_prgname(PRGNAME)
    GLib.set_application_name(NOME)
    return sys.exit(App().run(argv if argv is not None else sys.argv))
