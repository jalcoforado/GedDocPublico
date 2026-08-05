#!/usr/bin/env bash
# Fecha na internet as portas de banco/backend/frontend publicadas por container.
#
# Defesa em profundidade. A barreira principal é o `docker-compose.yml`, que
# desde 2026-08-05 publica tudo em `127.0.0.1:` menos a 8090 do nginx
# (`tests/test_guarda_portas_publicadas.py`). Isto aqui existe porque a
# barreira principal é um arquivo que alguém pode editar — inclusive o
# `docker-compose.override.yml`, que é gitignored e está fora do alcance da
# guarda.
#
# Duas armadilhas que custaram diagnóstico, e que explicam por que o script tem
# a forma que tem:
#
# - **`ufw` não alcança porta publicada por container.** O Docker insere DNAT
#   em `PREROUTING`, que desvia do `INPUT` inteiro. Regra de bloqueio tem de ir
#   na chain `DOCKER-USER`.
# - **O DNAT reescreve a porta ANTES da `DOCKER-USER`.** Por isso a lista tem
#   `3000` e não só `3100`: o mapeamento é `3100:3000`, e a regra precisa casar
#   a porta de DENTRO do container. Foi por não saber disso que a 3100
#   continuou aberta depois da primeira tentativa.
#
# Instalação (a unidade aponta para /usr/local/sbin, NÃO para o repositório —
# firewall de máquina não deve depender de o clone estar presente ou num
# commit específico):
#
#     install -m 755 deploy/vps/aprimora-fecha-portas.sh /usr/local/sbin/
#     cp deploy/systemd/aprimora-fecha-portas.service /etc/systemd/system/
#     systemctl daemon-reload && systemctl enable --now aprimora-fecha-portas
set -euo pipefail

# Portas do LADO DE DENTRO do container (ver a segunda armadilha abaixo), mais
# as publicadas onde as duas coincidem. Tem de cobrir todo serviço do compose
# que não seja a entrada pública — `test_guarda_portas_publicadas.py` cruza esta
# lista com o `docker-compose.yml` e reprova quem publicar serviço novo sem
# acrescentá-lo aqui. O 6379 entrou por essa via: estava a salvo pelo bind em
# `127.0.0.1`, mas fora desta camada.
PORTAS="${PORTAS:-5432 8000 3000 3100 6379}"

# A interface externa. Era literal `eth0`, e essa era a falha silenciosa desta
# camada: regra inserida com `-i <interface inexistente>` é aceita pelo
# iptables sem reclamar e **nunca casa pacote nenhum**. O `systemctl status`
# ficaria verde, `iptables -L` mostraria as quatro regras, e as portas estariam
# abertas. Aqui a interface é descoberta pela rota default e, se não existir, o
# script FALHA — porque unidade vermelha é o único sintoma que alguém vê.
IFACE="${IFACE:-$(ip route show default | awk '/^default/ {print $5; exit}')}"
[ -n "$IFACE" ] || { echo "[ERRO] não achei a interface da rota default." >&2; exit 1; }
ip link show "$IFACE" >/dev/null 2>&1 \
  || { echo "[ERRO] interface '$IFACE' não existe; as regras não casariam nada." >&2; exit 1; }

echo "Interface externa: $IFACE"

for porta in $PORTAS; do
  for cmd in iptables ip6tables; do
    # Remove antes de inserir, para não empilhar uma cópia a cada boot.
    while "$cmd" -C DOCKER-USER -i "$IFACE" -p tcp --dport "$porta" -j DROP 2>/dev/null; do
      "$cmd" -D DOCKER-USER -i "$IFACE" -p tcp --dport "$porta" -j DROP
    done
    "$cmd" -I DOCKER-USER 1 -i "$IFACE" -p tcp --dport "$porta" -j DROP
  done
done

# Controle positivo: confere que as regras existem depois de inseridas. Sem
# isto, um `iptables` que aceitasse a inserção e não a aplicasse passaria
# despercebido — e o modo de falha desta camada é justamente parecer instalada.
for porta in $PORTAS; do
  for cmd in iptables ip6tables; do
    "$cmd" -C DOCKER-USER -i "$IFACE" -p tcp --dport "$porta" -j DROP 2>/dev/null \
      || { echo "[ERRO] regra $cmd/$porta não está presente depois da inserção." >&2; exit 1; }
  done
done

echo "OK — $(echo "$PORTAS" | wc -w) porta(s) bloqueadas em $IFACE (IPv4 e IPv6)."
