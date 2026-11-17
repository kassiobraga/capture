"""tema_escuro nao pode abortar o processo quando o esquema do Cinnamon nao existe."""
import os
import subprocess
import sys
import unittest

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class Tema(unittest.TestCase):
    def rodar(self, codigo):
        # em subprocesso: se o GLib abortar (g_error), o teste falha em vez de derrubar o runner
        return subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, capture_output=True, text=True,
                              env=dict(os.environ, PYTHONPATH=RAIZ))

    def test_esquema_inexistente_devolve_none(self):
        r = self.rodar("from capture.app import tema_escuro\n"
                       "print(tema_escuro('org.exemplo.nao.existe'))")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "None")

    def test_chave_inexistente_devolve_none(self):
        r = self.rodar("from capture.app import tema_escuro\n"
                       "print(tema_escuro('org.gnome.desktop.interface', 'chave-que-nao-existe'))")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "None")

    def test_esquema_real_devolve_booleano_ou_none(self):
        r = self.rodar("from capture.app import tema_escuro\n"
                       "print(tema_escuro('org.cinnamon.desktop.interface'))")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(r.stdout.strip(), ("True", "False", "None"))



class NomeDeTema(unittest.TestCase):
    def test_variantes_escuras(self):
        sys.path.insert(0, RAIZ)
        from capture.app import nome_de_tema_escuro
        for n in ("Mint-Y-Dark-Blue", "Adwaita-dark", "Yaru-DARK", "Breeze-Dark"):
            self.assertTrue(nome_de_tema_escuro(n), n)
        for n in ("Mint-Y", "Adwaita", "", None):
            self.assertFalse(nome_de_tema_escuro(n), n)

    def test_tema_do_gtk_nao_quebra(self):
        r = Tema.rodar(self, "import gi\ngi.require_version('Gtk','4.0')\n"
                       "from capture.app import tema_escuro_do_gtk\nprint(tema_escuro_do_gtk())")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(r.stdout.strip(), ("True", "False", "None"))


class Caminho(unittest.TestCase):
    def test_decodifica_opcao_filename(self):
        sys.path.insert(0, RAIZ)
        from capture.app import decodifica_caminho
        self.assertEqual(decodifica_caminho(list(b"/tmp/a b.png\0")), "/tmp/a b.png")
        self.assertEqual(decodifica_caminho(b"rel.png"), "rel.png")
        self.assertEqual(decodifica_caminho("x.png"), "x.png")
        self.assertEqual(decodifica_caminho(list("ação.png".encode())), "ação.png")


if __name__ == "__main__":
    unittest.main()
