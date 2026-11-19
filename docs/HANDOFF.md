# Capture: documento de passagem do projeto

Documento para quem vai continuar o desenvolvimento (pessoa ou agente de IA).
Descreve o que o Capture é, como o código está organizado, como se testa e se
publica, o que já foi decidido e o que falta fazer. Estado em 19/11/2026,
versão **1.4.0**.

- Repositório: <https://github.com/kassiobraga/capture> (público, licença MIT)
- Página de instalação: <https://kassiobraga.github.io/capture/>
- Dono e mantenedor: Kassio Braga (conta GitHub `kassiobraga`), usa Linux Mint 22
  com Cinnamon em X11 e placa NVIDIA.

---

## 1. O que é o Capture

Aplicativo de captura de tela e anotação para Linux, em Python com GTK 4 e
libadwaita. Fluxo principal: a pessoa aperta Print, seleciona uma área, e a
imagem já sai copiada para a área de transferência e salva em PNG. Se quiser,
anota por cima no editor antes de colar em outro lugar.

### Recursos atuais (1.4.0)

- Modos de captura: retângulo, janela, tela cheia, forma livre e rolável; atraso opcional
  de 3, 5 ou 10 s; seleção em vários monitores ao mesmo tempo.
- **Captura rolável**: captura páginas e janelas mais compridas que a tela; o Capture
  rola automaticamente via XTest (python-xlib), tira fotos a cada passo e emenda os quadros
  por comparação exata de linhas de pixels, preservando cabeçalho e rodapé fixos uma única vez.
- Editor: caneta, marca-texto, borracha (apaga a marcação clicada), retângulo,
  elipse, linha, seta, texto, cortar, **pixelar** (tecla B), girar 90° e
  redimensionar (px ou %, com proporção). Desfazer/refazer em tudo.
- **Abas**: cada captura abre numa aba ("Captura 1", "Captura 2"...). Fecha no ×
  ou com Ctrl+W; se a aba tiver alterações não salvas (título com "•"), pede
  confirmação. Com 2+ abas, um botão no cabeçalho **junta todas num PDF**, uma
  página por aba.
- Salvar como **PNG, JPEG ou PDF**, decidido pela extensão do nome.
- Toda captura nova é copiada e salva automaticamente em `~/Imagens/Capturas`
  (pasta de imagens do usuário, via `GLib.get_user_special_dir`).
- Tema escuro (Dark) e claro (Clean), seguindo o tema do desktop.
- Instância única: `capture --novo` etc. são enviados para o processo aberto.

### Limitações conhecidas

- **Só X11.** Wayland não permite que um app comum fotografe a tela nem desenhe
  a seleção por cima de tudo. O suporte virá pelo portal (ver roadmap).
- Uma seleção não atravessa dois monitores; "tela cheia" junta todos numa imagem.
- A tecla Print não é configurada automaticamente no Flatpak (o sandbox não
  mexe nos atalhos do Cinnamon); a pessoa cria um atalho para
  `flatpak run io.github.kassiobraga.Capture --novo`.
- **Limites da rolagem**: cabeçalhos que mudam de tamanho, páginas com rolagem infinita,
  animações e vídeos no meio da página, e aplicativos que ignoram a roda do mouse podem
  resultar em emenda parcial; o Capture entrega o que conseguiu capturar.

---

## 2. Arquitetura e código

Tudo em Python puro, sem etapa de compilação. Identificadores, comentários e
mensagens de commit são em **português**; comentários e docstrings no código
ficam sem acento (ASCII); textos da interface têm acento normal.

```
capture/
  __init__.py   versao (__version__), APP_ID, MODOS, ATRASOS, CORES
  __main__.py   python3 -m capture -> app.principal()
  app.py        Janela (Adw.ApplicationWindow) e App (Adw.Application):
                cabecalho, dock de ferramentas, abas (Adw.TabView), avisos,
                copiar/salvar/PDF, dialogo de redimensionar, tema, linha de comando
  editor.py     Modelo (documento sem GTK: base + itens + desfazer) e Editor
                (Gtk.DrawingArea): desenho, gestos, pixelar/girar/redimensionar
  overlay.py    Sessao de captura (foto da tela + janelas de selecao por monitor),
                funcao foto() com as alternativas de captura
  costura.py    emenda de quadros por comparacao exata de linhas de pixels,
                deteccao de cabecalho e rodape fixos (SemSobreposicao, Costura)
  rolagem.py    laco de rolagem e captura automatica em thread separada (Rolador,
                rolar_regiao, Resultado)
  x11.py        foto da tela (libX11 via ctypes; reserva python-xlib), lista de
                janelas visiveis e rolar_roda (XTest fake_input)
  area.py       area de transferencia X11 propria (processo em segundo plano que
                serve image/png, com INCR), no lugar do xclip
  exportar.py   gravacao em PNG/JPEG (GdkPixbuf)/PDF (cairo) e PDF de varias paginas
  arquivos.py   pasta e nomes das capturas ("Captura de tela AAAA-MM-DD HHMMSS.png")
  icons.py      icones de linha desenhados com cairo (Icone, botao)
  tema.py       tokens de cor ESCURO/CLARO
  teste.py      ganchos dos testes e2e (CAPTURE_TEST_*): grava geometria em JSON
data/           capture.desktop (modelo), capture.svg, metainfo AppStream
docs/           imagens do README/site, gerar_captura.py, FLATHUB.md, este arquivo
flatpak/        manifesto do Flatpak e site/index.html (pagina do GitHub Pages)
scripts/        cinnamon.sh (atalho Print, usado so pelo install.sh)
tests/          unitarios (sem display) e tests/e2e (mouse/teclado reais via XTest)
install.sh      instalacao manual em ~/.local (modo desenvolvimento)
.github/workflows/flatpak.yml   build, assinatura e publicacao
```

