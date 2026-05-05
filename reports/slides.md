# Integration Gateway
## Gerenciamento Avançado de Containers — Trabalho Final

**Projeto 5 | Turma 2026**

---

## Slide 1 — Equipe

| Nome | GitHub |
|---|---|
| Allef Oliveira Ramos | [@allef-oliveira](https://github.com/allef-oliveira) |
| Fernanda de Oliveira da Costa | [@nanda-costa](https://github.com/nanda-costa) |
| Pedro Henrique Oliveira Dias | [@pedroddias-oss](https://github.com/pedroddias-oss) |
| Juliana Ballin Lima | [@JulianaBallin](https://github.com/JulianaBallin) |
| Camila Felix dos Reis | [@cawzkf](https://github.com/cawzkf) |

---

## Slide 2 — Contexto do Problema

Empresas com sistemas legados recebem dados externos em formatos incompatíveis com seus contratos internos.

**Solução:** Uma camada intermediária que:
- Recebe pedidos externos via HTTP
- Valida e transforma o payload para o contrato legado
- Encaminha para a API interna
- Registra auditoria completa no banco
- Expõe consultas de rastreabilidade

---

## Slide 3 — Arquitetura Geral

```
Cliente Externo
      |
      v
 gateway-api :8000       (external_net + internal_net)
      |
      v
 transformer :8100       (internal_net + data_net)
    /    \
   v      v
internal   postgres :5432
-api-mock  (data_net)
:8200
(internal_net)
      ^
      |
 audit-api :8300         (external_net + data_net)
      |
      v
Cliente Externo (consulta)
```

---

## Slide 4 — Serviços

| Serviço | Imagem | Porta Host | Função |
|---|---|---|---|
| `gateway-api` | build local | 8000 | Ponto de entrada externo |
| `transformer` | build local | interno | Valida, transforma e audita |
| `internal-api-mock` | build local | interno | Simula sistema legado |
| `postgres` | postgres:15-alpine | **nenhuma** | Persistência de auditoria |
| `audit-api` | build local | 8300 | Consulta de histórico |

**Postgres sem porta exposta** — acessível apenas via `data_net`.

---

## Slide 5 — Redes (Isolamento)

| Rede | Serviços | Finalidade |
|---|---|---|
| `external_net` | gateway-api, audit-api | Tráfego externo controlado |
| `internal_net` | gateway-api, transformer, internal-api-mock | Comunicação interna |
| `data_net` | transformer, audit-api, postgres | Banco isolado |

**Por que o gateway precisa de 2 redes?**
Ele é a fronteira: recebe de fora (`external_net`) e repassa internamente (`internal_net`).

**Por que o Postgres não está na external_net?**
Dados sensíveis de auditoria não devem ser expostos. Apenas os serviços autorizados acessam via `data_net`.

---

## Slide 6 — Volumes e Persistência

| Volume | Tipo | Finalidade |
|---|---|---|
| `postgres_data` | named volume | Auditoria persiste entre reinicializações |
| `./db/init.sql` | bind mount | Script de inicialização do banco |

---

## Slide 7 — Healthchecks

| Serviço | Endpoint | Intervalo | Timeout | Retries |
|---|---|---|---|---|
| gateway-api | GET /health | 10s | 5s | 3 |
| transformer | GET /health | 10s | 5s | 3 |
| internal-api-mock | GET /health | 10s | 5s | 3 |
| audit-api | GET /health | 10s | 5s | 3 |
| postgres | pg_isready | 10s | 5s | 5 |

O `transformer` verifica a conexão com o banco em seu `/health` — só reporta `healthy` quando o postgres está acessível.

**`depends_on` com `condition: service_healthy`** garante a ordem de inicialização.

---

## Slide 8 — Limites de Recursos

| Serviço | CPUs | Memória |
|---|---|---|
| gateway-api | 0.25 | 128m |
| transformer | 0.50 | 256m |
| internal-api-mock | 0.25 | 128m |
| audit-api | 0.25 | 128m |
| postgres | 0.50 | 256m |

Configurado via `deploy.resources.limits` no Compose.

---

## Slide 9 — Hardening (Segurança)

Aplicado nos 4 serviços Python:

| Configuração | Valor | Finalidade |
|---|---|---|
| `user` | `1000:1000` | Não roda como root |
| `read_only: true` | filesystem somente leitura | Impede escrita no container |
| `tmpfs: /tmp` | diretório temporário em memória | Escrita permitida apenas em /tmp |
| `cap_drop: ALL` | remove todas as capabilities Linux | Princípio do menor privilégio |
| `security_opt: no-new-privileges:true` | impede escalada de privilégios | Proteção adicional |

**Evidência pelo `docker inspect`:**
```
Memory: 268435456   (≠ 0) ✓
NanoCpus: 500000000 (≠ 0) ✓
ReadonlyRootfs: true ✓
CapDrop: ["ALL"] ✓
SecurityOpt: ["no-new-privileges:true"] ✓
```

---

## Slide 10 — Demo: Fluxo Normal

**1. Subir ambiente**
```bash
docker compose up -d --build
docker compose ps  # todos healthy
```

**2. Healthchecks**
```bash
curl http://localhost:8000/health  # gateway-api: healthy
curl http://localhost:8300/health  # audit-api: healthy
```

**3. Payload válido → 201**
```bash
sh scripts/send_valid_order.sh
# transformer_version: stable-v1, status: success
```

**4. Payload inválido → 400**
```bash
sh scripts/send_invalid_order.sh
# error: missing required external fields: ['order_id']
```

**5. Consultar auditoria**
```bash
curl http://localhost:8300/audits/summary
# SUCCESS: 3 | stable-v1
```

---

## Slide 11 — Incidente: transformer broken-v2

**Contexto:** Nova versão do transformer publicada com bug de contrato.

O `broken-v2` envia campos errados ao sistema legado:
- Envia: `order_id`, `items`, `sku`, `qty`
- Legado espera: `legacy_order_id`, `legacy_items`, `legacy_sku`, `legacy_qty`

**Reproduzir:**
```bash
docker compose -f docker-compose.yml -f docker-compose.incident.yml up -d --build transformer
sh scripts/send_valid_order.sh
# → 502: transformer_version: broken-v2, status: failed
```

---

## Slide 12 — Diagnóstico pelo Log

**Log do transformer:**
```
[transformer] starting on port 8100 version=broken-v2
[transformer] FAILED correlation_id=demo-valid-001 internal_status=422
```

**Log do internal-api-mock:**
```
[internal-api-mock] rejected missing=['legacy_order_id', 'legacy_customer_code',
'legacy_total_items', 'legacy_items'] payload={...}
```

**Auditoria:**
```bash
curl http://localhost:8300/audits/summary
# FAILED | broken-v2: 1 registro
```

**Causa raiz:** campos renomeados sem atualizar o contrato legado — violação do `LEGACY_ORDER_V1`.

---

## Slide 13 — Rollback e Correção

**Restaurar versão estável:**
```bash
docker compose up -d --build transformer
# → versão stable-v1 volta ao ar
```

**Validar:**
```bash
docker compose logs transformer | grep "version=stable-v1"
sh scripts/send_valid_order.sh
# → 201: transformer_version: stable-v1, status: success

curl http://localhost:8300/audits/summary
# SUCCESS | stable-v1: 4 registros
# FAILED  | broken-v2: 1 registro  (histórico imutável)
```

**Os registros de falha NÃO foram corrigidos** — auditoria é imutável, serve como prova do ocorrido.

---

## Slide 14 — Como a Auditoria Ajudou

O `audit-api` com o endpoint `/audits/summary` agrupou registros por `status` e `transformer_version`:

| status | transformer_version | total |
|---|---|---|
| SUCCESS | stable-v1 | 4 |
| FAILED | broken-v2 | 1 |
| FAILED | stable-v1 | 1 |

Isso deixou claro:
- **Quando** os erros começaram (`broken-v2`)
- **Quando** foram resolvidos (`stable-v1` voltou)
- **O quê** falhou: contrato legado violado

O `docker inspect` confirma que os limites e hardening foram aplicados corretamente.

---

## Slide 15 — Respostas às Perguntas do Projeto

**1. Por que o Postgres não deve estar na rede externa?**
Dados sensíveis de auditoria não devem ser expostos. Apenas `transformer` e `audit-api` acessam via `data_net`.

**2. Por que o Gateway precisa de duas redes?**
Ele é a fronteira: recebe de `external_net` e repassa via `internal_net`. Sem as duas, não consegue fazer a ponte.

**3. Qual serviço conhece o contrato legado?**
O `transformer`. Qualquer mudança de contrato deve ser implementada nele e testada antes do deploy.

**4. Como a falha foi identificada pelos logs?**
`internal-api-mock` logou os campos ausentes. `transformer` logou `internal_status=422`. A combinação torna o diagnóstico imediato.

**5. O rollback corrigiu as integrações já registradas como falha?**
Não. Os registros de falha são histórico imutável. O rollback corrige apenas integrações futuras — isso é intencional.

**6. Qual a importância de versionar contratos?**
Sem `transformer_version` na auditoria, seria impossível correlacionar falhas com versões específicas do código.

---

## Slide 16 — Aprendizados Principais

- Isolamento de redes por responsabilidade evita exposição desnecessária
- `depends_on` com healthcheck garante inicialização segura
- Auditoria com `transformer_version` é fundamental para rastrear incidentes
- Hardening (`read_only`, `cap_drop`, `no-new-privileges`) é configurável no Compose
- Rollback rápido é possível porque o `docker-compose.incident.yml` sobrescreve apenas o `build` do transformer
- Logs estruturados (`[serviço] campo=valor`) permitem diagnóstico sem acesso direto ao banco
