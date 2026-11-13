"""Testa scripts/cinnamon.sh com um gsettings falso (nao mexe nas configuracoes reais)."""
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tests.helpers import GSETTINGS_FALSO  # noqa: E402

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NOME = "Capture (io.github.kassiobraga.Capture)"
LANC = "/x/capture"


class Atalho(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stub = os.path.join(self.tmp.name, "estado")
        bin_ = os.path.join(self.tmp.name, "bin")
        os.makedirs(self.stub)
        os.makedirs(bin_)
        g = os.path.join(bin_, "gsettings")
        with open(g, "w") as f:
            f.write(GSETTINGS_FALSO)
        os.chmod(g, 0o755)
        self.env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ["PATH"],
                        STUB_DIR=self.stub, CIN_ESPERA="0")

    def sh(self, codigo):
        script = ". '%s/scripts/cinnamon.sh'\nset -eu\n%s" % (os.path.abspath(RAIZ), codigo)
        r = subprocess.run(["sh", "-c", script], env=self.env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def semear(self, lista, entradas):
        self.sh("cin_grava_lista %s" % " ".join(lista))
        for nome, (cmd, bind) in entradas.items():
            self.sh("cin_set %s name \"'x'\"; cin_set %s command \"'%s'\"; cin_set %s binding \"%s\""
                    % (nome, nome, cmd, nome, bind))

    def lista(self):
        return self.sh("cin_lista").split()

    def campo(self, e, k):
        return self.sh("cin_get %s %s" % (e, k)).strip()

    def historico(self):
        with open(os.path.join(self.stub, "historico")) as f:
            return [x for x in f.read().split("\n") if x]

    def test_lista_vazia_cria_custom0(self):
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0"])
        self.assertEqual(self.campo("custom0", "command"), "'%s --novo'" % LANC)
        self.assertEqual(self.campo("custom0", "binding"), "['Print']")
        self.assertEqual(self.campo("custom0", "name"), "'%s'" % NOME)

    def test_nao_mexe_em_entradas_alheias(self):
        self.semear(["custom0", "custom1"], {"custom0": ("/usr/bin/foo", "['<Super>e']"),
                                             "custom1": ("bar --x", "['<Super>b']")})
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom1", "custom2"])
        self.assertEqual(self.campo("custom0", "command"), "'/usr/bin/foo'")
        self.assertEqual(self.campo("custom0", "binding"), "['<Super>e']")
        self.assertEqual(self.campo("custom1", "command"), "'bar --x'")
        self.assertEqual(self.campo("custom2", "command"), "'%s --novo'" % LANC)

    def test_usa_primeiro_numero_livre(self):
        self.semear(["custom0", "custom2"], {"custom0": ("a", "['F1']"), "custom2": ("b", "['F2']")})
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom2", "custom1"])

    def test_entrada_alheia_chamada_capture_nao_e_tocada(self):
        # mesmo comando "<caminho>/capture --novo", mas de outra pessoa/outro programa
        self.semear(["custom0"], {"custom0": ("/some/path/capture --novo", "['Print']")})
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom1"])
        self.assertEqual(self.campo("custom0", "command"), "'/some/path/capture --novo'")
        self.assertEqual(self.campo("custom0", "name"), "'x'")
        self.sh("cin_desvincula %s" % LANC)
        self.assertEqual(self.lista(), ["custom0"])
        self.assertEqual(self.campo("custom0", "command"), "'/some/path/capture --novo'")
        self.assertEqual(self.campo("custom0", "binding"), "['Print']")

    def test_mesmo_comando_com_outro_nome_nao_e_nosso(self):
        self.semear(["custom0"], {"custom0": ("%s --novo" % LANC, "['F9']")})
        self.sh("cin_desvincula %s" % LANC)
        self.assertEqual(self.lista(), ["custom0"])
        self.assertEqual(self.campo("custom0", "binding"), "['F9']")

    def test_nome_antigo_nao_e_reaproveitado(self):
        self.semear(["custom0"], {"custom0": ("/h/.local/bin/old-tool --novo", "['Print']")})
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom1"])

    def test_repetir_nao_duplica_e_reaproveita_a_propria_entrada(self):
        self.sh("cin_vincula_print %s" % LANC)
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.lista(), ["custom0"])

    def test_recarrega_mudando_a_lista(self):
        self.sh("cin_vincula_print %s" % LANC)
        self.assertEqual(self.historico()[-2:], ["['__dummy__', 'custom0']", "['custom0']"])

    def test_desvincular_remove_so_o_capture(self):
        self.semear(["custom0", "custom1"], {"custom0": ("a", "['F1']"), "custom1": ("b", "['F2']")})
        self.sh("cin_vincula_print %s" % LANC)
        self.sh("cin_desvincula %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom1"])
        self.assertEqual(self.campo("custom2", "command"), "''")
        self.assertEqual(self.campo("custom0", "command"), "'a'")

    def test_desvincular_sem_nada_a_remover_nao_toca_na_lista(self):
        self.semear(["custom0", "custom1"], {"custom0": ("a", "['F1']"), "custom1": ("b", "['F2']")})
        antes = os.path.join(self.stub, "historico")
        self.sh("cin_desvincula %s" % LANC)
        self.assertEqual(self.lista(), ["custom0", "custom1"])
        # nenhuma gravacao de custom-list alem da semeadura
        with open(antes) as f:
            self.assertEqual(len([x for x in f.read().split("\n") if x]), 1)

    def test_interrupcao_nao_deixa_o_dummy_na_lista(self):
        env = dict(self.env, CIN_ESPERA="30")
        script = ". '%s/scripts/cinnamon.sh'\ncin_recarrega custom0 custom1\n" % os.path.abspath(RAIZ)
        p = subprocess.Popen(["sh", "-c", script], env=env, start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            hist = os.path.join(self.stub, "historico")
            for _ in range(100):
                if os.path.exists(hist) and "__dummy__" in pathlib.Path(hist).read_text():
                    break
                time.sleep(0.05)
            else:
                self.fail("o recarregamento nao comecou")
            os.killpg(p.pid, signal.SIGTERM)
            p.wait(timeout=10)
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
        self.assertEqual(self.lista(), ["custom0", "custom1"])
        self.assertNotIn("__dummy__", self.sh("cin_lista"))


if __name__ == "__main__":
    unittest.main()
