# Community Roots — Plano de Implementação

Documento companheiro de [architecture.md](./architecture.md), onde está o
raciocínio por trás de cada decisão citada aqui. O escopo vem de
[../PROJECT_BOOTSTRAP.md](../PROJECT_BOOTSTRAP.md).

Cada fase termina com uma etapa de validação. Uma fase não está concluída
enquanto a validação não passar e o resultado não for relatado honestamente.

O backlog está no GitHub: cada fase é um
[milestone](https://github.com/iagorosa/community-roots/milestones), com as
issues do trabalho correspondente.

| Fase | Resultado | Situação |
|---|---|---|
| 0 | Planejamento, documentação e decisões | concluída |
| 1 | Fundação do projeto: esqueleto, banco, endpoint de saúde | não iniciada |
| 2 | Canteiros: model, migration, seed, API em GeoJSON | não iniciada |
| 3 | Mapa interativo | não iniciada |
| 4 | Páginas de canteiro e linha do tempo (só leitura) | não iniciada |
| 5 | Envio de fotos | não iniciada |
| 6 | QR Codes | não iniciada |
| 7 | Polimento, acessibilidade e revisão de segurança | não iniciada |

---

## Decisões confirmadas

Resolvidas com o responsável pelo projeto durante o planejamento:

1. **Localização de referência.** A área de plantio fica em **Matias Barbosa,
   Minas Gerais** (aproximadamente `-21.883859, -43.312459`). O centro é
   configurado por `SEED_CENTER_LAT` e `SEED_CENTER_LON`, nunca fixado em código.
2. **Dados de desenvolvimento.** 10 canteiros fictícios, gerados em grade ao
   redor do centro configurado. São placeholders de desenvolvimento, não
   levantamento geográfico, e cada registro é identificado como tal.
3. **Geometria do canteiro.** `geometry(Geometry, 4326)` com constraint CHECK
   sobre o tipo de geometria, mais um `centroid` gerado — ver arquitetura §4.1.
4. **EXIF.** Data de captura e GPS são ambos extraídos; o GPS só é gravado quando
   a pessoa adere explicitamente, por um checkbox desmarcado por padrão. O arquivo
   armazenado sempre tem os metadados removidos — ver arquitetura §6.2.
5. **Linguagem do frontend.** TypeScript.
6. **Idioma.** Documentação e interface em português; código, identificadores,
   nomes de arquivo e nomes de branch em inglês; mensagens de commit em português.

Decisões tomadas pelo implementador, abertas a reversão: venv local em vez de
backend em container; endpoints administrativos atrás de um token compartilhado;
imagem `postgis/postgis:16-3.4`; porta do banco configurável, para não conflitar
com as outras instâncias de Postgres já rodando nesta máquina.

---

## Fase 1 — Fundação do projeto

**Objetivo:** `docker compose up -d`, um comando no backend, um no frontend, e os
três respondem. Nenhuma lógica de domínio ainda.

### Entregáveis

**Infraestrutura**
- `docker-compose.yml` com um único serviço `db` na imagem
  `postgis/postgis:16-3.4`, volume nomeado, healthcheck com `pg_isready` e a
  porta vinda de `POSTGRES_PORT`.
- `infrastructure/postgres/init/01-init.sql`: `CREATE EXTENSION postgis` e
  criação do banco `community_roots_test`.
- `.env.example` na raiz.

**Backend**
- `pyproject.toml` pinando fastapi, uvicorn, sqlalchemy, geoalchemy2, psycopg,
  alembic, pydantic-settings, pillow, qrcode e python-multipart; extras de
  desenvolvimento: pytest, httpx e ruff.
- `.python-version` (3.11.10) e `backend/.env.example`.
- `app/core/config.py` — `Settings`, validado na importação, falhando com uma
  mensagem que diz qual variável está faltando.
- `app/db/session.py` — engine, session factory e a dependência `get_db`.
- `app/db/base.py` — `DeclarativeBase` com mixins compartilhados de `id` e de
  timestamps.
- `app/main.py` — app factory, CORS a partir das settings, handlers de exceção e
  montagem dos routers.
- `app/api/routes/health.py` — `GET /health` devolvendo
  `{"status": "ok", "database": "ok"}`, onde `database` reflete um `SELECT 1` de
  verdade.
- Alembic inicializado contra o metadata da aplicação, com uma revisão baseline
  vazia.
- `tests/conftest.py` e `tests/test_health.py`.

**Frontend**
- `npm create vite@latest` (react-ts), com o Node fixado pelo `.nvmrc` (22.22.1).
- Tailwind v4 pelo plugin `@tailwindcss/vite` — sem comando `init`, sem
  `tailwind.config.js`, sem `postcss.config.js`.
- `react-router`, TanStack Query, `leaflet` e `react-leaflet` instalados, mas
  ainda não ligados a nenhuma página.
- Proxy de desenvolvimento do Vite de `/api` para o backend, para que o navegador
  enxergue uma origem só.
- `src/services/apiClient.ts` e uma `HomePage` provisória que renderiza a resposta
  do endpoint de saúde, provando o caminho inteiro.
- Vitest configurado, com um teste de fumaça passando.
- `frontend/.env.example`.

**Documentação**
- README com passos de setup reais, verificados executando-os a partir de um
  estado limpo.

### Validação
- `docker compose up -d` chega a um container saudável; `SELECT postgis_version()`
  responde.
- `alembic upgrade head` roda limpo; `alembic downgrade base` seguido de
  `upgrade head` também.
- `GET /health` devolve `database: "ok"`; parar o banco muda esse campo em vez de
  derrubar o processo.
- `pytest` passa.
- `npm run dev` serve uma página que mostra a resposta de saúde obtida pelo proxy.
- `npm run build` e `npm run test` passam.

---

## Fase 2 — Canteiros

**Objetivo:** os canteiros existem no PostGIS e são legíveis como GeoJSON.

### Entregáveis
- `app/models/region.py` conforme arquitetura §4.2, usando o `Geometry` do
  GeoAlchemy2.
- Migration do Alembic: garantia da extensão, tabela, constraints CHECK, centroide
  gerado, índices GiST e constraints de unicidade. Revisada à mão, não autogenerate
  cru.
- `app/schemas/geojson.py` — modelos `Feature` e `FeatureCollection`, para que o
  OpenAPI documente a resposta real em vez de um `dict` genérico.
- `app/services/region_service.py` — listar, resolver por slug ou UUID, criar e
  atualizar. A geração de slug e de `qr_token` vive aqui.
- `GET /api/regions`, `GET /api/regions/{region}`, `POST /api/regions` e
  `PATCH /api/regions/{region}`.
- `app/core/security.py` — dependência do token administrativo nas rotas de
  escrita.
- `scripts/seed.py` — idempotente (upsert por slug), gerando 10 canteiros numa
  grade 5 × 2 de quadrados de aproximadamente 50 m ao redor do centro configurado,
  com nomes em português de árvores nativas brasileiras. Lê o centro das settings;
  rodar duas vezes não muda nada.
- Testes: formato do GeoJSON, ida e volta da geometria pelo banco, resolução por
  slug e por UUID, tratamento de 404, exigência do token administrativo e
  idempotência do seed.

### Validação
- O seed produz 10 canteiros; rodar de novo continua produzindo 10.
- `GET /api/regions` devolve uma `FeatureCollection` válida, que passa numa
  verificação de schema GeoJSON.
- A constraint CHECK de geometria rejeita uma `LINESTRING`.
- `photo_count` está presente e vale zero, resolvido numa única consulta
  (verificado pelo log de SQL, não presumido).
- `pytest` passa.

---

## Fase 3 — Mapa interativo

**Objetivo:** o mapa mostra os canteiros reais vindos do backend e navega até eles.

### Entregáveis
- `App.tsx` com o roteador; `Layout` e `Header`.
- `types/api.ts` espelhando os schemas do backend.
- `services/regions.ts` e `hooks/useRegions.ts`.
- `components/map/PlantingMap.tsx` — `MapContainer`, tiles e atribuição do
  OpenStreetMap vindos de variáveis de ambiente, altura fornecida pelo pai.
- `components/map/RegionLayer.tsx` — desenha a `FeatureCollection`, trata clique e
  ativação por teclado, aplica estilo de hover e de foco.
- `components/map/RegionPopup.tsx` — nome, contagem de fotos e link para o
  canteiro.
- `MapPage` — layout de altura cheia, ajustando o enquadramento aos limites das
  features retornadas.
- `feedback/LoadingState`, `ErrorState` e `EmptyState`.
- `HomePage` com conteúdo de verdade: o que é o projeto, como participar e chamada
  para ação levando ao mapa.
- Testes do `RegionLayer` com o `react-leaflet` simulado.

### Validação
- Os canteiros aparecem; não há nenhuma geografia fixada em código no frontend.
- Tocar num canteiro abre a página dele.
- O mapa preenche o container numa viewport de 360 px de largura, sem área cinza e
  sem scroll horizontal na página.
- O Strict Mode não causa inicialização dupla nem erro no console.
- Com o backend parado, aparece o estado de erro, não uma tela em branco.

---

## Fase 4 — Páginas de canteiro

**Objetivo:** uma página de canteiro alcançável por URL, com a sua linha do tempo
(ainda vazia).

### Entregáveis
- `app/models/photo.py` e a migration correspondente, conforme arquitetura §4.3.
- `app/services/photo_service.py` — listagem com paginação.
- `GET /api/regions/{region}/photos`.
- `GET /api/photos/{photo_id}/file` — transmite a partir do backend de storage,
  com content type correto e `Cache-Control` de conteúdo imutável.
- `RegionPage` — nome, descrição, um mapa pequeno centrado no canteiro, contagem de
  fotos, linha do tempo e um botão de envio desabilitado até a Fase 5.
- `PhotoTimeline` e `PhotoCard`, agrupados por data, mais recentes primeiro.
- `NotFoundPage`, e um 404 de verdade para slug desconhecido.

### Validação
- A URL de um canteiro carrega direto, sem passar antes pelo mapa.
- O estado vazio explica como contribuir, em vez de mostrar uma área em branco.
- O mapa pequeno renderiza corretamente ao lado do conteúdo, com proporção fixa.
- Um slug desconhecido leva à página 404, não ao estado de erro.

---

## Fase 5 — Envio de fotos

**Objetivo:** o fluxo de contribuição por QR Code funciona de ponta a ponta.

### Entregáveis
- `app/storage/base.py` — o protocolo `StorageBackend`.
- `app/storage/local.py` — `LocalFilesystemStorage`, injetado como dependência.
- `app/services/image_processing.py` — limite de tamanho, detecção de formato real
  pelo Pillow, proteção contra bomba de descompressão, extração de EXIF, aplicação
  da orientação e reescrita sem metadados.
- `POST /api/regions/{region}/photos` — multipart com `file`, `description`,
  `contributor_name` e `share_location`.
- Exceções de domínio traduzidas para mensagens em português, seguras para o
  usuário, com códigos estáveis.
- `PhotoUploadForm` — seletor de arquivo com preview imediato, nome e observação
  opcionais, checkbox `share_location` desmarcado com texto em linguagem simples
  explicando o que ele faz, estado de progresso e botão desabilitado durante o
  envio.
- A linha do tempo se atualiza sozinha ao concluir, por invalidação de query.
- Testes: caminho feliz; arquivo grande demais; formato errado; bytes corrompidos;
  nome `.jpg` com conteúdo que não é imagem; ausência de EXIF no arquivo gravado,
  verificada relendo-o; GPS gravado somente com adesão.

### Validação
- Uma foto enviada pelo celular aparece na linha do tempo.
- Todo caminho de rejeição devolve uma mensagem sobre a qual um usuário não
  técnico consegue agir.
- O arquivo gravado, reaberto, não tem bloco EXIF.
- Com o checkbox desmarcado, uma foto com GPS resulta em `location IS NULL`.
- Dois envios de arquivos com nome idêntico não colidem.

---

## Fase 6 — QR Codes

**Objetivo:** o organizador consegue imprimir os códigos e instalá-los em campo.

### Entregáveis
- `app/services/qr_service.py` e `GET /api/regions/{region}/qr-code`
  (`?format=png|svg`, `?size=`), codificando
  `{PUBLIC_WEB_BASE_URL}/r/{qr_token}`.
- `GET /api/qr/{qr_token}` e a rota `/r/:qrToken` no frontend, redirecionando para
  o canteiro.
- Uma folha imprimível: um card por canteiro, com o QR Code e o nome, diagramada
  para A4 com CSS de impressão.
- `POST /api/regions/import` aceitando uma `FeatureCollection` GeoJSON, casando
  por slug e relatando quantos foram criados, atualizados e ignorados.
- Testes: conteúdo da URL codificada, content types, 404 para token desconhecido,
  casamento e idempotência da importação.

### Validação
- Um código escaneado com a câmera do celular abre o canteiro correto.
- Renomear um canteiro e trocar o seu slug não invalida o código já impresso.
- Importar um arquivo GeoJSON substitui a geometria placeholder preservando o
  `qr_token` de cada canteiro.

---

## Fase 7 — Polimento

### Entregáveis
- Passada de mobile em todas as páginas, a 360 px; alvos de toque de pelo menos
  44 px.
- Acessibilidade: navegação por teclado sobre os canteiros do mapa, foco visível,
  texto alternativo nas fotos, campos com label, contraste verificado e um único
  `h1` por página.
- Revisão do tratamento de erros: nenhum stack trace e nenhuma string em inglês
  chegando ao usuário.
- Revisão de segurança contra arquitetura §9; decisão sobre rate limiting no
  endpoint de envio.
- `Dockerfile` do backend e uma nota de publicação.
- Documentação: roteiros de teste manual para cada fluxo da especificação §15,
  guia do organizador e revisão das lacunas de cobertura.

---

## Acordo de trabalho

- Uma fase por vez; validação relatada com a saída real dos comandos, não
  afirmada.
- Nomes de branch em inglês; mensagens de commit em português, seguindo
  Conventional Commits.
- Mudanças de arquitetura são registradas em `docs/architecture.md` no momento em
  que acontecem, não no final.
- Qualquer coisa que toque o modelo de privacidade, autenticação, serviços pagos
  ou uma mudança irreversível no modelo de dados para para confirmação.
