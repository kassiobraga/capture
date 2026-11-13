"""install.sh e uninstall.sh de ponta a ponta, num HOME falso e com gsettings falso."""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tests.helpers import GSETTINGS_FALSO  # noqa: E402

RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
APP_ID = "io.github.kassiobraga.Capture"


def instantaneo(raiz):
    """{caminho relativo: hash do conteudo} de tudo sob raiz (links, como o proprio alvo)."""
    out = {}
    for pasta, _, arqs in os.walk(raiz):
        for a in arqs:
            c = os.path.join(pasta, a)
            with open(c, "rb") as f:
                out[os.path.relpath(c, raiz)] = hashlib.sha256(f.read()).hexdigest()
    return out


class Instalacao(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cap")
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "home")
        self.stub = os.path.join(self.tmp.name, "estado")
        bin_ = os.path.join(self.tmp.name, "bin")
        for d in (self.home, self.stub, bin_):
            os.makedirs(d)
        g = os.path.join(bin_, "gsettings")
        with open(g, "w") as f:
            f.write(GSETTINGS_FALSO)
        os.chmod(g, 0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith(("XDG_", "CAPTURE_"))}
        env.update(HOME=self.home, PATH=bin_ + os.pathsep + os.environ["PATH"], STUB_DIR=self.stub,
                   CIN_ESPERA="0", XDG_SESSION_TYPE="x11")
        self.env = env
        self.bin = os.path.join(self.home, ".local", "bin", "capture")
        self.desktop = os.path.join(self.home, ".local/share/applications", APP_ID + ".desktop")
        self.dados = os.path.join(self.home, ".local/share", APP_ID)

    def roda(self, script, *args, env=None):
        return subprocess.run(["sh", os.path.join(RAIZ, script), *args], env=env or self.env,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def instala(self, *args):
        r = self.roda("install.sh", *args)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        return r

    def test_instala_os_arquivos_esperados(self):
        self.instala("--bind-print")
        with open(self.bin) as f:
            lancador = f.read()
        self.assertIn("# capture-launcher: " + APP_ID, lancador)
        self.assertIn(self.dados, lancador)
        self.assertTrue(os.access(self.bin, os.X_OK))
        with open(self.desktop) as f:
            d = f.read()
        self.assertIn("Exec=%s\n" % self.bin, d)
        self.assertIn("Icon=" + APP_ID, d)
        self.assertIn("StartupWMClass=capture", d)
        self.assertNotIn("@BIN@", d)
        self.assertTrue(os.path.isfile(os.path.join(self.dados, "capture", "__main__.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".local/share/icons/hicolor/scalable/apps",
                                                    APP_ID + ".svg")))
        # nada com nome generico
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local/share/capture")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".local/share/applications/capture.desktop")))

    def test_instalar_duas_vezes_nao_muda_nada(self):
        self.instala("--bind-print")
        antes = instantaneo(self.home)
        estado = instantaneo(self.stub)
        r = self.instala("--bind-print")
        self.assertEqual(instantaneo(self.home), antes)
        with open(os.path.join(self.stub, "org.cinnamon.desktop.keybindings_custom-list")) as f:
            self.assertEqual(f.read().strip(), "['custom0']")
        del estado, r

    def test_nao_sobrescreve_lancador_alheio(self):
        os.makedirs(os.path.dirname(self.bin))
        with open(self.bin, "w") as f:
            f.write("#!/bin/sh\necho meu proprio capture\n")
        r = self.roda("install.sh")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nao foi criado pelo Capture", r.stderr)
        with open(self.bin) as f:
            self.assertIn("meu proprio capture", f.read())
        self.assertFalse(os.path.exists(self.dados))

    def test_rejeita_home_com_espaco(self):
        casa = os.path.join(self.tmp.name, "pasta com espaco")
        os.makedirs(casa)
        r = self.roda("install.sh", env=dict(self.env, HOME=casa))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("espacos", r.stderr)
        self.assertEqual(os.listdir(casa), [])

    def test_desinstalar_remove_o_nosso_e_deixa_o_alheio(self):
        self.instala("--bind-print")
        cache_alheio = os.path.join(self.home, ".cache", "capture")
        os.makedirs(cache_alheio)
        with open(os.path.join(cache_alheio, "dado"), "w") as f:
            f.write("de outro programa")
        os.makedirs(os.path.join(self.home, ".cache", APP_ID))
        r = self.roda("uninstall.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        for c in (self.bin, self.desktop, self.dados, os.path.join(self.home, ".cache", APP_ID)):
            self.assertFalse(os.path.exists(c), c)
        self.assertEqual(os.listdir(cache_alheio), ["dado"])
        with open(os.path.join(self.stub, "org.cinnamon.desktop.keybindings_custom-list")) as f:
            self.assertEqual(f.read().strip(), "[]")
        restos = [c for c in instantaneo(self.home) if APP_ID in c]
        self.assertEqual(restos, [])

    def test_desinstalar_mantem_lancador_alheio(self):
        self.instala()
        with open(self.bin, "w") as f:
            f.write("#!/bin/sh\necho outro\n")
        r = self.roda("uninstall.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(os.path.exists(self.bin))
        self.assertFalse(os.path.exists(self.dados))

    def test_desinstalar_remove_o_atalho_mesmo_sem_o_lancador(self):
        self.instala("--bind-print")
        os.unlink(self.bin)   # apagado a mao
        r = self.roda("uninstall.sh")
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.stub, "org.cinnamon.desktop.keybindings_custom-list")) as f:
            self.assertEqual(f.read().strip(), "[]")
        self.assertFalse(os.path.exists(self.dados))

    def test_desinstalar_sem_instalar_nao_faz_nada(self):
        r = self.roda("uninstall.sh")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_desinstalar_nao_toca_em_atalho_alheio(self):
        self.instala("--bind-print")
        # outra pessoa passa a usar Print com um comando proprio
        subprocess.run(["sh", "-c", ". '%s/scripts/cinnamon.sh'; cin_set custom9 name \"'x'\"; "
                        "cin_set custom9 command \"'/y/capture --novo'\"; "
                        "cin_grava_lista custom0 custom9" % RAIZ], env=self.env, check=True)
        self.roda("uninstall.sh")
        with open(os.path.join(self.stub, "org.cinnamon.desktop.keybindings_custom-list")) as f:
            self.assertEqual(f.read().strip(), "['custom9']")


if __name__ == "__main__":
    unittest.main()
