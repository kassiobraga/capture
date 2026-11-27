"""Captura e area de transferencia via python-xlib num display X de verdade.

Pulados sem DISPLAY, sem python-xlib ou sem xclip (usado so para ler de volta).
Para rodar sem desktop: xvfb-run -a python3 -m unittest tests.test_xlib
"""
import os
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture import area, x11  # noqa: E402

PULAR = None
if not x11.tem_xlib():
    PULAR = "python-xlib nao esta instalado"
elif not os.environ.get("DISPLAY"):
    PULAR = "sem display X"


@unittest.skipIf(PULAR, PULAR or "")
class Xlib(unittest.TestCase):
    def test_foto_tem_o_tamanho_da_tela(self):
        img = x11.foto_da_tela()
        d = x11._abre()
        geo = d.screen().root.get_geometry()
        d.close()
        self.assertEqual((img.get_width(), img.get_height()), (geo.width, geo.height))

    def test_libx11_e_python_xlib_dao_a_mesma_imagem(self):
        a, b = x11._foto_libx11(), x11._foto_xlib()
        self.assertEqual((a.get_width(), a.get_height()), (b.get_width(), b.get_height()))
        self.assertEqual(bytes(a.get_data()), bytes(b.get_data()))

    def test_listar_janelas_nao_falha(self):
        self.assertIsInstance(x11.listar_janelas(), list)

    def test_capturador_regiao_le_quadro_bgr0(self):
        with x11.CapturadorRegiao(10, 15, 96, 64) as cap:
            q = cap.quadro()
            self.assertEqual(len(q), 96 * 64 * 4)
            sup = cap.para_superficie(q)
            self.assertEqual((sup.get_width(), sup.get_height()), (96, 64))

    @unittest.skipUnless(shutil.which("xclip"), "sem xclip para ler a area de transferencia")
    def test_copia_pequena_e_grande(self):
        for n in (1000, 2_000_000):  # a grande passa pelo protocolo INCR
            dados = os.urandom(n)
            self.assertTrue(area.copiar(dados))
            lido = subprocess.run(["xclip", "-o", "-selection", "clipboard", "-t", "image/png"],
                                  capture_output=True, timeout=20).stdout
            self.assertEqual(lido, dados)
        subprocess.run(["xclip", "-selection", "clipboard"], input=b"fim", timeout=5)


class ConsensoQuadros(unittest.TestCase):
    def _quadro(self, h=20, passo=16, faixa=None):
        """Gera um quadro limpo com opcional faixa corrompida (y0, y1, byte)."""
        linhas = [bytes([10 + i]) * passo for i in range(h)]
        if faixa is not None:
            y0, y1, val = faixa
            for i in range(y0, y1):
                linhas[i] = bytes([val]) * passo
        return b"".join(linhas)

    def test_tela_estatica_para_no_segundo_quadro(self):
        limpo = self._quadro()
        chamadas = []

        def ler():
            chamadas.append(1)
            return limpo, 4, 20, 16

        res, w, h, passo = x11._capturar_estavel(ler, intervalo=0, dormir=lambda _: None)
        self.assertEqual(len(chamadas), 2)
        self.assertEqual((res, w, h, passo), (limpo, 4, 20, 16))

    def test_remove_faixa_no_primeiro_segundo_ou_terceiro_quadro(self):
        limpo = self._quadro()
        sujo = self._quadro(faixa=(8, 12, 250))
        for seq in ([sujo, limpo, limpo], [limpo, sujo, limpo], [limpo, limpo, sujo]):
            it = iter(seq)
            res, *_ = x11._capturar_estavel(
                lambda: (next(it), 4, 20, 16), intervalo=0, dormir=lambda _: None
            )
            self.assertEqual(res, limpo)

    def test_remove_faixas_em_linhas_distintas_entre_quadros(self):
        limpo = self._quadro()
        q1 = self._quadro(faixa=(2, 5, 200))
        q2 = self._quadro(faixa=(12, 15, 210))
        q3 = limpo
        self.assertEqual(x11._combinar_quadros(q1, q2, q3, 20, 16), limpo)


if __name__ == "__main__":
    unittest.main()
