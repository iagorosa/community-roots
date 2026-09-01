# Community Roots

Um projeto comunitário de educação ambiental. Crianças, adolescentes e vizinhos
plantam sementes numa área compartilhada da cidade e acompanham como essas plantas
crescem ao longo do tempo.

A aplicação é o gêmeo digital dessa área física: um mapa interativo dos canteiros,
um QR Code em cada canteiro no local, e uma linha do tempo de fotos mostrando o
desenvolvimento de cada um.

```
Placa no canteiro  ->  QR Code  ->  canteiro digital  ->  linha do tempo de fotos
```

Área de referência: **Matias Barbosa, Minas Gerais**.

---

## Situação do projeto

O MVP original (Fases 0–7) está concluído. Depois dele, o modelo de dados
passou por um pivô: o antigo "canteiro" (um único `Planting` por área) virou
dois conceitos — `Region` (a área/canteiro físico) e `Planting` (cada muda
individual dentro dela). O pivô do frontend (Fase 9) também está concluído;
restam 2 issues abertas de acabamento no backend (milestone "Fase 8").

| Fase | Descrição | Situação |
|---|---|---|
| 0 | Planejamento e documentação | concluída |
| 1 | Fundação do projeto | concluída |
| 2 | Canteiros | concluída |
| 3 | Mapa interativo | concluída |
| 4 | Páginas de canteiro | concluída |
| 5 | Envio de fotos | concluída |
| 6 | QR Codes | concluída |
| 7 | Polimento | concluída |
| 8 | Pivô Region/Planting — backend | em andamento (2 issues abertas) |
| 9 | Pivô Region/Planting — frontend | concluída |

As instruções de instalação abaixo funcionam de ponta a ponta: banco de dados,
backend, frontend e o passo opcional de dados de desenvolvimento (seed).

