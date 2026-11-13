# Atalho de teclado no Cinnamon (POSIX sh). Usado por install.sh e uninstall.sh:
#   . scripts/cinnamon.sh
# Mexe so na entrada do Capture; as demais entradas personalizadas ficam como estao.

CIN_SCHEMA=org.cinnamon.desktop.keybindings
CIN_KB_SCHEMA=org.cinnamon.desktop.keybindings.custom-keybinding
CIN_KB_PATH=/org/cinnamon/desktop/keybindings/custom-keybindings

cin_disponivel() {
    command -v gsettings >/dev/null 2>&1 && gsettings list-keys "$CIN_SCHEMA" >/dev/null 2>&1
}

# Entradas de custom-list, uma por linha.
cin_lista() {
    gsettings get "$CIN_SCHEMA" custom-list | sed "s/^@as //; s/[][' ]//g" | tr ',' '\n' | sed '/^$/d'
}

# Grava custom-list com os nomes recebidos como argumentos.
cin_grava_lista() {
    if [ $# -eq 0 ]; then
        v='[]'
    else
        v=
        for e in "$@"; do v="$v'$e', "; done
        v="[${v%, }]"
    fi
    gsettings set "$CIN_SCHEMA" custom-list "$v"
}

cin_get() { gsettings get "$CIN_KB_SCHEMA:$CIN_KB_PATH/$1/" "$2"; }
cin_set() { gsettings set "$CIN_KB_SCHEMA:$CIN_KB_PATH/$1/" "$2" "$3"; }

# Nome unico da entrada do Capture; so entradas com este nome E o comando exato
# "<lancador> --novo" sao consideradas nossas. Atalhos de outras pessoas nao sao tocados.
CIN_NOME="Capture (io.github.kassiobraga.Capture)"

# cin_eh_capture LANCADOR COMANDO NOME: valores como gsettings os imprime (entre aspas simples).
cin_eh_capture() {
    [ "$2" = "'$1 --novo'" ] && [ "$3" = "'$CIN_NOME'" ]
}

# A entrada E e a do Capture com este lancador?
cin_entrada_nossa() {
    cin_eh_capture "$1" "$(cin_get "$2" command)" "$(cin_get "$2" name)"
}

# O Cinnamon so recarrega os atalhos personalizados quando custom-list muda
# (e o que o painel de teclado dele faz). Muda e volta ao valor final. Se o
# processo for interrompido no meio, o trap grava o valor final antes de sair.
cin_recarrega() {
    CIN_FINAL="$*"
    # shellcheck disable=SC2064
    trap 'cin_grava_lista $CIN_FINAL; exit 130' INT TERM HUP
    gsettings set "$CIN_SCHEMA" custom-list "['__dummy__'$(for e in "$@"; do printf ", '%s'" "$e"; done)]"
    sleep "${CIN_ESPERA:-1}"
    cin_grava_lista "$@"
    trap - INT TERM HUP
}

# cin_vincula_print LANCADOR: cria ou atualiza a entrada do Capture com a tecla Print.
cin_vincula_print() {
    bin=$1
    entradas=$(cin_lista)
    alvo=
    for e in $entradas; do
        if cin_entrada_nossa "$bin" "$e"; then
            alvo=$e
            break
        fi
    done
    for e in $entradas; do
        [ "$e" = "$alvo" ] && continue
        if cin_get "$e" binding | grep -q "'Print'"; then
            echo "aviso: a entrada '$e' ($(cin_get "$e" name)) tambem usa Print." >&2
        fi
    done
    if gsettings get org.cinnamon.desktop.keybindings.media-keys screenshot 2>/dev/null | grep -q "'Print'"; then
        echo "aviso: o atalho de captura do proprio Cinnamon tambem usa Print (Configuracoes > Teclado)." >&2
    fi
    nova=0
    if [ -z "$alvo" ]; then
        n=0
        while printf '%s\n' "$entradas" | grep -qx "custom$n"; do n=$((n + 1)); done
        alvo=custom$n
        nova=1
    fi
    cin_set "$alvo" name "'$CIN_NOME'"
    cin_set "$alvo" command "'$bin --novo'"
    cin_set "$alvo" binding "['Print']"
    # shellcheck disable=SC2086
    set -- $entradas
    [ "$nova" = 1 ] && set -- "$@" "$alvo"
    cin_recarrega "$@"
    echo "Tecla Print vinculada a '$bin --novo' (entrada $alvo)."
}

# cin_desvincula LANCADOR: remove so a entrada do Capture; sem ela, nao mexe em nada.
cin_desvincula() {
    bin=$1
    restantes=
    removidas=
    for e in $(cin_lista); do
        if cin_entrada_nossa "$bin" "$e"; then
            removidas="$removidas $e"
        else
            restantes="$restantes $e"
        fi
    done
    [ -z "$removidas" ] && return 0
    for e in $removidas; do
        for k in name command binding; do
            gsettings reset "$CIN_KB_SCHEMA:$CIN_KB_PATH/$e/" "$k"
        done
    done
    # shellcheck disable=SC2086
    cin_recarrega $restantes
    echo "Atalho do Capture removido (${removidas# })."
}
