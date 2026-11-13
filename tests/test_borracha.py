"""Borracha: o acerto vale para a geometria real do desenho, nao para a caixa que o envolve."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from capture.editor import acerta_item, item_vazio  # noqa: E402
from tests.helpers import novo_doc, superficie  # noqa: E402

V = (1.0, 0.0, 0.0)


def forma(t, a, b, esp=4):
    return {"t": t, "cor": V, "esp": esp, "a": a, "b": b}


class Acerto(unittest.TestCase):
    def test_miolo_vazio_do_retangulo_nao_acerta(self):
        r = forma("f_ret", (20, 20), (180, 120))
        self.assertFalse(acerta_item(r, (100, 70)))
        self.assertTrue(acerta_item(r, (100, 20)))   # em cima do lado
        self.assertTrue(acerta_item(r, (20, 70)))
        self.assertTrue(acerta_item(r, (100, 25)))   # dentro da tolerancia
        self.assertFalse(acerta_item(r, (100, 40)))  # 20 px do lado: fora

    def test_miolo_vazio_da_elipse_nao_acerta(self):
        e = forma("f_elipse", (20, 20), (180, 120))
        self.assertFalse(acerta_item(e, (100, 70)))
        self.assertFalse(acerta_item(e, (25, 25)))   # canto da caixa, fora da curva
        self.assertTrue(acerta_item(e, (180, 70)))
        self.assertTrue(acerta_item(e, (100, 20)))

    def test_longe_da_diagonal_dentro_da_caixa_nao_acerta(self):
        d = forma("f_linha", (10, 10), (190, 110))
        self.assertTrue(acerta_item(d, (100, 65)))   # na linha
        self.assertFalse(acerta_item(d, (180, 20)))  # canto da caixa
        self.assertFalse(acerta_item(d, (20, 100)))

    def test_seta(self):
        s = forma("f_seta", (10, 10), (190, 110))
        self.assertTrue(acerta_item(s, (100, 65)))
        self.assertFalse(acerta_item(s, (20, 100)))

    def test_caneta_e_marca_texto(self):
        c = {"t": "caneta", "cor": V, "esp": 4, "pts": [(10, 10), (100, 10), (100, 100)]}
        self.assertTrue(acerta_item(c, (50, 10)))
        self.assertTrue(acerta_item(c, (100, 60)))
        self.assertFalse(acerta_item(c, (30, 80)))   # dentro da caixa, longe do traco
        m = {"t": "marca", "cor": V, "esp": 20, "pts": [(10, 50), (100, 50)]}
        self.assertTrue(acerta_item(m, (50, 58)))
        self.assertFalse(acerta_item(m, (50, 80)))

    def test_texto_usa_a_area_ocupada_pela_tinta(self):
        t = {"t": "texto", "cor": V, "txt": "Ola", "a": (50, 50), "tam": 30, "esp": 2}
        self.assertTrue(acerta_item(t, (60, 65)))
        self.assertFalse(acerta_item(t, (300, 65)))
        self.assertFalse(acerta_item(t, (60, 200)))

    def test_elipse_degenerada(self):
        self.assertFalse(acerta_item(forma("f_elipse", (10, 10), (10, 80)), (10, 40)))


class ApagarNoDocumento(unittest.TestCase):
    def setUp(self):
        self.d = novo_doc(superficie(200, 150, (1, 1, 1, 1)))

    def test_clique_no_miolo_nao_apaga_a_forma(self):
        self.d.adiciona(forma("f_ret", (20, 20), (180, 120)))
        self.assertFalse(self.d.apaga_em((100, 70)))
        self.assertEqual(len(self.d.itens), 1)
        self.assertTrue(self.d.apaga_em((100, 20)))
        self.assertEqual(self.d.itens, [])

    def test_apaga_o_item_de_tras_quando_o_de_cima_nao_esta_sob_o_ponto(self):
        self.d.adiciona(forma("f_ret", (20, 20), (180, 120)))
        self.d.adiciona(forma("f_linha", (30, 30), (60, 30)))
        self.assertTrue(self.d.apaga_em((100, 20)))
        self.assertEqual([i["t"] for i in self.d.itens], ["f_linha"])

    def test_arraste_da_borracha_e_um_unico_passo(self):
        for y in (20, 60, 100):
            self.d.adiciona({"t": "caneta", "cor": V, "esp": 4, "pts": [(10, y), (150, y)]})
        passos = len(self.d.desf)
        achou = False
        for i, y in enumerate((20, 60, 100)):
            achou = self.d.apaga_em((80, y), guarda=(i == 0)) or achou
        self.assertTrue(achou)
        self.assertEqual(self.d.itens, [])
        self.assertEqual(len(self.d.desf), passos + 1)
        self.d.desfazer()
        self.assertEqual(len(self.d.itens), 3)


class ShapesVazias(unittest.TestCase):
    def setUp(self):
        self.d = novo_doc(superficie(100, 100))

    def test_clique_simples_com_forma_nao_cria_item(self):
        for t in ("f_ret", "f_elipse", "f_linha", "f_seta"):
            self.assertFalse(self.d.adiciona(forma(t, (50, 50), (51, 50.5))), t)
        self.assertEqual(self.d.itens, [])
        self.assertEqual(self.d.desf, [])

    def test_forma_com_tamanho_real_e_guardada(self):
        self.assertTrue(self.d.adiciona(forma("f_ret", (10, 10), (14, 12))))

    def test_clique_de_caneta_continua_sendo_um_ponto(self):
        self.assertTrue(self.d.adiciona({"t": "caneta", "cor": V, "esp": 4, "pts": [(5, 5)]}))
        self.assertFalse(item_vazio({"t": "caneta", "pts": [(5, 5)]}))



class ArrasteSemInicio(unittest.TestCase):
    def test_borracha_sem_passar_pelo_inicio_do_arraste(self):
        # E pressionada no meio de um arraste de outra ferramenta: _apagou nunca foi definido pelo inicio
        d = novo_doc(superficie(200, 150))
        d.adiciona({"t": "caneta", "cor": V, "esp": 4, "pts": [(10, 10), (150, 10)]})
        self.assertTrue(d.apaga_arraste((80, 10)))
        self.assertEqual(d.itens, [])
        self.assertEqual(len(d.desf), 2)  # adicionar + apagar


if __name__ == "__main__":
    unittest.main()
