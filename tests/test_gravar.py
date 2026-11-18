"""Testes unitarios da gravacao de tela (MP4 e GIF), posicionamento da barra e historico."""
import datetime
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.arquivos import nome_gravacao  # noqa: E402
from capture.gravar import (  # noqa: E402
    Gravador,
    escolher_encoder_mp4,
    extrair_quadro_cairo,
    formatar_duracao,
    posicionar_barra,
    tem_ffmpeg,
)
from capture.historico import Registro  # noqa: E402


def _intercepta(a, b):
    return (a[0] < b[0] + b[2] and a[0] + a[2] > b[0]
            and a[1] < b[1] + b[3] and a[1] + a[3] > b[1])


class GravacaoUnitaria(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_formatar_duracao(self):
        self.assertEqual(formatar_duracao(0), "00:00")
        self.assertEqual(formatar_duracao(9.8), "00:09")
        self.assertEqual(formatar_duracao(65), "01:05")
        self.assertEqual(formatar_duracao(3661), "1:01:01")

    def test_nome_gravacao_mp4_gif_e_colisao(self):
        dt = datetime.datetime(2026, 11, 17, 15, 30, 45)
        pasta = os.path.join(self.tmp.name, "Capturas")
        c1 = nome_gravacao(pasta, "mp4", agora=dt)
        self.assertTrue(c1.endswith("Gravação de tela 2026-11-17 153045.mp4"))
        with open(c1, "wb") as f:
            f.write(b"x")
        c2 = nome_gravacao(pasta, "mp4", agora=dt)
        self.assertTrue(c2.endswith("Gravação de tela 2026-11-17 153045 (2).mp4"))
        cg = nome_gravacao(pasta, ".GIF", agora=dt)
        self.assertTrue(cg.endswith("Gravação de tela 2026-11-17 153045.gif"))

    def test_posicionar_barra_fica_fora_da_area_gravada(self):
        mon = [(0, 0, 1280, 800)]
        bw, bh = 220, 46

        # regiao no alto -> fica abaixo
        area_alto = (300, 80, 400, 250)
        bx, by = posicionar_barra(area_alto, mon, bw, bh)
        self.assertFalse(_intercepta((bx, by, bw, bh), area_alto))
        self.assertGreaterEqual(by, 80 + 250)

        # regiao embaixo -> fica acima
        area_baixo = (300, 500, 400, 260)
        bx, by = posicionar_barra(area_baixo, mon, bw, bh)
        self.assertFalse(_intercepta((bx, by, bw, bh), area_baixo))
        self.assertLessEqual(by + bh, 500)

        # regiao ocupando a altura quase toda na esquerda -> vai para a direita
        area_esq = (20, 20, 500, 760)
        bx, by = posicionar_barra(area_esq, mon, bw, bh)
        self.assertFalse(_intercepta((bx, by, bw, bh), area_esq))
        self.assertGreaterEqual(bx, 520)

    def test_posicionar_barra_usa_segundo_monitor_quando_primeiro_cheio(self):
        mons = [(0, 0, 1280, 800), (1280, 0, 1280, 800)]
        bw, bh = 220, 46
        area = (0, 0, 1280, 800)
        bx, by = posicionar_barra(area, mons, bw, bh)
        self.assertFalse(_intercepta((bx, by, bw, bh), area))
        self.assertGreaterEqual(bx, 1280)

    def test_posicionar_barra_tela_cheia_monitor_unico_cabe_na_tela(self):
        mons = [(0, 0, 1280, 800)]
        bw, bh = 220, 46
        bx, by = posicionar_barra((0, 0, 1280, 800), mons, bw, bh)
        self.assertGreaterEqual(bx, 0)
        self.assertGreaterEqual(by, 0)
        self.assertLessEqual(bx + bw, 1280)
        self.assertLessEqual(by + bh, 800)

    def test_escolher_encoder_mp4_prioridade_e_fallback(self):
        saida_x264 = " V....D libx264              libx264 H.264\n V....D mpeg4                MPEG-4\n"
        self.assertEqual(escolher_encoder_mp4(saida_x264)[0], "libx264")
        saida_open = " V....D libopenh264          Cisco OpenH264\n V....D mpeg4                MPEG-4\n"
        self.assertEqual(escolher_encoder_mp4(saida_open)[0], "libopenh264")
        saida_min = " V....D mpeg4                MPEG-4 part 2\n"
        self.assertEqual(escolher_encoder_mp4(saida_min)[0], "mpeg4")

    @unittest.skipUnless(tem_ffmpeg(), "sem ffmpeg instalado")
    def test_gravar_mp4_com_dimensoes_impares_e_extrair_miniatura(self):
        w, h = 141, 95
        # BGR0: azul=20, verde=180, vermelho=40
        quadro = bytes([20, 180, 40, 0]) * (w * h)
        destino = os.path.join(self.tmp.name, "video.mp4")
        g = Gravador(w, h, destino, formato="mp4", fps=12, fonte_quadros=lambda: quadro)
        g.iniciar()
        time.sleep(0.22)
        info = g.parar()
        self.assertIsNotNone(info)
        self.assertTrue(os.path.isfile(destino))
        self.assertGreater(os.path.getsize(destino), 200)
        with open(destino, "rb") as f:
            cab = f.read(32)
        self.assertIn(b"ftyp", cab)
        img = extrair_quadro_cairo(destino)
        self.assertIsNotNone(img)
        self.assertGreaterEqual(img.get_width(), w)
        self.assertGreaterEqual(img.get_height(), h)

    @unittest.skipUnless(tem_ffmpeg(), "sem ffmpeg instalado")
    def test_gravar_gif_com_paleta_e_registrar_no_historico(self):
        w, h = 120, 80
        q1 = bytes([30, 40, 220, 0]) * (w * h)
        q2 = bytes([210, 150, 20, 0]) * (w * h)
        n = [0]

        def fonte():
            n[0] += 1
            return q1 if n[0] % 2 else q2

        destino = os.path.join(self.tmp.name, "animacao.gif")
        g = Gravador(w, h, destino, formato="gif", fps=10, fonte_quadros=fonte)
        g.iniciar()
        time.sleep(0.25)
        info = g.parar()
        self.assertIsNotNone(info)
        self.assertTrue(os.path.isfile(destino))
        with open(destino, "rb") as f:
            self.assertEqual(f.read(6), b"GIF89a")

        reg = Registro(
            os.path.join(self.tmp.name, "dados"),
            os.path.join(self.tmp.name, "cache"),
            os.path.join(self.tmp.name, "config"),
        )
        reg.definir_formato_gravacao("gif")
        it = reg.adicionar(destino, info["miniatura_img"], tipo="gif", duracao=info["duracao"])
        self.assertEqual(it["tipo"], "gif")
        self.assertGreater(it["duracao"], 0)
        mini = reg.caminho_miniatura(it)
        self.assertTrue(mini and os.path.isfile(mini))
        # se apagar a miniatura do cache, recria extraindo um quadro do GIF
        os.unlink(mini)
        recriada = reg.caminho_miniatura(it)
        self.assertTrue(recriada and os.path.isfile(recriada))
        # preferencia de formato persiste
        reg2 = Registro(
            os.path.join(self.tmp.name, "dados"),
            os.path.join(self.tmp.name, "cache"),
            os.path.join(self.tmp.name, "config"),
        )
        self.assertEqual(reg2.formato_gravacao, "gif")

    @unittest.skipUnless(tem_ffmpeg(), "sem ffmpeg instalado")
    def test_cancelar_gravacao_descarta_arquivo(self):
        w, h = 80, 60
        quadro = bytes([100, 100, 100, 0]) * (w * h)
        destino = os.path.join(self.tmp.name, "cancelado.mp4")
        g = Gravador(w, h, destino, formato="mp4", fps=10, fonte_quadros=lambda: quadro)
        g.iniciar()
        time.sleep(0.1)
        self.assertIsNone(g.parar(cancelar=True))
        self.assertFalse(os.path.exists(destino))


if __name__ == "__main__":
    unittest.main()
