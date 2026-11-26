"""Fase 5 (congelado): versao 1.4.2, metainfo, README, pagina e documento de passagem."""
import os
import re
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import capture

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def fonte(rel):
    with open(os.path.join(RAIZ, rel), encoding="utf-8") as f:
        return f.read()


class Versao(unittest.TestCase):
    def test_versao_do_pacote(self):
        self.assertEqual(capture.__version__, "1.5.0")

    def test_metainfo_valido_com_a_1_5_0_no_topo(self):
        raiz = ET.fromstring(fonte("data/io.github.kassiobraga.Capture.metainfo.xml"))
        versoes = [r.get("version") for r in raiz.find("releases").findall("release")]
        self.assertEqual(versoes[0], "1.5.0")
        self.assertIn("1.4.2", versoes)
        self.assertIn("1.4.1", versoes)
        self.assertIn("1.3.0", versoes)
        topo = raiz.find("releases").findall("release")[0]
        self.assertRegex(topo.get("date"), r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue("".join(topo.itertext()).strip())

    def test_readme_descreve_recursos_atuais_e_autoria(self):
        r = fonte("README.md")
        self.assertIn("rolável", r.lower())
        self.assertIn("microfone", r.lower())
        self.assertIn("kassiobraga.com.br", r)
        self.assertIn("--modo ret|janela|tela|livre|rolavel", r)
        self.assertRegex(r, r"\*\*1\.5\*\* \(atual\)")
        self.assertNotRegex(r, r"\*\*1\.4\*\* \(atual\)")

    def test_pagina_do_site_cita_a_1_5_e_portfolio(self):
        s = fonte("flatpak/site/index.html")
        self.assertRegex(s, r"v1\.5\.0</span>\s*<span class=\"status-pill status-done\">Dispon")
        self.assertIn("rolável", s.lower())
        self.assertIn("microfone", s.lower())
        self.assertIn("kassiobraga.com.br", s)
        self.assertIn("tooltip-bubble", s)

    def test_documento_de_passagem_atualizado(self):
        h = fonte("docs/HANDOFF.md")
        self.assertIn("1.5.0", h)
        self.assertIn("kassiobraga.com.br", h)

    def test_sem_travessao_nos_textos(self):
        for rel in ("README.md", "flatpak/site/index.html", "docs/HANDOFF.md",
                    "data/io.github.kassiobraga.Capture.metainfo.xml"):
            with self.subTest(rel):
                self.assertNotIn("—", fonte(rel))


if __name__ == "__main__":
    unittest.main()
