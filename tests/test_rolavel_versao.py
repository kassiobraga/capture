"""Fase 5 (congelado): versao 1.4.1, metainfo, README, pagina e documento de passagem."""
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
        self.assertEqual(capture.__version__, "1.4.1")

    def test_metainfo_valido_com_a_1_4_1_no_topo(self):
        raiz = ET.fromstring(fonte("data/io.github.kassiobraga.Capture.metainfo.xml"))
        versoes = [r.get("version") for r in raiz.find("releases").findall("release")]
        self.assertEqual(versoes[0], "1.4.1")
        self.assertIn("1.3.0", versoes)
        topo = raiz.find("releases").findall("release")[0]
        self.assertRegex(topo.get("date"), r"^\d{4}-\d{2}-\d{2}$")
        self.assertTrue("".join(topo.itertext()).strip())

    def test_readme_descreve_a_captura_rolavel(self):
        r = fonte("README.md")
        self.assertIn("rolável", r.lower())
        self.assertIn("--modo ret|janela|tela|livre|rolavel", r)
        self.assertRegex(r, r"\*\*1\.4\*\* \(atual\)")
        self.assertNotRegex(r, r"\*\*1\.3\*\* \(atual\)")

    def test_pagina_do_site_cita_a_1_4_1(self):
        s = fonte("flatpak/site/index.html")
        self.assertRegex(s, r"1\.4\.1\s*<span class=\"etiqueta\">dispon")
        self.assertIn("rolável", s.lower())

    def test_documento_de_passagem_atualizado(self):
        h = fonte("docs/HANDOFF.md")
        self.assertIn("1.4.1", h)

    def test_sem_travessao_nos_textos(self):
        for rel in ("README.md", "flatpak/site/index.html", "docs/HANDOFF.md",
                    "data/io.github.kassiobraga.Capture.metainfo.xml"):
            with self.subTest(rel):
                self.assertNotIn("—", fonte(rel))


if __name__ == "__main__":
    unittest.main()
