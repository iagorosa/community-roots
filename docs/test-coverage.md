# Revisão de lacunas de cobertura de teste

Levantamento feito para a issue #40 (Fase 7 — Polimento), rodando a suíte real
contra o estado do repositório em 2026-09-01. Os números abaixo são a saída
real dos comandos, não uma estimativa — reproduza com os comandos de cada
seção.

## Backend

```bash
cd backend
source .venv/bin/activate
uv pip install pytest-cov   # não é uma dependência do projeto — ver nota abaixo
pytest --cov=app --cov-report=term-missing
```

Resultado: **222 testes passando, 98% de cobertura de linha** (952
statements, 20 não cobertos).

| Módulo | Cobertura | Linhas não cobertas |
|---|---|---|
| `app/api/routes/health.py` | 76% | 30–36 |
| `app/db/session.py` | 64% | 24–28 |
| `app/storage/dependency.py` | 57% | 25–28 |
| `app/services/planting_service.py` | 96% | 127, 173, 185 |
| `app/services/qr_service.py` | 96% | 128 |
| `app/services/region_service.py` | 96% | 145, 157, 188, 283 |
| `app/storage/local.py` | 95% | 63 |
| todos os outros módulos | 100% | — |

O que cada lacuna é, de verdade (lido módulo a módulo, não só pela
porcentagem):

- **`health.py` 30–36 — o ramo de banco fora do ar.** É o `except
  SQLAlchemyError` de `GET /health`, que devolve `503` e
  `{"status": "degraded"}` quando o `SELECT 1` falha. Nenhum teste simula uma
  conexão quebrada para exercitar esse ramo — é o teste mais realista de
  todos que faltam, porque é justamente o cenário em que alguém vai olhar
  para esse endpoint pra valer (um monitoramento de produção). Vale um teste
  que sobrescreva `get_db` para levantar `SQLAlchemyError`, como já é feito em
  `tests/conftest.py` para outros cenários de dependência.
- **`session.py` 24–28 — o corpo do gerador `get_db`.** `yield`/`db.close()`
  só rodam dentro do ciclo de vida de uma request real; a suíte usa uma
  sessão de teste isolada (`tests/conftest.py`) para não depender do pool de
  conexão de produção, então esse caminho específico nunca executa sob
  `pytest`. Baixo risco — é código de três linhas, sem lógica condicional.
- **`storage/dependency.py` 25–28 — a seleção de backend de storage.** O
  `if settings.storage_backend == "local"` e o `NotImplementedError` do
  `else` nunca são exercitados porque todo teste sobrescreve a dependência
  diretamente (`app.dependency_overrides`), sem passar por
  `get_storage_backend`. Como `storage_backend` é hoje `Literal["local"]`
  (arquitetura §6), o `else` é também inatingível pela aplicação real — vale
  cobrir se um segundo backend (S3) for adicionado, não antes.
- **`planting_service.py` 127/173, `region_service.py` 145/157 — corridas de
  "sumiu entre o `flush` e o fetch".** São os `raise *NotFound` dentro de
  `_fetch_feature_by_id`/`update_planting`/`_resolve_region_id`, alcançáveis
  só se a linha desaparecer entre ser criada/localizada e ser relida na mesma
  transação — não acontece na prática dado o fluxo atual (sem exclusão
  concorrente no meio de um único request). Defensivo, não um buraco real.
- **`planting_service.py` 185, `region_service.py` 283 (mesmo padrão em
  `qr_service.py` 128) — ramos definidos por tipo, não por dado.** O primeiro
  é a atualização de geometria num `PATCH` só com esse campo isolado (as
  combinações testadas sempre misturam geometria com outro campo); o segundo
  é o `ValueError` de `qr_service.generate_qr_code` para um `format` fora de
  `"png"/"svg"` — inatingível pela rota, que já restringe `format` via
  `Literal["png", "svg"]` do Pydantic antes de chegar aqui (o comentário no
  próprio código já documenta isso). Nenhum dos dois é um cenário de uso
  real hoje.
- **`storage/local.py` 63 — `LocalFilesystemStorage.delete()`.** O método
  existe na interface `StorageBackend`, mas nenhum caminho do app hoje chama
  `delete()` (a foto "escondida" continua no disco — ver
  [`docs/architecture.md` §4.5](./architecture.md)). É a única lacuna que é
  literalmente **código sem nenhum chamador nem teste**, não um ramo raro de
  um caminho testado. Se `delete()` continuar sem uso, vale avaliar removê-lo
  em vez de deixá-lo sem cobertura indefinidamente.

**Nota sobre `pytest-cov`:** não é uma dependência do projeto (não está em
`[project.optional-dependencies].dev` no `backend/pyproject.toml`) — o comando
acima instala-o pontualmente no ambiente virtual local, sem alterar
`pyproject.toml`/`uv.lock`. Quem quiser repetir essa medição precisa do mesmo
passo `uv pip install pytest-cov`.

## Frontend

```bash
cd frontend
npm run test -- --run   # a suíte roda normalmente
npm run test -- --coverage --run   # mas cobertura não está configurada
```

A suíte roda limpa: **34 arquivos de teste, 137 testes passando**. Mas não há
uma métrica de cobertura de linha disponível — `npm run test -- --coverage`
falha imediatamente com:

```
MISSING DEPENDENCY  Cannot find dependency '@vitest/coverage-v8'
```

Nem `@vitest/coverage-v8` nem `@vitest/coverage-istanbul` estão em
`frontend/package.json`. Isso é uma lacuna de ferramental, não só de teste: os
137 testes existentes cobrem os componentes e hooks mais centrais (mapa,
timeline de fotos, formulário de envio, resolução de QR) a julgar pelos nomes
dos arquivos em `frontend/src/**/*.test.tsx`, mas sem um provedor de
cobertura instalado não é possível medir, com números reais, o que ficou de
fora — só listar por inspeção, o que este documento evita fazer para não
inventar uma porcentagem sem medi-la de verdade.

## Lacunas funcionais conhecidas (fora do escopo de teste)

Uma lacuna foi encontrada durante este levantamento que não é sobre cobertura
de teste, mas sobre funcionalidade ausente — registrada como issue à parte,
não corrigida nesta issue de documentação:

- [Issue #135](https://github.com/iagorosa/community-roots/issues/135) —
  folha imprimível de QR Codes (a issue original, #32, foi fechada sem
  implementação quando o modelo Region/Planting mudou).
