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

CSS_BASE = """
headerbar, .barra { background: @window_bg_color; box-shadow: none; }
.barra { padding: 4px 10px 8px 10px; }
button, menubutton > button, dropdown > button { border-radius: 5px; }
.status { padding: 5px 12px; font-size: 0.86em; opacity: 0.75; border-top: 1px solid alpha(currentColor, 0.12); }
.tela { background: alpha(currentColor, 0.06); }
.pill { background: @window_bg_color; color: @window_fg_color; border-radius: 9px; padding: 5px;
        border: 1px solid alpha(currentColor, 0.18); box-shadow: 0 8px 24px alpha(black, 0.45); }
.pill button { min-width: 34px; min-height: 30px; padding: 0; }
.pill button:checked, .barra togglebutton:checked, .barra menubutton.on > button {
        background: alpha(currentColor, 0.12); box-shadow: inset 0 -2px 0 @accent_bg_color; }
.sobre { background: black; }
.amostra { min-width: 26px; min-height: 26px; padding: 0; border-radius: 13px; }
"""
CSS_CLARO = """
@define-color accent_bg_color #0f6cbd; @define-color accent_color #0f6cbd; @define-color accent_fg_color #ffffff;
@define-color window_bg_color #f3f3f3; @define-color headerbar_bg_color #f3f3f3;
"""
CSS_ESCURO = """
@define-color accent_bg_color #60cdff; @define-color accent_color #60cdff; @define-color accent_fg_color #06202e;
@define-color window_bg_color #202020; @define-color headerbar_bg_color #202020;
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
        super().__init__(application=app, title=NOME, default_width=560, default_height=300)
        self.sessao = None
        self.salvo_em = None

        cab = Adw.HeaderBar(title_widget=Adw.WindowTitle(title=NOME))
        self.b_novo = botao("mais", "Nova captura (Ctrl+N)", "Novo", plano=False)
        self.b_novo.add_css_class("suggested-action")
        self.b_novo.connect("clicked", lambda *_: self.nova_captura())
        self.dd_modo = Gtk.DropDown.new_from_strings([n for _, n in MODOS])
        self.dd_modo.set_tooltip_text("Modo de captura")
        self.dd_atraso = Gtk.DropDown.new_from_strings([n for _, n in ATRASOS])
        self.dd_atraso.set_tooltip_text("Atraso antes de capturar")
        for w in (self.b_novo, self.dd_modo, self.dd_atraso):
            cab.pack_start(w)

        # barra de ferramentas do editor
        self.barra = Gtk.CenterBox()
        self.barra.add_css_class("barra")
        meio = Gtk.Box(spacing=2)
        self.editor = Editor(self._mudou)
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

        alterna("caneta", "caneta", "Caneta (P)", meio)
        alterna("marca", "marca", "Marca-texto (H)", meio)
        alterna("borracha", "borracha", "Borracha (E): apaga a marcação clicada", meio)
        self.mb_formas = Gtk.MenuButton(tooltip_text="Formas")
        self.mb_formas.set_child(Icone("formas"))
        self.mb_formas.add_css_class("flat")
        cx = Gtk.Box(spacing=2)
        for cod, dica in (("f_ret", "Retângulo (R)"), ("f_elipse", "Elipse (O)"), ("f_linha", "Linha (L)"), ("f_seta", "Seta (A)")):
            alterna(cod, cod, dica, cx).connect("clicked", lambda *_: self.mb_formas.popdown())
        self.mb_formas.set_popover(Gtk.Popover(child=cx))
        meio.append(self.mb_formas)
        alterna("texto", "texto", "Texto (T)", meio)
        alterna("cortar", "cortar", "Cortar a imagem (X)", meio)
        meio.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4, margin_end=4))

        self.ic_cor = Icone("cor", 18, self.editor.cor)
        self.mb_cor = Gtk.MenuButton(tooltip_text="Cor e espessura")
        self.mb_cor.set_child(self.ic_cor)
        self.mb_cor.add_css_class("flat")
        pc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin_top=6, margin_bottom=6,
                     margin_start=6, margin_end=6)
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
        meio.append(self.mb_cor)
        meio.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL, margin_start=4, margin_end=4))
        self.b_desf = botao("desfazer", "Desfazer (Ctrl+Z)")
        self.b_desf.connect("clicked", lambda *_: self.editor.desfazer())
        self.b_refz = botao("refazer", "Refazer (Ctrl+Y)")
        self.b_refz.connect("clicked", lambda *_: self.editor.refazer())
        meio.append(self.b_desf)
        meio.append(self.b_refz)
        fim = Gtk.Box(spacing=2)
        b = botao("copiar", "Copiar (Ctrl+C)")
        b.connect("clicked", lambda *_: self.copiar())
        fim.append(b)
        b = botao("salvar", "Salvar como (Ctrl+S)")
        b.connect("clicked", lambda *_: self.salvar_como())
        fim.append(b)
        self.barra.set_center_widget(meio)
        self.barra.set_end_widget(fim)

        vazio = Adw.StatusPage(icon_name=ICONE, title="Pressione Print para capturar",
                               description="Ou clique em Novo. A captura vai direto para a área de transferência.")
        self.editor.add_css_class("tela")
        self.pilha = Gtk.Stack()
        self.pilha.add_named(vazio, "vazio")
        self.pilha.add_named(self.editor, "editor")
        self.status = Gtk.Label(xalign=0)
        self.status.add_css_class("status")

        tv = Adw.ToolbarView()
        tv.add_top_bar(cab)
        tv.add_top_bar(self.barra)
        tv.add_bottom_bar(self.status)
        tv.set_content(self.pilha)
        self.set_content(tv)
        self.barra.set_visible(False)
        self.status.set_visible(False)
        self.ferrs["caneta"].set_active(True)

        tec = Gtk.EventControllerKey()
        tec.connect("key-pressed", self._tecla)
        self.add_controller(tec)

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
            self.dd_modo.set_selected([c for c, _ in MODOS].index(modo))
        modo = MODOS[self.dd_modo.get_selected()][0]
        if atraso is None:
            atraso = ATRASOS[self.dd_atraso.get_selected()][0]
        self._visivel = self.get_visible()
        self.set_visible(False)
        self.sessao = Sessao(self.get_application(), modo, atraso, self._capturou)

    def _capturou(self, img, erro=None):
        modo = self.sessao.modo if self.sessao else None
        self.sessao = None
        if modo in dict(MODOS):
            self.dd_modo.set_selected([c for c, _ in MODOS].index(modo))
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
        w, h = int(min(max(iw + 60, 720), lim_w)), int(min(max(ih + 170, 440), lim_h))
        if self.get_mapped():
            # GTK 4 ignora set_default_size com a janela visivel: esconde e mostra de novo
            self.set_visible(False)
        self.set_default_size(w, h)

    def abrir(self, img, novo=False):
        self.editor.definir_imagem(img)
        self.pilha.set_visible_child_name("editor")
        self.barra.set_visible(True)
        self.status.set_visible(True)
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
        img = self.editor.base
        tam = ["%d × %d px" % (img.get_width(), img.get_height())] if img else []
        self.status.set_label("     ".join(tam + list(partes)))

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
        css.load_from_string((CSS_ESCURO if escuro else CSS_CLARO) + CSS_BASE)
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
