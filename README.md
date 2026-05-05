# Integration Gateway

Projeto final para avaliação do curso **Gerenciamento Avançado de Containers**.

## 1. Contexto

Uma empresa possui sistemas legados que recebem dados em formatos diferentes. O **Integration Gateway** recebe payloads externos, transforma para um contrato interno legado, encaminha para uma API interna simulada e mantém auditoria no banco.

---

## 2. Arquitetura

```text
Cliente externo
      |
      v
Gateway API  ───▶ Transformer ───▶ Internal API Mock
                       |
                       v
                   PostgreSQL
                       ^
                       |
                   Audit API
```

## 3. Serviços

| Serviço | Função |
|---|---|
| `gateway-api` | Recebe `POST /integrations` e repassa para o transformer |
| `transformer` | Normaliza o payload e chama a API interna |
| `internal-api-mock` | Simula sistema legado e valida contrato |
| `postgres` | Persiste auditoria |
| `audit-api` | Consulta histórico das integrações |

---

## 4. Redes

| Rede | Serviços | Finalidade |
|---|---|---|
| `external_net` | gateway-api, audit-api | Acesso externo controlado |
| `internal_net` | gateway-api, transformer, internal-api-mock | Integração interna entre serviços |
| `data_net` | transformer, audit-api, postgres | Persistência e auditoria |

O Postgres não possui porta publicada para o host.

---

## 5. Como executar (após a construção do docker-compose.yml)

### Criar `.env`

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

### Subir ambiente

```bash
docker compose up -d --build
docker compose ps
```

---

## 6. Como testar

### Healthchecks

```bash
curl http://localhost:8000/health
curl http://localhost:8300/health
```

### Enviar payload válido

```bash
sh scripts/send_valid_order.sh
```

PowerShell:

```powershell
.\scripts\send_valid_order.ps1
```

### Enviar payload inválido

```bash
sh scripts/send_invalid_order.sh
```

PowerShell:

```powershell
.\scripts\send_invalid_order.ps1
```

### Consultar auditoria

```bash
curl http://localhost:8300/audits
curl http://localhost:8300/audits/summary
curl http://localhost:8300/audits/demo-valid-001
```

---

## 7. Incidente obrigatório

### Subir incidente

```bash
docker compose -f docker-compose.yml -f docker-compose.incident.yml up -d --build transformer
```

### Enviar payload válido novamente

```bash
sh scripts/send_valid_order.sh
```

### Diagnosticar

```bash
docker compose logs -f transformer
docker compose logs -f internal-api-mock
curl http://localhost:8300/audits
curl http://localhost:8300/audits/summary
```

- Espera-se que a equipe identifique qual serviço está falhando.
- Dica: olhar os logs dos serviços.


### Correção
Espera-se que a equipe identifique o problema e realize a correção apropriada.

Após correção, enviar payload válido novamente e validar sucesso:

```bash
sh scripts/send_valid_order.sh
curl http://localhost:8300/audits/summary
```

---

## 8. Evidências obrigatórias

A equipe deve entregar prints ou saídas de:

```bash
docker compose ps
docker network ls
docker volume ls
docker compose logs gateway-api
docker compose logs transformer
docker compose logs internal-api-mock
curl http://localhost:8000/health
curl http://localhost:8300/audits
curl http://localhost:8300/audits/summary
docker inspect <container_python>
```

No `docker inspect`, procurar:

```json
"Memory": != 0,
"NanoCpus": != 0,
"ReadonlyRootfs": true,
"CapDrop": ["ALL"],
"SecurityOpt": ["no-new-privileges:true"]
```

---

## 9. Perguntas sobre o projeto

1. Por que o Postgres não deve estar na rede externa?
2. Por que o Gateway precisa estar em duas redes?
3. Qual serviço é responsável por conhecer o contrato legado?
4. Como a falha de contrato foi identificada pelos logs?
5. Como a auditoria ajudou na análise do incidente?
6. O rollback corrigiu as integrações já registradas como falha?
7. Qual a importância de versionar contratos entre serviços?
8. Quais evidências comprovam que os limites e hardening foram aplicados?

---

## 10. Remover ambiente

```bash
docker compose down
```

Remover dados:

```bash
docker compose down -v
```
