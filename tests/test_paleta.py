import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.tema import CLARO, ESCURO, rgb, tokens_css  # noqa: E402


class Paleta(unittest.TestCase):
    def test_rgb(self):
        self.assertEqual(rgb("#000000"), (0, 0, 0))
        self.assertEqual(rgb("#FFFFFF"), (1, 1, 1))
        self.assertAlmostEqual(rgb("#2DD4A7")[1], 0xD4 / 255)

    def test_temas_tem_os_mesmos_tokens(self):
        self.assertEqual(set(ESCURO), set(CLARO))

    def test_css_gerado_define_todos_os_tokens(self):
        css = tokens_css(ESCURO)
        for k, v in ESCURO.items():
            self.assertIn("@define-color cap_%s %s;" % (k, v), css)

    def test_a_sobreposicao_usa_a_paleta_do_tema(self):
        os.environ.pop("DISPLAY", None)
        from capture import overlay
        self.assertEqual(overlay.ACENTO, rgb(ESCURO["accent"]))
        self.assertEqual(overlay.SUPERFICIE, rgb(ESCURO["surface"]))
        self.assertEqual(overlay.FUNDO_ESCURO, (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