O backlog fica nas [issues](https://github.com/iagorosa/community-roots/issues),
organizadas por [milestone](https://github.com/iagorosa/community-roots/milestones)
— um milestone por fase.

Para entender o projeto por dentro:

- [docs/architecture.md](docs/architecture.md) — a arquitetura e o porquê de cada
  decisão.
- [docs/implementation-plan.md](docs/implementation-plan.md) — as fases, os
  entregáveis e os critérios de validação.
- [PROJECT_BOOTSTRAP.md](PROJECT_BOOTSTRAP.md) — a especificação do produto.

---

## Tecnologias

**Frontend** — React 19.2.8, Vite 8.2.2, TypeScript 6.0.2, Tailwind CSS 4.3.3
(via `@tailwindcss/vite`, sem `tailwind.config.js`), React Leaflet 5.0.0 +
Leaflet 1.9.4, React Router 8.3.1, TanStack Query 5.102.8. Versões exatas
fixadas em `frontend/package.json`.

**Backend** — Python 3.11, FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Pydantic v2,
Alembic.

**Banco de dados** — PostgreSQL 16 com PostGIS 3.4, em Docker.

Os tiles do mapa vêm do OpenStreetMap. Nenhum serviço pago e nenhuma API key são
necessários para rodar o projeto.

---

## Requisitos

| Ferramenta | Versão | Observação |
|---|---|---|
| Docker + Compose | qualquer recente | Roda apenas o banco de dados |
| Python | 3.11.10 | Fixada em `backend/.python-version` |
| Node.js | 22.22.1 | Fixada em `frontend/.nvmrc` |

O `pyenv` e o `nvm` reconhecem essas versões automaticamente.
Nenhum pacote npm global é necessário.

---

## Instalação

### 1. Banco de dados

```bash
cp .env.example .env          # ajuste POSTGRES_PASSWORD
docker compose up -d
docker compose ps             # aguarde o status "healthy"
```

O container expõe a porta definida em `POSTGRES_PORT` (padrão `5432`). Troque se
essa porta já estiver ocupada na sua máquina. No primeiro start, o script de
inicialização habilita o PostGIS e cria o banco `community_roots_test`, usado pela
suíte de testes.

### 2. Backend

```bash
cd backend
cp .env.example .env           # a DATABASE_URL precisa bater com o .env da raiz
pyenv install --skip-existing 3.11.10

uv venv && source .venv/bin/activate
uv sync --extra dev             # --extra dev traz pytest e ruff também

alembic upgrade head
uvicorn app.main:app --reload
```

Sem o `uv`, o equivalente é:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

- API: <http://localhost:8000>
- Documentação interativa: <http://localhost:8000/docs>
- Verificação de saúde: <http://localhost:8000/health>

### 3. Frontend

```bash
cd frontend
cp .env.example .env
nvm use                        # lê o .nvmrc
npm install
npm run dev
```

Abra <http://localhost:5173>. Em desenvolvimento, `/api` e `/health` são
redirecionados para o backend pelo proxy do Vite, então há uma origem só e
nenhum CORS para configurar. A página inicial já mostra o status ao vivo de
`/health`, confirmando que frontend, backend e banco estão conectados.

### 4. Dados de desenvolvimento

```bash
cd backend
python scripts/seed.py
```

Isso cria uma única `Region` (a AAMA — Matias Barbosa) ao redor de
`SEED_CENTER_LAT`/`SEED_CENTER_LON`, com `SEED_PLANTING_COUNT` `Planting`s
(mudas) distribuídas em grade dentro dela, cada uma com um `nickname`
fictício. **A geometria é um placeholder** — os polígonos reais serão
importados quando o geógrafo entregar o levantamento. Rodar o script de novo não
duplica nada: ele reconhece a região pelo slug e só completa as mudas que
ainda faltarem.

---

## Comandos do dia a dia

```bash
# Backend
pytest                                   # testes
ruff check . && ruff format .            # lint e formatação
alembic revision --autogenerate -m "..." # nova migration (sempre revise antes)
alembic upgrade head                     # aplica as migrations
python scripts/seed.py                   # dados de desenvolvimento

# Frontend
npm run dev
npm run build
npm run test
npm run lint

# Banco de dados
docker compose up -d
docker compose logs -f db
docker compose down                      # para, preservando os dados
docker compose down -v                   # para e apaga os dados
```

---

## Teste manual

**Fluxo A — explorar o mapa.** Abra `/`, siga a chamada para ação, toque num
canteiro e confirme que a página dele abre com a linha do tempo.

**Fluxo B — contribuir pelo QR Code.** Obtenha o QR Code de uma muda ou de um
canteiro (`/api/plantings/{id}/qr-code` ou `/api/regions/{slug}/qr-code`),
escaneie com a câmera do celular, confirme que abre o destino certo, envie uma
foto e confirme que ela aparece na linha do tempo.

**Fluxo C — organizador.** Crie um canteiro (e as mudas dentro dele) pela API
usando o header `X-Admin-Token`, obtenha o QR Code e confirme que ele escaneia
a partir do papel.

Teste também numa viewport de 360 px de largura. O celular é a experiência
principal para quem está de pé na área de plantio.

O passo a passo detalhado de cada fluxo — o que clicar e o que conferir em
cada etapa — está em [docs/manual-testing.md](docs/manual-testing.md). Para
quem organiza a área de plantio no dia a dia (criar canteiro/muda, obter e
imprimir o QR Code, esconder uma foto), o guia dedicado é
[docs/organizer-guide.md](docs/organizer-guide.md) — não é preciso saber
programar para segui-lo. As lacunas conhecidas de cobertura de teste, com os
números reais da suíte, estão em
[docs/test-coverage.md](docs/test-coverage.md).

---

## Convenções do projeto

- Código, identificadores, comentários, nomes de arquivo e nomes de branch em
  **inglês**.
- Documentação e todo texto de interface em **português do Brasil**, evitando
  vocabulário técnico. Uma região é um *canteiro*; o usuário nunca vê "polígono",
  "GeoJSON" ou "token".
- Mensagens de commit em português, seguindo Conventional Commits.
- Segredos ficam em arquivos `.env`, que nunca são versionados.
- Fotos enviadas ficam em `backend/storage/` e nunca são versionadas.

## Privacidade

As fotos podem ser tiradas por crianças e mostrar crianças. Toda imagem armazenada
tem os metadados removidos antes de ser gravada em disco. As coordenadas de GPS só
são registradas quando a pessoa marca explicitamente essa opção no formulário de
envio. A política completa, e o que ficou deliberadamente adiado, estão em
[docs/architecture.md](docs/architecture.md), seções 6.2 e 9.

## Como contribuir

O backlog está nas [issues](https://github.com/iagorosa/community-roots/issues),
agrupadas por fase. Antes de abrir uma pull request, vale ler
[docs/architecture.md](docs/architecture.md) — a maioria das decisões estruturais
já tem um porquê registrado lá.

## Licença

[MIT](LICENSE).
