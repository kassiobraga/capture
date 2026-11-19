"""Costura de quadros para a captura rolavel. Sem GTK e sem display."""


class SemSobreposicao(Exception):
    """Levantada quando nao e possivel encontrar sobreposicao confiavel."""


def linhas_fixas(a, b):
    """Retorna (topo, base): linhas iguais no inicio e no fim dos dois quadros.

    Se os quadros sao identicos, retorna (len(a), 0).
    """
    n = len(a)
    if n != len(b):
        raise ValueError("quadros com alturas diferentes")

    topo = 0
    while topo < n and a[topo] == b[topo]:
        topo += 1

    if topo == n:
        return (n, 0)

    base = 0
    while base < (n - topo) and a[n - 1 - base] == b[n - 1 - base]:
        base += 1

    return (topo, base)


def _busca_candidatos(a, b, inicio_a, fim_a, inicio_b, fim_b, minimo, tolerancia):
    """Busca todos os deslocamentos validos na faixa indicada dos quadros.

    Retorna lista de inteiros d tal que b[inicio_b..fim_b] bate com
    a[inicio_a+d..fim_a-...].
    """
    na = fim_a - inicio_a
    nb = fim_b - inicio_b

    candidatos = []
    # d e o deslocamento: linha i de b corresponde a linha i+d de a
    # sobreposicao = na - d (linhas de b que cabem em a apos o deslocamento)
    for d in range(1, na):
        sobreposicao = na - d
        if sobreposicao < minimo:
            break
        if sobreposicao > nb:
            continue
        # verificar se b[inicio_b .. inicio_b+sobreposicao] == a[inicio_a+d .. inicio_a+d+sobreposicao]
        permitidas = int(tolerancia * sobreposicao)
        diferentes = 0
        valido = True
        for k in range(sobreposicao):
            if b[inicio_b + k] != a[inicio_a + d + k]:
                diferentes += 1
                if diferentes > permitidas:
                    valido = False
                    break
        if valido:
            candidatos.append(d)
    return candidatos


def deslocamento(a, b, esperado=None, minimo=8, tolerancia=0.0):
    """Calcula o deslocamento de rolagem de a para b.

    Retorna:
        0 se a == b;
        int d se houver sobreposicao confiavel;
        None se nao houver sobreposicao confiavel.

    Levanta ValueError se as alturas diferem.

    Com varios candidatos: sem esperado escolhe o menor; com esperado escolhe
    o mais proximo (empate: o menor).

    Ordem de busca: primeiro no quadro inteiro; se nao achar, retira partes
    fixas e busca na parte do meio.
    """
    na = len(a)
    nb = len(b)
    if na != nb:
        raise ValueError("quadros com alturas diferentes")

    # Verifica igualdade total (com a mesma tolerancia: brilho de fim de pagina etc.)
    permitidas = int(tolerancia * na)
    diferentes = 0
    for k in range(na):
        if a[k] != b[k]:
            diferentes += 1
            if diferentes > permitidas:
                break
    if diferentes <= permitidas:
        return 0

    # Primeira tentativa: quadro inteiro
    candidatos = _busca_candidatos(a, b, 0, na, 0, nb, minimo, tolerancia)

    # Segunda tentativa: sem partes fixas
    if not candidatos:
        topo, base = linhas_fixas(a, b)
        if topo > 0 or base > 0:
            fim_a = na - base
            fim_b = nb - base
            candidatos = _busca_candidatos(
                a, b, topo, fim_a, topo, fim_b, minimo, tolerancia
            )

    if not candidatos:
        return None

    if esperado is None:
        return candidatos[0]  # menor (lista esta em ordem crescente)

    # Escolhe o mais proximo do esperado; empate: o menor (primeiro na lista)
    melhor = candidatos[0]
    melhor_dist = abs(melhor - esperado)
    for c in candidatos[1:]:
        dist = abs(c - esperado)
        if dist < melhor_dist:
            melhor = c
            melhor_dist = dist
    return melhor


class Costura:
    """Emenda quadros de rolagem numa unica imagem.

    Parametros:
        primeiro: lista de bytes (uma por linha de pixels) do primeiro quadro.
        minimo: minimo de linhas sobrepostas para aceitar o deslocamento.
        tolerancia: fracao das linhas sobrepostas que podem diferir.
    """

    def __init__(self, primeiro, minimo=8, tolerancia=0.0):
        self._linhas = list(primeiro)
        self._minimo = minimo
        self._tolerancia = tolerancia
        # Ultimo quadro adicionado (para comparar com o proximo)
        self._ultimo = list(primeiro)
        # Quantas linhas do rodape do quadro atual sao fixas
        self._base_atual = 0

    def adicionar(self, quadro, esperado=None):
        """Acrescenta quadro e devolve o deslocamento aplicado.

        Retorna 0 se o quadro nao trouxe conteudo novo (fim de pagina).
        Levanta SemSobreposicao sem alterar o estado quando nao ha sobreposicao.
        """
        anterior = self._ultimo

        d = deslocamento(
            anterior, quadro,
            esperado=esperado,
            minimo=self._minimo,
            tolerancia=self._tolerancia,
        )

        if d is None:
            raise SemSobreposicao("nao foi possivel encontrar sobreposicao confiavel")

        if d == 0:
            return 0

        n = len(quadro)

        # Detecta rodape fixo: linhas que ficam fixas apos o deslocamento.
        # Compara as ultimas linhas do anterior com as ultimas linhas do quadro,
        # mas limitado a no maximo d linhas (as linhas novas sao as ultimas d).
        # O rodape so pode ter ate (n - d - minimo) linhas para nao encolher
        # demais a sobreposicao.
        base = 0
        base_max = min(d, n - d - self._minimo)
        if base_max > 0:
            for k in range(base_max):
                if anterior[n - 1 - k] == quadro[n - 1 - k]:
                    base += 1
                else:
                    break

        # Remove o rodape fixo atual do costurado.
        # Na primeira adicao (_base_atual=0 mas base>0), remove o rodape
        # que estava incluido no primeiro quadro mas so agora e identificado.
        to_remove = self._base_atual if self._base_atual > 0 else base
        if to_remove > 0:
            del self._linhas[-to_remove:]

        # As d ultimas linhas da parte rolante do quadro novo
        # (excluindo o rodape fixo)
        fim_rolante = n - base
        novas = quadro[fim_rolante - d:fim_rolante]
        self._linhas.extend(novas)

        # Adiciona o rodape do quadro novo
        if base > 0:
            self._linhas.extend(quadro[n - base:])

        self._base_atual = base
        self._ultimo = list(quadro)

        return d

    @property
    def altura(self):
        """Numero total de linhas costuradas."""
        return len(self._linhas)

    def linhas(self):
        """Devolve uma copia da lista de linhas costuradas."""
        return list(self._linhas)