### Pontos importantes do desenho

- **Modelo x Editor**: `editor.Modelo` não usa GTK e é o que os testes
  unitários exercitam. Itens são dicts (`{"t": "caneta", "pts": [...]}`,
  `{"t": "f_seta", "a": ..., "b": ...}`, `{"t": "pixelar", "pos": ..., "patch":
  surface}` etc.). Operações destrutivas (cortar, girar, redimensionar) achatam
  as marcações na imagem base. `_guarda()` cria o passo de desfazer e marca
  `alterado = True`.
- **Abas**: cada aba é um `Editor`. `Janela.editor` aponta sempre para o da aba
  atual; sem abas, aponta para `_sem_aba` (editor vazio fora da tela). Cores,
  espessuras e ferramenta são compartilhadas entre abas.
- **Captura da tela** (`x11.foto_da_tela`): um único `XGetImage` na janela raiz
  pela libX11 (ctypes). Antes era em faixas via python-xlib, e um redesenho no
  meio deixava listras com o papel de parede (bug corrigido na 1.1.1). Ordem de
  reserva: libX11 → python-xlib → `maim`.
- **Área de transferência**: `xclip` se existir (instalação manual); senão
  `python3 -m capture.area` (processo próprio que fica dono do CLIPBOARD até
  outro app copiar algo); por último `Gdk.Clipboard`.
- **Tema**: `CAPTURE_TEMA=escuro|claro` força; senão lê o esquema do Cinnamon;
  no Flatpak (sem esse esquema) lê `gtk-theme` pelo portal
  `org.freedesktop.portal.Settings` (o libadwaita troca o nome interno do tema
  para "Adwaita-empty", por isso a leitura direta do portal).
- **Captura rolável**: `costura.py` faz a emenda exata de linhas de pixels (BGR0)
  e trata cabeçalho e rodapé fixos; `rolagem.py` executa o laço de captura em thread
  separada e rola o conteúdo via `x11.rolar_roda` (XTest fake_input). O resultado é
  entregue à interface via `GLib.idle_add` e aberto numa nova aba.
- **NVIDIA**: o manifesto define `GSK_RENDERER=cairo`. Com driver NVIDIA, os
  renderizadores GL/Vulkan do GTK falham no sandbox X11 e a janela não abre.
- **Variáveis de ambiente**: `CAPTURE_DIR` (pasta das capturas),
  `CAPTURE_APP_ID` (id alternativo, usado nos testes), `CAPTURE_TEMA`,
  `CAPTURE_TEST_GEOM`, `CAPTURE_TEST_SALVAR`, `CAPTURE_TEST_PDF`.

---

## 3. Empacotamento e distribuição

### Flatpak (forma oficial de instalar)

- Manifesto: `flatpak/io.github.kassiobraga.Capture.yml`. Runtime
  `org.gnome.Platform` **49** (traz Python, GTK 4, libadwaita, PyGObject,
  pycairo, GdkPixbuf e libX11). Único módulo extra: `python-xlib` 0.33 + `six`
  (wheels do PyPI com sha256).
- Permissões: `--socket=x11`, `--share=ipc`, `--filesystem=xdg-pictures`,
  `--env=GSK_RENDERER=cairo`.
- **Regra do projeto: nada de dependência que o usuário precise instalar.**
  Qualquer biblioteca ou binário novo vai dentro do manifesto.

### Repositório próprio com atualização automática

Não está no Flathub (ver seção 7). O Capture tem um **repositório Flatpak
próprio** servido pelo GitHub Pages:

- `https://kassiobraga.github.io/capture/repo/` (OSTree), ramo `stable`.
- `io.github.kassiobraga.Capture.flatpakref` (botão "Instalar" da página) e
  `capture.flatpakrepo`.
