"""Laco de rolagem para a captura rolavel. Sem GTK; cairo e x11 so dentro de funcoes."""

from .costura import Costura, SemSobreposicao


def _linha_com_cauda(cauda):
    """Cria um tipo de linha que ignora os ultimos `cauda` bytes ao comparar.

    Serve para a faixa da barra de rolagem, que aparece e some sozinha e
    faria todas as linhas parecerem diferentes entre um quadro e outro.
    """

    class Linha(bytes):
        def __eq__(self, outra):
            return bytes.__eq__(self[:-cauda], bytes(outra)[:-cauda])

        def __ne__(self, outra):
            return not self.__eq__(outra)

        __hash__ = None

    return Linha


def quadro_para_linhas(dados, w, h, cauda_px=0):
    """Converte bytes brutos (BGR0, w*4 bytes por linha) numa lista de bytes.

    Com cauda_px > 0, as linhas ignoram as ultimas cauda_px colunas ao comparar.
    """
    stride = w * 4
    tipo = _linha_com_cauda(cauda_px * 4) if cauda_px > 0 else bytes
    return [tipo(dados[i * stride:(i + 1) * stride]) for i in range(h)]


def linhas_para_superficie(linhas, w):
    """Converte lista de linhas numa cairo.ImageSurface RGB24."""
    import cairo
    h = len(linhas)
    img = cairo.ImageSurface(cairo.FORMAT_RGB24, w, h)
    destino = img.get_data()
    passo = img.get_stride()
    n = w * 4
    for i, linha in enumerate(linhas):
        destino[i * passo:i * passo + n] = linha[:n]
    img.mark_dirty()
    return img


class Resultado:
    """Resultado de uma captura rolavel.

    Atributos:
        linhas: lista de bytes com as linhas costuradas.
        quadros: numero de quadros capturados.
        motivo: razao do encerramento.
        largura: largura em pixels (ou None).
    """

    def __init__(self, linhas, quadros, motivo, largura=None):
        self.linhas = linhas
        self.quadros = quadros
        self.motivo = motivo
        self.largura = largura

    def superficie(self):
        """Devolve cairo.ImageSurface com o resultado costurado."""
        return linhas_para_superficie(self.linhas, self.largura)


class Rolador:
    """Executa o laco de rolagem e costura os quadros capturados.

    Parametros:
        capturar: callable que devolve um quadro (lista de linhas).
        rolar: callable que rola um passo e devolve o numero de pixels (ou None).
        esperar: callable chamado apos rolar() e antes de cada recaptura.
        cancelado: callable que retorna True quando o laco deve parar.
        altura_maxima: limite de linhas do resultado (padrao 30000).
        max_quadros: limite de quadros capturados (padrao 300).
        tolerancia: fracao de linhas sobrepostas que podem diferir.
        tentativas: recapturas apos SemSobreposicao antes de desistir.
    """

    def __init__(
        self,
        capturar,
        rolar,
        esperar=None,
        cancelado=None,
        altura_maxima=30000,
        max_quadros=300,
        tolerancia=0.02,
        tentativas=2,
    ):
        self._capturar = capturar
        self._rolar = rolar
        self._esperar = esperar if esperar is not None else lambda: None
        self._cancelado = cancelado if cancelado is not None else lambda: False
        self._altura_maxima = altura_maxima
        self._max_quadros = max_quadros
        self._tolerancia = tolerancia
        self._tentativas = tentativas

    def executar(self):
        """Executa o laco e devolve um Resultado."""
        primeiro = self._capturar()
        quadros = 1
        costura = Costura(primeiro, tolerancia=self._tolerancia)
        motivo = None

        while True:
            # Verifica cancelamento antes de cada rolagem
            if self._cancelado():
                motivo = "cancelado"
                break

            # Rola e obtem passo esperado (pode ser None)
            passo = self._rolar()
            self._esperar()

            # Captura o proximo quadro
            quadro = self._capturar()
            quadros += 1

            # Tenta adicionar com tratamento de d==0 e SemSobreposicao
            try:
                d = costura.adicionar(quadro, esperado=passo)
            except SemSobreposicao:
                # Recaptura ate tentativas vezes
                adicionado = False
                for _ in range(self._tentativas):
                    self._esperar()
                    quadro = self._capturar()
                    quadros += 1
                    try:
                        d = costura.adicionar(quadro, esperado=passo)
                        adicionado = True
                        break
                    except SemSobreposicao:
                        continue
                if not adicionado:
                    motivo = "sem_sobreposicao"
                    break
                # d foi definido dentro do loop; continua abaixo

            else:
                if d == 0:
                    # Quadro igual: pode ser carga lenta; espera e recaptura UMA vez
                    self._esperar()
                    quadro = self._capturar()
                    quadros += 1
                    try:
                        d = costura.adicionar(quadro, esperado=passo)
                    except SemSobreposicao:
                        motivo = "sem_sobreposicao"
                        break
                    if d == 0:
                        motivo = "fim"
                        break

            # Verifica limite de altura
            if costura.altura >= self._altura_maxima:
                motivo = "limite_altura"
                break

            # Verifica limite de quadros
            if quadros >= self._max_quadros:
                motivo = "limite_quadros"
                break

        linhas = costura.linhas()

        # Corta no limite de altura
        if motivo == "limite_altura" and len(linhas) > self._altura_maxima:
            linhas = linhas[:self._altura_maxima]

        return Resultado(linhas, quadros, motivo)


def rolar_regiao(x, y, w, h, cancelado=None, capturador=None, rodar=None, esperar=None,
                 cliques=3, espera_s=0.35, **kw):
    """Rola e captura uma regiao da tela, devolvendo um Resultado costurado.

    Parametros:
        x, y, w, h: posicao e tamanho da regiao.
        cancelado: callable que retorna True para parar o laco.
        capturador: objeto com quadro(), fechar(), w, h (padrao: x11.CapturadorRegiao).
        rodar: callable(x, y, cliques) que rola a roda do mouse (padrao: x11.rolar_roda).
        esperar: callable chamado antes de cada recaptura (padrao: time.sleep(espera_s)).
        cliques: numero de cliques da roda por passo.
        espera_s: tempo de espera entre passos (segundos).
        **kw: repassado ao Rolador.
    """
    import time
    from . import x11

    if capturador is None:
        capturador = x11.CapturadorRegiao(x, y, w, h)
    if rodar is None:
        rodar = x11.rolar_roda
    if esperar is None:
        esperar = lambda: time.sleep(espera_s)

    cauda = min(20, capturador.w // 10)  # faixa da barra de rolagem, ignorada ao comparar
    cx = x + capturador.w // 2
    cy = y + capturador.h // 2

    def capturar():
        dados = capturador.quadro()
        return quadro_para_linhas(dados, capturador.w, capturador.h, cauda)

    def rolar():
        rodar(cx, cy, cliques)
        return None

    rolador = Rolador(capturar, rolar, esperar=esperar, cancelado=cancelado, **kw)
    try:
        resultado = rolador.executar()
    finally:
        capturador.fechar()

    resultado.largura = capturador.w
    return resultado
