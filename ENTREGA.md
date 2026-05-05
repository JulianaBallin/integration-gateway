# Entrega Final — Projeto 5: Integration Gateway

Trabalho final do módulo **Gerenciamento Avançado de Containers**.

---

## Equipe

| Nome | GitHub |
|---|---|
| Allef Oliveira Ramos | [@allef-oliveira](https://github.com/allef-oliveira) |
| Fernanda de Oliveira da Costa | [@nanda-costa](https://github.com/nanda-costa) |
| Pedro Henrique Oliveira Dias | [@pedroddias-oss](https://github.com/pedroddias-oss) |
| Juliana Ballin Lima | [@JulianaBallin](https://github.com/JulianaBallin) |

---

## 1. Contexto do Problema

Empresas com sistemas legados frequentemente recebem dados externos em formatos variados que não são compatíveis com seus contratos internos. O **Integration Gateway** resolve esse problema criando uma camada intermediária que:

- Recebe pedidos externos via HTTP;
- Valida e transforma o payload para o contrato legado esperado;
- Encaminha para a API interna simulada;
- Persiste um registro de auditoria completo no banco de dados;
- Expõe endpoints de consulta para rastreabilidade de cada integração.

---

## 2. Arquitetura

```text
Cliente externo
      |
      v
 ┌─────────────┐   external_net + internal_net
 │  gateway-api │  ──────────────────────────▶ ┌─────────────┐   internal_net
 │  :8000       │                               │ transformer  │ ─────────────▶ ┌──────────────────┐
 └─────────────┘                               │  :8100       │                 │ internal-api-mock │
                                                └──────┬──────┘                 │  :8200            │
                                                       │ data_net               └──────────────────┘
                                                       v
                                               ┌─────────────┐
                                               │  postgres   │
                                               │  :5432      │
                                               └──────▲──────┘
                                                      │ data_net
                                               ┌──────┴──────┐   external_net
                                               │  audit-api  │ ◀─────────────── Cliente externo
                                               │  :8300       │
                                               └─────────────┘
```

### Fluxo de dados

1. Cliente envia `POST /integrations` para o **gateway-api**.
2. **gateway-api** encaminha o envelope (com `correlation_id`) para o **transformer**.
3. **transformer** valida, converte o payload para o contrato `LEGACY_ORDER_V1` e chama o **internal-api-mock**.
4. O resultado (sucesso ou falha) é gravado na tabela `integration_audit` no **postgres**.
5. **audit-api** permite consultar o histórico em `GET /audits` e `GET /audits/summary`.

---

## 3. Serviços

| Serviço | Imagem | Porta exposta | Função |
|---|---|---|---|
| `gateway-api` | build local | 8000 | Recebe `POST /integrations`, repassa ao transformer |
| `transformer` | build local | 8100 (interno) | Valida e transforma payload; grava auditoria |
| `internal-api-mock` | build local | 8200 (interno) | Simula sistema legado; valida contrato `LEGACY_ORDER_V1` |
| `postgres` | `postgres:15-alpine` | nenhuma | Persiste auditoria; não exposto ao host |
| `audit-api` | build local | 8300 | Consulta histórico de integrações |

---

## 4. Redes

| Rede | Tipo | Serviços participantes | Finalidade |
|---|---|---|---|
| `external_net` | bridge | `gateway-api`, `audit-api` | Tráfego de entrada/saída de clientes externos |
| `internal_net` | bridge | `gateway-api`, `transformer`, `internal-api-mock` | Comunicação interna entre serviços de integração |
| `data_net` | bridge | `transformer`, `audit-api`, `postgres` | Acesso exclusivo ao banco de dados |

O **postgres** não possui porta publicada para o host e não participa de `external_net`, garantindo que o banco só seja acessível pelos serviços autorizados.

---

## 5. Volumes

| Volume | Serviço | Finalidade |
|---|---|---|
| `postgres_data` | `postgres` | Persistência dos registros de auditoria entre reinicializações |
| `./db:/docker-entrypoint-initdb.d` | `postgres` | Bind mount para execução do script `init.sql` na criação do banco |

---

## 6. Healthchecks

| Serviço | Endpoint | Intervalo | Timeout | Retries |
|---|---|---|---|---|
| `gateway-api` | `GET /health` | 10s | 5s | 3 |
| `transformer` | `GET /health` | 10s | 5s | 3 |
| `internal-api-mock` | `GET /health` | 10s | 5s | 3 |
| `audit-api` | `GET /health` | 10s | 5s | 3 |
| `postgres` | `pg_isready` | 10s | 5s | 5 |

O transformer verifica conexão com o banco em seu `/health`, garantindo que só reporta `healthy` quando o postgres está acessível.

---

## 7. Limites de recursos

| Serviço | CPUs | Memória |
|---|---|---|
| `gateway-api` | 0.25 | 128m |
| `transformer` | 0.50 | 256m |
| `internal-api-mock` | 0.25 | 128m |
| `audit-api` | 0.25 | 128m |
| `postgres` | 0.50 | 256m |

---

## 8. Segurança (Hardening)

Aplicado nos serviços Python (`gateway-api`, `transformer`, `internal-api-mock`, `audit-api`):

| Configuração | Valor | Finalidade |
|---|---|---|
| `user` | `1000:1000` | Execução como usuário não-root |
| `read_only` | `true` | Filesystem da imagem somente leitura |
| `tmpfs` | `/tmp` | Diretório temporário em memória (necessário para alguns frameworks) |
| `cap_drop` | `ALL` | Remove todas as Linux capabilities |
| `security_opt` | `no-new-privileges:true` | Impede escalada de privilégios |

---

## 9. Como executar

### Pré-requisitos

- Docker Engine 24+
- Docker Compose v2

### Criar arquivo `.env`

```bash
cp .env.example .env
```

### Subir o ambiente

```bash
docker compose up -d --build
docker compose ps
```

### Aguardar todos os serviços ficarem healthy

```bash
docker compose ps
```

Todos os serviços devem aparecer com status `healthy` antes de iniciar os testes.

---

## 10. Como testar

### Verificar healthchecks

```bash
curl http://localhost:8000/health
curl http://localhost:8300/health
```

### Enviar payload válido

```bash
sh scripts/send_valid_order.sh
```

Payload enviado (`payloads/valid-order.json`):

```json
{
  "order_id": "EXT-2026-0001",
  "customer": { "code": "CUST-ALPHA", "name": "Alpha Manufacturing" },
  "items": [
    { "sku": "MB-001", "quantity": 10 },
    { "sku": "RAM-008", "quantity": 20 }
  ]
}
```

Resposta esperada (`201`):

```json
{
  "gateway": "accepted",
  "correlation_id": "demo-valid-001",
  "transformer_status": 201,
  "transformer_response": {
    "status": "success",
    "transformer_version": "stable-v1"
  }
}
```

### Enviar payload inválido

```bash
sh scripts/send_invalid_order.sh
```

Resposta esperada (`400`) — falha de validação no transformer antes de chegar ao sistema legado.

### Consultar auditoria

```bash
# Últimas 20 integrações
curl http://localhost:8300/audits

# Resumo por status e versão do transformer
curl http://localhost:8300/audits/summary

# Detalhe de uma integração específica
curl http://localhost:8300/audits/demo-valid-001
```

---

## 11. Incidente simulado e Troubleshooting

### Contexto do incidente

Uma nova versão do transformer (`broken-v2`) foi publicada com um bug de contrato: os campos enviados ao sistema legado estão com nomes errados (`sku`/`qty`/`order_id` em vez de `legacy_sku`/`legacy_qty`/`legacy_order_id`). O sistema legado rejeita todos os pedidos com `422 Unprocessable Entity`.

### Reproduzir o incidente

```bash
docker compose -f docker-compose.yml -f docker-compose.incident.yml up -d --build transformer
```

### Enviar payload e observar a falha

```bash
sh scripts/send_valid_order.sh
```

Resposta esperada com o transformer quebrado (`502`):

```json
{
  "gateway": "accepted",
  "transformer_status": 502,
  "transformer_response": {
    "status": "failed",
    "transformer_version": "broken-v2"
  }
}
```

### Diagnóstico

```bash
# Verificar qual versão está rodando
docker compose logs transformer | grep "version"

# Ver o payload que chegou ao sistema legado e o motivo da rejeição
docker compose logs internal-api-mock

# Confirmar falhas registradas na auditoria
curl http://localhost:8300/audits/summary
```

Sinais no log do `internal-api-mock`:

```
[internal-api-mock] rejected missing=['legacy_order_id', 'legacy_customer_code', 'legacy_total_items', 'legacy_items'] payload={...}
```

Sinais no log do `transformer`:

```
[transformer] FAILED correlation_id=... internal_status=422
```

### Rollback e correção

Restaurar a versão estável:

```bash
docker compose up -d --build transformer
```

Validar que o serviço voltou à versão correta:

```bash
docker compose logs transformer | grep "version=stable-v1"
curl http://localhost:8000/health
```

Enviar payload válido novamente e confirmar sucesso:

```bash
sh scripts/send_valid_order.sh
curl http://localhost:8300/audits/summary
```

O resumo mostrará registros `FAILED` (transformer_version: `broken-v2`) e registros `SUCCESS` (transformer_version: `stable-v1`), comprovando que a auditoria rastreia toda a linha do tempo do incidente.

---

## 12. Evidências obrigatórias

Execute os comandos abaixo e registre as saídas como evidências da entrega:

```bash
# Serviços em execução
docker compose ps

# Redes criadas
docker network ls
docker network inspect integration-gateway_external_net
docker network inspect integration-gateway_internal_net
docker network inspect integration-gateway_data_net

# Volumes persistentes
docker volume ls
docker volume inspect integration-gateway_postgres_data

# Logs dos serviços principais
docker compose logs gateway-api
docker compose logs transformer
docker compose logs internal-api-mock
docker compose logs audit-api

# Healthchecks e endpoints
curl http://localhost:8000/health
curl http://localhost:8300/health
curl http://localhost:8300/audits
curl http://localhost:8300/audits/summary

# Limites de recursos e hardening (checar nos containers Python)
docker inspect integration-gateway-transformer-1
```

No `docker inspect` do transformer, confirmar:

```json
"Memory": <valor diferente de 0>,
"NanoCpus": <valor diferente de 0>,
"ReadonlyRootfs": true,
"CapDrop": ["ALL"],
"SecurityOpt": ["no-new-privileges:true"]
```

---

## 13. Respostas às perguntas do projeto

**1. Por que o Postgres não deve estar na rede externa?**
O banco contém dados sensíveis de auditoria. Expô-lo à rede externa aumentaria a superfície de ataque. Apenas os serviços que precisam acessar o banco (`transformer` e `audit-api`) estão em `data_net`.

**2. Por que o Gateway precisa estar em duas redes?**
O `gateway-api` precisa receber requisições externas (`external_net`) e ao mesmo tempo encaminhar para o `transformer`, que está isolado na rede interna (`internal_net`). Ele atua como ponto de fronteira controlado.

**3. Qual serviço é responsável por conhecer o contrato legado?**
O `transformer`. Ele converte o payload externo para o formato `LEGACY_ORDER_V1` esperado pelo `internal-api-mock`. Qualquer mudança de contrato deve ser implementada nele.

**4. Como a falha de contrato foi identificada pelos logs?**
O `internal-api-mock` loga exatamente quais campos estão ausentes (`missing=['legacy_order_id', ...]`). O `transformer` loga o status HTTP de rejeição (`internal_status=422`). A combinação dos dois logs torna o diagnóstico imediato.

**5. Como a auditoria ajudou na análise do incidente?**
O endpoint `/audits/summary` agrupou registros por `status` e `transformer_version`, deixando claro quando os erros começaram (`broken-v2`) e quando foram resolvidos (`stable-v1`). O endpoint `/audits/<correlation_id>` permitiu inspecionar o payload exato de cada falha.

**6. O rollback corrigiu as integrações já registradas como falha?**
Não. Os registros de falha permanecem na auditoria como histórico imutável. O rollback só corrige integrações futuras. Isso é intencional: a auditoria serve como prova do ocorrido.

**7. Qual a importância de versionar contratos entre serviços?**
Sem versionamento, uma mudança silenciosa num serviço quebra outros sem deixar rastro claro da causa. O campo `transformer_version` na auditoria permite correlacionar falhas com versões específicas do código.

**8. Quais evidências comprovam que os limites e hardening foram aplicados?**
O `docker inspect` dos containers Python exibe `ReadonlyRootfs: true`, `CapDrop: ["ALL"]`, `SecurityOpt: ["no-new-privileges:true"]`, além dos valores de `Memory` e `NanoCpus` diferentes de zero.

---

## 14. Remover o ambiente

```bash
# Para os containers
docker compose down

# Para os containers e remove os volumes (apaga dados de auditoria)
docker compose down -v
```