- Quem instala por esse link recebe as versões novas pelo Gerenciador de
  Atualizações do Mint (ou `flatpak update`). Já foi testado de ponta a ponta
  (a 1.1.0 e a 1.1.1 chegaram assim no PC do Kassio).

O workflow `.github/workflows/flatpak.yml`:

- **Todo push**: constrói, assina com uma chave descartável se o segredo não
  existir, e guarda `Capture.flatpak` como artefato de teste. Não publica.
- **Tag `v*`** (ou execução manual na `main`): assina com a chave real (segredo
  `FLATPAK_GPG_KEY`), publica o site e o repositório no branch `gh-pages`
  (`force_orphan`) e anexa `Capture.flatpak` ao release.
- O Pages está configurado como "Deploy from a branch: gh-pages / root".

### Chave de assinatura

- GPG RSA 4096, identificação `03CEC8A4A14E992DDFD6564798FE424A49BDA810`
  ("Capture Flatpak"). A privada está no segredo `FLATPAK_GPG_KEY` do GitHub e
  com cópia no gerenciador de senhas do Kassio.
- **Nunca** coloque a chave privada no repositório, em logs ou em chat. Se a
  chave mudar, quem já instalou precisa reinstalar pelo link.

### Como lançar uma versão

1. Altere `__version__` em `capture/__init__.py`.
2. Acrescente um `<release version="X.Y.Z" date="AAAA-MM-DD">` **no topo** de
   `<releases>` em `data/io.github.kassiobraga.Capture.metainfo.xml` (descrição
   em inglês, curta).
3. Se a mudança aparece para o usuário: atualize README (Recursos, atalhos,
   Roadmap) e `flatpak/site/index.html` (cartões e roadmap).
4. Rode os testes (seção 4), faça commit e envie para a `main`; espere o build
   do push passar.
5. Crie e envie a tag anotada:
   ```sh
   git tag -a vX.Y.Z -m "Capture X.Y.Z" <commit>
   git push origin vX.Y.Z
   ```
6. Em ~3 min o workflow publica. Confira o release e rode `flatpak update`.

Valide o metainfo com `appstreamcli validate --no-net data/*.metainfo.xml`.

### Instalação manual (desenvolvimento)

`./install.sh` instala em `~/.local` (comando `~/.local/bin/capture`), e
`--bind-print` liga a tecla Print no Cinnamon. Exige no sistema: python3-gi,
GTK 4.12+, libadwaita 1.4+, e `python3-xlib` (ou `maim` + `xclip`). Não use as
duas instalações com a tecla Print ao mesmo tempo.

---

## 4. Testes

```sh
# unitarios, sem display (precisam de um python3 com PyGObject/GTK 4)
python3 -m unittest discover -s tests

# captura e area de transferencia reais num X virtual
xvfb-run -a python3 -m unittest tests.test_xlib

# ponta a ponta: controla o app instalado com mouse/teclado simulados (XTest)
CAPTURE_E2E=1 python3 -m unittest discover -s tests/e2e -t .
```

- Os e2e usam o lançador `~/.local/bin/capture` (ou `CAPTURE_BIN=<lançador>`,
  que precisa conter a linha `# capture-launcher: io.github.kassiobraga.Capture`),
  um id e uma pasta de saída próprios, e restauram a área de transferência.
  Precisam de `xclip`, `wmctrl`, `xprop`, `python-xlib` e de um gerenciador de
  janelas (no Xvfb, `openbox` + `dbus-run-session` funcionam).
- Num Xvfb, **1 teste falha sempre**:
  `test_arraste_que_comeca_sob_a_dica_gera_captura` dá 154 px em vez de 155. Ele
  falha igual em versões antigas; é diferença de arredondamento do ambiente, não
  regressão.
- Regra: toda funcionalidade nova ganha teste unitário no `Modelo`/módulos sem
  GTK e, quando mexe na interface, um e2e em `tests/e2e/`.

---

## 5. Decisões já tomadas (não reabrir sem falar com o Kassio)

- Distribuição: Flatpak com repositório próprio no GitHub Pages. Snap,
  AppImage e PPA foram descartados (Mint bloqueia Snap; GTK 4 empacota mal em
  AppImage; PPA só serve Debian/Ubuntu).
- Captura e área de transferência sem programas externos (libX11/python-xlib).
- Uma aba por captura; título "Captura N"; janela só cresce para caber uma
  imagem nova, nunca encolhe por causa de uma aba menor.
- Pixelar (e não borrar) para esconder dados: blocos grandes
  (`max(12, maior_lado/16)` px), como marcação apagável.
- Formato do "Salvar como" pela extensão; capturas automáticas sempre em PNG.
- Histórico (1.2): a opção "apagar no mesmo dia" **só limpa a lista**; os
  arquivos em `~/Imagens/Capturas` ficam.

