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

O planejamento está concluído. A implementação ainda não começou.

| Fase | Descrição | Situação |
|---|---|---|
| 0 | Planejamento e documentação | concluída |
| 1 | Fundação do projeto | não iniciada |
| 2 | Canteiros | não iniciada |
| 3 | Mapa interativo | não iniciada |
| 4 | Páginas de canteiro | não iniciada |
| 5 | Envio de fotos | não iniciada |
| 6 | QR Codes | não iniciada |
| 7 | Polimento | não iniciada |

As instruções de instalação abaixo descrevem o estado ao final da Fase 1. **Elas
ainda não funcionam.**

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
uv sync

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

Abra <http://localhost:5173>. Em desenvolvimento, `/api` é redirecionado para o
backend pelo proxy do Vite, então há uma origem só e nenhum CORS para configurar.

### 4. Dados de desenvolvimento

```bash
cd backend
python scripts/seed.py
```

Isso cria 10 canteiros fictícios distribuídos ao redor de `SEED_CENTER_LAT` e
`SEED_CENTER_LON`. **A geometria é um placeholder** — os polígonos reais serão
importados quando o geógrafo entregar o levantamento. Rodar o script de novo não
muda nada: ele reconhece os canteiros pelo slug.

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

**Fluxo B — contribuir pelo QR Code.** Obtenha o QR Code de um canteiro em
`/api/regions/{slug}/qr-code`, escaneie com a câmera do celular, confirme que abre
o canteiro certo, envie uma foto e confirme que ela aparece na linha do tempo.

**Fluxo C — organizador.** Crie um canteiro pela API usando o header
`X-Admin-Token`, obtenha o QR Code dele e confirme que a folha de impressão sai
utilizável.

Teste também numa viewport de 360 px de largura. O celular é a experiência
principal para quem está de pé na área de plantio.

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
