"""Janela principal e aplicacao."""
import io
import os
import shutil
import subprocess
import sys

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, ATRASOS, CORES, ICONE, MODOS, NOME, PRGNAME
from .arquivos import nome_captura, nome_livre, pasta_capturas, pasta_para_exibir
from .editor import Editor
from .icons import Icone, botao
from .overlay import Sessao
from . import teste
from .tema import CLARO, ESCURO, tokens_css

# Identidade: azul-marinho profundo, um unico acento verde-agua e paineis de "vidro"
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

.vidro { background: alpha(@cap_raised, 0.78); border: 1px solid @cap_edge; border-radius: 16px;
         box-shadow: 0 10px 30px alpha(black, 0.35); }
.dock, .pill { padding: 6px 8px; }
.dock button, .dock menubutton > button, .pill button, .modos button, .atraso > button {
        min-width: 34px; min-height: 34px; padding: 0; border-radius: 10px;
        background: none; box-shadow: none; border: none; color: @cap_text; }
.dock button:hover, .dock menubutton > button:hover, .pill button:hover, .modos button:hover,
.atraso > button:hover { background: alpha(@cap_text, 0.08); }
.dock button:checked, .dock menubutton.on > button, .pill button:checked, .modos button:checked {
        background: alpha(@cap_accent, 0.18); color: @cap_accent; }
.dock separator { background: @cap_edge; min-width: 1px; margin: 6px 4px; }
.chip { padding: 5px 12px; border-radius: 14px; font-size: 0.86em; margin: 0 0 18px 18px; }
.dica { padding: 7px 16px; border-radius: 14px; font-size: 0.92em; }

.modos { background: alpha(@cap_text, 0.06); border-radius: 12px; padding: 3px; }
.modos button { min-width: 38px; min-height: 28px; }
.atraso > button { min-width: 0; padding: 0 10px; min-height: 30px; background: alpha(@cap_text, 0.06); }
.atraso label { font-weight: 600; font-size: 0.92em; }
button.capturar { background: @cap_accent; color: @cap_accent_fg; border-radius: 10px; font-weight: 700;
                  min-height: 32px; padding: 0 14px; box-shadow: none; border: none; }
button.capturar:hover { background: shade(@cap_accent, 1.08); }
headerbar button.discreto { min-width: 34px; min-height: 32px; padding: 0; border-radius: 10px; background: none;
                            box-shadow: none; color: @cap_text; }
headerbar button.discreto:hover { background: alpha(@cap_text, 0.08); }
headerbar button.discreto:disabled { opacity: 0.35; }

.cartao { background: alpha(@cap_raised, 0.78); border: 1px solid @cap_edge; border-radius: 16px;
          padding: 18px 22px; min-width: 110px; box-shadow: 0 10px 30px alpha(black, 0.25); color: @cap_text; }