---

## 6. Pendências imediatas

1. **Confirmar a correção das listras (1.1.1)** no PC do Kassio (Cinnamon +
   NVIDIA): com a janela do Capture aberta, apertar Print várias vezes sobre uma
   página com muito conteúdo. Se ainda aparecerem faixas com o papel de parede,
   a próxima hipótese é o compositor (Muffin) entregando um quadro parcial; a
   saída seria a captura pelo compositor (portal `Screenshot` ou D-Bus do
   Cinnamon) em vez de `XGetImage`.
2. **Prints do site e do README** (`docs/captura-*.png`) ainda são da 1.0, sem a
   barra de abas. Precisam ser refeitos num desktop real com compositor (sombra
   e fundo transparente): `docs/gerar_captura.py`, rodado no Mint do Kassio, com
   e sem `CAPTURE_TEMA=claro`.
3. Usuária Renata: instalar pelo link da página (se tiver a versão do arquivo
   antigo, desinstalar e reinstalar pelo link) e remover o Flameshot.

---

## 7. Flathub: atenção à política de IA

O Flathub tem uma
[política de IA generativa](https://docs.flathub.org/docs/for-app-authors/requirements#generative-ai-policy)
que proíbe IA no manifesto submetido, no pull request de submissão e nas
respostas aos revisores, e exige declarar o código gerado com IA (boa parte do
Capture foi escrita com IA). Também exige histórico de desenvolvimento e uso
real. **Um agente de IA não deve preparar nem abrir a submissão ao Flathub.**
Se um dia for feita, é trabalho manual do Kassio (detalhes em
`docs/FLATHUB.md`). O repositório próprio já cobre instalação em um clique e
atualização automática.

---

## 8. Roadmap (o que falta construir)

### 1.2: Histórico (próxima)

Painel lateral com as capturas feitas pelo Capture.

- Painel recolhível na lateral (ex.: `Adw.OverlaySplitView`, libadwaita 1.4+),
  com miniaturas, data e hora, ordenado da mais nova para a mais antiga.
- Ações por item: abrir numa aba nova, copiar, abrir a pasta, remover da lista.
- Registro em JSON no diretório de dados do app (`GLib.get_user_data_dir()`,
  que no Flatpak é `~/.var/app/io.github.kassiobraga.Capture/data`); miniaturas
  em cache (`GLib.get_user_cache_dir()`). Entradas cujo arquivo sumiu
  desaparecem da lista.
- Configuração de retenção: **manter o histórico** (padrão) ou **limpar a lista
  todo dia** (só a lista; os arquivos ficam, decisão do Kassio).
- **Modo anônimo**: a captura não entra no histórico. Confirmar com o Kassio se
  também não deve ser salva automaticamente em disco (ficaria só na área de
  transferência e na aba); a frase original foi "captura anônima, onde ele não
  salva no histórico".
- Preferências persistidas com `Gio.Settings` exige schema compilado; um JSON
  simples no diretório de configuração é mais fácil de empacotar.

### 1.3: Gravação de tela

- Gravar região, janela ou tela inteira, reaproveitando a seleção de `overlay.py`.
- Exportar MP4 e GIF. Codificadores precisam ir dentro do Flatpak: opções são
  GStreamer (`ximagesrc`, já no runtime GNOME) com o encoder certo, ou a
  extensão `org.freedesktop.Platform.ffmpeg-full` declarada no manifesto. MP4
  H.264 depende de codec que não vem no runtime base; verificar a licença e a
  extensão antes de escolher. GIF: gerar paleta (ffmpeg `palettegen` ou similar).
- Interface: botão de parar visível (fora da área gravada), contador de tempo,
  opção de áudio do sistema/microfone ficaria para depois.

### Depois: Wayland

Captura pelo `org.freedesktop.portal.Screenshot`/`ScreenCast`, sem a seleção
própria por cima das janelas (o portal mostra a dele). Permite retirar
`--socket=x11` do Flatpak quando a sessão for Wayland.

---

## 9. Como trabalhar neste repositório

- Branch principal: `main`. Versões publicadas são as tags `vX.Y.Z`; a tag
  `v1.0.0` é antiga (antes do Flatpak) e não deve ser movida.
- Commits pequenos, em português, com o porquê no corpo.
- Antes de commitar: testes unitários passando, metainfo válido e, se mexeu na
  interface, um teste rodando o app de verdade (Xvfb serve).
- Não adicionar permissões ao Flatpak sem necessidade clara, e documentar o
  motivo no próprio manifesto (como já é feito com cada `finish-arg`).
- O app é usado por pessoas não técnicas: mensagens claras em português,
  nada que exija terminal para o uso normal.
