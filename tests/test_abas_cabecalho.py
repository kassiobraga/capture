"""Testes unitarios para abas (Adw.TabBar) e cabecalho (HeaderBar)."""
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.app import CSS_BASE, Janela  # noqa: E402
from capture.tema import CLARO, ESCURO, tokens_css  # noqa: E402


class AbasCabecalhoTeste(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        with open(os.path.join(raiz, "capture", "app.py"), encoding="utf-8") as f:
            cls.codigo_app = f.read()

    def test_expand_tabs_desligado_na_criacao(self):
        # Verifica se Adw.TabBar e instanciado com expand_tabs=False
        padrao = r"Adw\.TabBar\([^)]*expand_tabs=False[^)]*\)"
        self.assertRegex(self.codigo_app, padrao)

    def test_cabecalho_altura_e_margem_capturar_css(self):
        # Botao capturar com min-height de 32px e margens verticais de 8px (sem height)
        self.assertIn("button.capturar", CSS_BASE)
        # Verifica min-height de 32px e margem de 8px
        bloco_capturar = re.search(r"button\.capturar\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_capturar)
        estilo = bloco_capturar.group(1)
        self.assertIn("min-height: 32px", estilo)
        self.assertIsNone(re.search(r"(?<![-\w])height\s*:", estilo))
        self.assertIn("margin-top: 8px", estilo)
        self.assertIn("margin-bottom: 8px", estilo)

    def test_cabecalho_altura_e_margem_discreto_css(self):
        # Botoes discretos do cabecalho com min-height de 32px e margens de 8px (sem height)
        bloco_discreto = re.search(r"headerbar button\.discreto\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_discreto)
        estilo = bloco_discreto.group(1)
        self.assertIn("min-height: 32px", estilo)
        self.assertIsNone(re.search(r"(?<![-\w])height\s*:", estilo))
        self.assertIn("margin-top: 8px", estilo)
        self.assertIn("margin-bottom: 8px", estilo)

    def test_cabecalho_modos_e_atraso_css(self):
        # Grupo de modos e atraso com min-height de 32px e margens verticais de 8px
        bloco_modos = re.search(r"\.modos button\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_modos)
        estilo_modos = bloco_modos.group(1)
        self.assertIn("min-height: 32px", estilo_modos)
        self.assertIsNone(re.search(r"(?<![-\w])height\s*:", estilo_modos))
        self.assertIn("margin-top: 8px", estilo_modos)
        self.assertIn("margin-bottom: 8px", estilo_modos)

        bloco_atraso = re.search(r"(?:^|\n)\.atraso > button\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_atraso)
        estilo_atraso = bloco_atraso.group(1)
        self.assertIn("min-height: 32px", estilo_atraso)
        self.assertIsNone(re.search(r"(?<![-\w])height\s*:", estilo_atraso))
        self.assertIn("margin-top: 8px", estilo_atraso)
        self.assertIn("margin-bottom: 8px", estilo_atraso)

    def test_cabecalho_valign_botoes_no_codigo(self):
        # Verifica se os botoes principais e containers do cabecalho recebem valign center
        self.assertIn("self.b_capturar.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.b_historico.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.b_anonimo.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.b_salvar.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.b_copiar.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.b_pdf.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("self.mb_atraso.set_valign(Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("centro = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)", self.codigo_app)
        self.assertIn("modos = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)", self.codigo_app)

    def test_abas_dimensoes_e_respiro_css(self):
        # Cada aba com min-width 110px, min-height 32px, margens verticais 4px e laterais 1px
        bloco_tab = re.search(r"tabbar tab\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_tab)
        estilo_tab = bloco_tab.group(1)

        self.assertNotIn("max-width", estilo_tab)
        self.assertIsNone(re.search(r"(?<![-\w])height\s*:", estilo_tab))
        self.assertIn("min-width: 110px", estilo_tab)
        self.assertIn("min-height: 32px", estilo_tab)
        self.assertIn("margin-top: 4px", estilo_tab)
        self.assertIn("margin-bottom: 4px", estilo_tab)
        self.assertIn("border-radius: 8px", estilo_tab)
        self.assertIn("background: none", estilo_tab)

        # Espaco entre abas: margin-left e margin-right de 1px cada
        self.assertIn("margin-left: 1px", estilo_tab)
        self.assertIn("margin-right: 1px", estilo_tab)
        self.assertNotIn("margin-start", estilo_tab)
        self.assertNotIn("margin-end", estilo_tab)

    def test_abas_titulo_sem_text_overflow_invalido_css(self):
        # GTK 4 nao reconhece text-overflow no CSS; Adw.TabBar ja abrevia nativo
        self.assertNotIn("text-overflow", CSS_BASE)

    def test_abas_destaque_selecionada_e_hover_css(self):
        # Aba selecionada com destaque suave e hover nas abas
        self.assertIn("tabbar tab:selected", CSS_BASE)
        self.assertIn("alpha(@cap_accent, 0.14)", CSS_BASE)

        bloco_hover = re.search(r"tabbar tab:hover\s*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_hover)
        self.assertIn("alpha(@cap_text,", bloco_hover.group(1))

    def test_abas_botao_fechar_discreto_css(self):
        # Botao de fechar pequeno e discreto
        bloco_btn = re.search(r"tabbar tab button.*\{([^}]+)\}", CSS_BASE)
        self.assertIsNotNone(bloco_btn)
        estilo_btn = bloco_btn.group(1)
        self.assertIn("min-width: 20px", estilo_btn)
        self.assertIn("min-height: 20px", estilo_btn)
        self.assertIn("border-radius: 6px", estilo_btn)
        self.assertIn("background: none", estilo_btn)

    def test_titulo_aba_com_alteracoes_mantem_marcador(self):
        # Mantem o marcador no titulo quando ha alteracoes nao salvas
        ed = MagicMock()
        ed.titulo = "Captura 1"
        ed.alterado = True
        jan = MagicMock()
        jan.abas = MagicMock()
        pag = MagicMock()
        jan.abas.get_page.return_value = pag

        Janela._titulo_aba(jan, ed)
        pag.set_title.assert_called_once_with("Captura 1 \u2022")

        ed.alterado = False
        pag.reset_mock()
        Janela._titulo_aba(jan, ed)
        pag.set_title.assert_called_once_with("Captura 1")

    def test_css_valido_sem_erros_de_parse_gtk(self):
        # Valida que o CSS carrega sem erros no Gtk.CssProvider para ambos os temas
        display_ok = True
        try:
            if hasattr(Gtk, "is_initialized") and Gtk.is_initialized():
                display_ok = True
            else:
                display_ok = Gtk.init_check()
        except Exception:
            display_ok = False

        if display_ok:
            try:
                Adw.init()
            except Exception:
                pass

        for tema, nome in ((ESCURO, "escuro"), (CLARO, "claro")):
            try:
                provider = Gtk.CssProvider()
            except Exception as e:
                self.skipTest("sem display para Gtk.CssProvider: %s" % e)

            erros = []

            def on_parsing_error(prov, section, error, *extra):
                msg = error.message if hasattr(error, "message") else str(error)
                sec_str = section.to_string() if (section and hasattr(section, "to_string")) else str(section)
                erros.append("%s: %s" % (sec_str, msg))

            provider.connect("parsing-error", on_parsing_error)
            css = tokens_css(tema) + CSS_BASE
            try:
                provider.load_from_string(css)
            except Exception as e:
                if not display_ok:
                    self.skipTest("sem display para carregar CSS: %s" % e)
                raise
            self.assertEqual(erros, [], "Erros de parse no CSS do tema %s: %s" % (nome, erros))


if __name__ == "__main__":
    unittest.main()