.cartao:hover { border-color: alpha(@cap_accent, 0.7); color: @cap_accent; }
.cartao label { font-weight: 600; }
.amostra { min-width: 26px; min-height: 26px; padding: 0; border-radius: 13px; }
.sobre { background: @cap_canvas; }
"""


ATALHOS_FERRAMENTAS = {Gdk.KEY_p: "caneta", Gdk.KEY_h: "marca", Gdk.KEY_e: "borracha", Gdk.KEY_r: "f_ret",
                       Gdk.KEY_o: "f_elipse", Gdk.KEY_l: "f_linha", Gdk.KEY_a: "f_seta", Gdk.KEY_t: "texto",
                       Gdk.KEY_x: "cortar"}


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


def decodifica_caminho(v):
    """Valor de uma opcao FILENAME (bytestring, lista de bytes ou str) -> str."""
    if isinstance(v, (list, tuple)):
        v = bytes(v)
    if isinstance(v, bytes):
        v = os.fsdecode(v.rstrip(b"\0"))
    return v


class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=NOME, default_width=760, default_height=560)
        self.sessao = None
        self.salvo_em = None
        self.modo = MODOS[0][0]
        self.atraso = ATRASOS[0][0]
        self.editor = Editor(self._mudou)
        self.editor.add_css_class("tela")

        # ---- cabecalho: titulo | modos + atraso | copiar, salvar, capturar
        cab = Adw.HeaderBar()
        t = Gtk.Label(label=NOME)
        t.add_css_class("titulo-app")
        cab.pack_start(t)

        centro = Gtk.Box(spacing=10)
        modos = Gtk.Box(spacing=2)
        modos.add_css_class("modos")
        self.b_modo = {}
        grupo = None
        for cod, nome in MODOS:
            b = botao(cod, nome, alternar=True, plano=False)
            if grupo:
                b.set_group(grupo)
            grupo = grupo or b
            b.connect("toggled", self._modo_escolhido, cod)
            self.b_modo[cod] = b
            modos.append(b)
        self.b_modo[self.modo].set_active(True)
        centro.append(modos)

        self.lb_atraso = Gtk.Label(label="0s")
        cx = Gtk.Box(spacing=6)
        cx.append(Icone("relogio"))
        cx.append(self.lb_atraso)
        self.mb_atraso = Gtk.MenuButton(tooltip_text="Atraso antes de capturar")
        self.mb_atraso.add_css_class("atraso")
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
        self.b_capturar.connect("clicked", lambda *_: self.nova_captura())
        cab.pack_end(self.b_capturar)
        self.b_salvar = botao("salvar", "Salvar como (Ctrl+S)")
        self.b_salvar.add_css_class("discreto")
        self.b_salvar.connect("clicked", lambda *_: self.salvar_como())
        cab.pack_end(self.b_salvar)
        self.b_copiar = botao("copiar", "Copiar (Ctrl+C)")
        self.b_copiar.add_css_class("discreto")
        self.b_copiar.connect("clicked", lambda *_: self.copiar())
        cab.pack_end(self.b_copiar)
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
        self.dock.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self.ic_cor = Icone("cor", 18, self.editor.cor)
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
        self.b_desf.connect("clicked", lambda *_: self.editor.desfazer())
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
        aj = Gtk.Label(label="Pressione Print para capturar, ou escolha um modo.\n"
                             "A captura é copiada e salva automaticamente.", justify=Gtk.Justification.CENTER)
        aj.add_css_class("mudo")
        vazio.append(aj)
        cartoes = Gtk.Box(spacing=14, halign=Gtk.Align.CENTER, margin_top=12)
        self.cartoes = {}
        for cod, nome in MODOS:
            b = Gtk.Button()
            b.add_css_class("cartao")
            b.add_css_class("flat")
            cv = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
            cv.append(Icone(cod, 28))
            cv.append(Gtk.Label(label=nome))
            b.set_child(cv)
            b.set_tooltip_text("Capturar: " + nome)
            b.connect("clicked", lambda _b, c=cod: self.nova_captura(c))
            self.cartoes[cod] = b
            cartoes.append(b)
        vazio.append(cartoes)

        self.pilha = Gtk.Stack()
        self.pilha.add_named(vazio, "vazio")
        self.pilha.add_named(self.editor, "editor")
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

        tv = Adw.ToolbarView()
        tv.add_top_bar(cab)
        tv.set_content(ov)
        self.set_content(tv)
        self.ferrs["caneta"].set_active(True)

        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)
        teste.grava_geometria(self)

    # ---- modo e atraso
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

    # ---- ferramentas
    def _ferr(self, b, cod):
        if not b.get_active():
            return
        self.editor.ferr = cod
        if cod.startswith("f_"):
            self.mb_formas.add_css_class("on")
        else:
            self.mb_formas.remove_css_class("on")
        self.esc_esp.set_value(self.editor.esp.get(self.editor.grupo(), 4))
        self.ic_cor.queue_draw()
        self.editor.set_cursor(Gdk.Cursor.new_from_name("text" if cod == "texto" else "crosshair"))

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
        elif ctrl and t == Gdk.KEY_c and self.editor.base:
            self.copiar()
        elif ctrl and t == Gdk.KEY_s and self.editor.base:
            self.salvar_como()
        elif ctrl and (t == Gdk.KEY_y or (t == Gdk.KEY_z and shift)):
            self.editor.refazer()
        elif ctrl and t == Gdk.KEY_z:
            self.editor.desfazer()
        elif not ctrl and not (estado & Gdk.ModifierType.ALT_MASK) and t in ATALHOS_FERRAMENTAS:
            self.ferrs[ATALHOS_FERRAMENTAS[t]].set_active(True)
        else:
            return False
        return True

    # ---- captura
    def nova_captura(self, modo=None, atraso=None):
        if self.sessao:
            return
        if modo in dict(MODOS):
            self._define_modo(modo)
        modo = self.modo
        if atraso is None:
            atraso = self.atraso
        self._visivel = self.get_visible()
        self.set_visible(False)
        self.sessao = Sessao(self.get_application(), modo, atraso, self._capturou)

    def _capturou(self, img, erro=None):
        modo = self.sessao.modo if self.sessao else None
        self.sessao = None
        if modo in dict(MODOS):
            self._define_modo(modo)
        if erro:
            ficou = self._visivel or self.editor.base
            self.present()
            self.mostra_erro(erro, None if ficou else self.get_application().quit)
            return
        if img is None:
            if self._visivel or self.editor.base:
                self.present()
            else:
                self.get_application().quit()
            return
        self.abrir(img, novo=True)

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
        self.abrir(img)

    def _dimensiona(self, iw, ih):
        """Tamanho da janela para a imagem, limitado ao monitor."""
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
        w, h = int(min(max(iw + 60, 720), lim_w)), int(min(max(ih + 200, 480), lim_h))
        if self.get_mapped():
            # GTK 4 ignora set_default_size com a janela visivel: esconde e mostra de novo
            self.set_visible(False)
        self.set_default_size(w, h)

    def abrir(self, img, novo=False):
        self.editor.definir_imagem(img)
        self.pilha.set_visible_child_name("editor")
        self.dock.set_visible(True)
        self.chip.set_visible(True)
        self.b_copiar.set_sensitive(True)
        self.b_salvar.set_sensitive(True)
        self._dimensiona(img.get_width(), img.get_height())
        self.salvo_em = None
        partes = []
        if novo:
            if self.copiar(quieto=True):
                partes.append("Copiado para a área de transferência")
            self.salvo_em = self._salva_auto()
            if self.salvo_em:
                partes.append("Salvo em " + pasta_para_exibir(self.salvo_em))
        self._status(*partes)
        self.present()
        teste.grava_geometria(self)

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
        self._status()

    def _salva_auto(self):
        try:
            arq = nome_captura(pasta_capturas())
            self.editor.exportar().write_to_png(arq)
            return arq
        except Exception as e:
            print("falha ao salvar:", e, file=sys.stderr)
            return None

    def copiar(self, quieto=False):
        if not self.editor.base:
            return False
        ok = False
        try:
            dados = io.BytesIO()
            self.editor.exportar().write_to_png(dados)
            dados = dados.getvalue()
            if shutil.which("xclip"):
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

    def _grava(self, arq):
        try:
            self.editor.exportar().write_to_png(arq)
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
        dlg = Gtk.FileDialog(title="Salvar captura", initial_name=os.path.basename(nome_captura(pasta)))
        try:
            os.makedirs(pasta, exist_ok=True)
            dlg.set_initial_folder(Gio.File.new_for_path(pasta))
        except Exception:
            pass

        def feito(d, res):
            try:
                arq = d.save_finish(res).get_path()
            except GLib.Error:
                return
            if not arq.lower().endswith(".png"):
                arq = nome_livre(arq + ".png")  # o dialogo confirmou "arq", nao "arq.png"
            self._grava(arq)

        dlg.save(self, None, feito)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=os.environ.get("CAPTURE_APP_ID") or APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.jan = None
        self.add_main_option("novo", ord("n"), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Inicia uma captura imediatamente", None)
        self.add_main_option("modo", ord("m"), GLib.OptionFlags.NONE, GLib.OptionArg.STRING,
                             "ret, janela, tela ou livre", "MODO")
        self.add_main_option("abrir", ord("a"), GLib.OptionFlags.NONE, GLib.OptionArg.FILENAME,
                             "Abre um PNG no editor", "ARQUIVO")

    def do_startup(self):
        Adw.Application.do_startup(self)
        escuro = tema_escuro()
        if escuro is None:  # sem o esquema do Cinnamon: segue o padrao do sistema
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
        if "abrir" in op:
            # relativo ao diretorio de quem chamou, nao ao da instancia ja aberta
            arq = cl.create_file_for_arg(decodifica_caminho(op["abrir"]))
            self.jan.abrir_arquivo(arq.get_path())
        elif "novo" in op or "modo" in op:
            self.jan.nova_captura(op.get("modo"), atraso=0 if "novo" in op else None)
        else:
            self.jan.present()
        return 0


def principal(argv=None):
    GLib.set_prgname(PRGNAME)
    GLib.set_application_name(NOME)
    return sys.exit(App().run(argv if argv is not None else sys.argv))
