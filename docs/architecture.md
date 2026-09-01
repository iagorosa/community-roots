# Community Roots — Arquitetura

Situação atual: **fase de planejamento**. Este documento descreve a arquitetura
alvo e o motivo de cada decisão. É a referência para todas as fases descritas em
[implementation-plan.md](./implementation-plan.md).

Especificação do produto: [../PROJECT_BOOTSTRAP.md](../PROJECT_BOOTSTRAP.md).

> Nota sobre idioma: esta documentação é escrita em português porque o projeto é
> comunitário e aberto à participação local. O código — identificadores,
> comentários, nomes de arquivo, rotas da API — continua em inglês.

---

## 1. Visão geral do sistema

O Community Roots é um monolito bem organizado, dividido em duas unidades
publicáveis e um banco de dados:

```
Navegador (mobile-first)
      |
      |  HTTPS / JSON + multipart
      v
SPA em React (Vite)  ---- build estático, servido por qualquer host de arquivos
      |
      |  REST /api/*
      v
Backend FastAPI  ----> StorageBackend (disco local hoje, S3 no futuro)
      |
      |  SQLAlchemy + GeoAlchemy2
      v
PostgreSQL 16 + PostGIS 3.4
```

Não há microsserviços, fila de mensagens nem worker em segundo plano no MVP.
Toda requisição é atendida de forma síncrona.

A corrente do físico para o digital, que é o coração do produto:

```
Placa no canteiro -> QR Code -> canteiro digital -> linha do tempo de fotos
```

---

## 2. Decisões de tecnologia

| Camada | Escolha | Por quê |
|---|---|---|
| Framework de frontend | React 19 + Vite 8 | Segue a direção do protótipo anterior; o Vite dá HMR rápido e build estático trivial. |
| Linguagem do frontend | TypeScript 6 | O desenvolvedor é mais forte em backend; tipos em `Region` e `Photo` espelham os schemas Pydantic e pegam erro de formato de dado em tempo de edição. |
| Estilo | Tailwind CSS v4 via `@tailwindcss/vite` | Ver [§2.1](#21-decisão-do-tailwind-v4). |
| Mapa | `react-leaflet` v5 + `leaflet` 1.9 | Ver [§2.2](#22-decisão-do-mapa). |
| Rotas | `react-router` v8 (modo declarativo) | Padrão do ecossistema, pequeno, sem amarrar a um framework. |
| Estado de servidor | TanStack Query v5 | Estados de carregamento, erro e recarga são a maior parte da lógica de tela deste app. Reescrever isso em cada página é a complexidade maior. |
| Backend | FastAPI + Pydantic v2 | Documentação OpenAPI automática, validação de request e suporte a multipart. |
| ORM | SQLAlchemy 2.0 (tipado, com `Mapped[...]`) + GeoAlchemy2 | O GeoAlchemy2 mapeia colunas de geometria do PostGIS para tipos Python reais e expõe as funções `ST_*` através do SQLAlchemy. |
| Migrations | Alembic | Exigido pela especificação. O autogenerate serve só como ponto de partida: toda migration é revisada à mão. |
| Banco de dados | PostgreSQL 16 + PostGIS 3.4 (`postgis/postgis:16-3.4`) | O produto é geográfico por natureza; polígonos e consultas espaciais são o núcleo, não um extra futuro. |
| Infra local | Docker Compose (só o banco) | Ver [§2.3](#23-decisão-de-topologia-de-execução). |
| Ambiente Python | pyenv 3.11.10 + virtualenv do `uv` | O pyenv já é a ferramenta do desenvolvedor; o `uv` dá instalação rápida e reproduzível com lockfile. O `venv` + `pip` fica documentado como alternativa. |
| Testes de backend | pytest + `TestClient` do FastAPI | A pilha é síncrona, então não é preciso harness de teste assíncrono. |
| Testes de frontend | Vitest + Testing Library + MSW | Mesmo pipeline de transformação do Vite; o MSW simula a API na camada de rede. |
| QR Codes | `qrcode` + `Pillow` | Python puro, sem serviço externo e sem API key. |

> As versões major desta tabela foram atualizadas na issue #46 para
> refletir o que `npm create vite@latest` e `npm install` realmente
> instalaram na implementação da #6 (Vite 7→8, TypeScript passou a ser
> especificado como 6, React Router v7→8; versões exatas em
> `frontend/package.json`). O modo declarativo do React Router continua
> existindo e sendo o modo recomendado pela documentação oficial da v8
> para quem "quer usar o React Router da forma mais simples possível" —
> a decisão registrada na linha "Rotas" segue válida sem mudanças.

### 2.1 Decisão do Tailwind v4

O protótipo anterior quebrou no setup do Tailwind, especificamente em torno de
`npx tailwindcss init -p`. O Tailwind v4 elimina esse modo de falha por completo:

- Não existe mais comando `init`, nem `tailwind.config.js` obrigatório.
- Não há configuração de PostCSS para manter — o plugin oficial
  `@tailwindcss/vite` cuida do pipeline.
- O setup são duas linhas: o plugin no `vite.config.ts` e
  `@import "tailwindcss";` no topo de `src/styles/index.css`.
- Quando for preciso customizar o tema, isso vive no próprio CSS, num bloco
  `@theme { ... }`.

As versões exatas ficam registradas em `frontend/package.json` e repetidas no
README, para que a combinação que funciona nunca mais precise ser adivinhada.

### 2.2 Decisão do mapa

O Leaflet é usado através do `react-leaflet`, nunca por chamada direta a
`L.map(...)`. Isso elimina os três problemas enfrentados no protótipo anterior:

- **Inicialização dupla.** O `react-leaflet` é dono do ciclo de vida da instância
  do mapa, então não existe um `L.map("map")` amarrado a um id global do DOM que
  possa ser inicializado duas vezes sob o Strict Mode do React.
- **Dimensão do container.** O container do mapa recebe altura explícita por CSS
  (um wrapper dimensionado por flex na página do mapa; uma caixa de
  `aspect-ratio` fixo na página do canteiro). Essa é a causa real do clássico
  "mapa cinza pela metade" — o conserto é de layout, não de espalhar
  `invalidateSize()` pelo código.
- **Ciclo de vida manual.** Nenhum `useEffect` para criar ou destruir o mapa.

O `invalidateSize()` é usado em exatamente um lugar, se necessário: um hook
pequeno reagindo ao redimensionamento do container na página do canteiro. Se o
layout sozinho resolver, esse hook não chega a existir.

Os tiles vêm do OpenStreetMap, com a URL e a atribuição lidas de variáveis de
ambiente, para trocar de provedor sem alterar código. Nenhuma API key paga é
necessária.

### 2.3 Decisão de topologia de execução

Só o PostgreSQL/PostGIS roda em Docker Compose. Backend e frontend rodam direto
na máquina.

Motivo: para um desenvolvedor sozinho, Python dentro de container com watcher de
reload é perceptivelmente mais lento de iterar e adiciona uma camada a mais para
depurar, sem benefício aqui. O banco, ao contrário, ganha de verdade com
isolamento — instalar PostGIS nativamente é chato, e a máquina já roda outras
instâncias de Postgres que não podem ser perturbadas.

A porta do banco é exposta através da variável `POSTGRES_PORT` (padrão `5432`)
justamente porque as portas `5433` e `54322` já estão ocupadas por outros
contêineres Postgres nesta máquina.

Um `Dockerfile` do backend entra na Fase 7, para publicação — não para
desenvolvimento local.

---

## 3. Estrutura do repositório

```
community_roots/
├── README.md
├── PROJECT_BOOTSTRAP.md          # especificação do produto (fonte do escopo)
├── docker-compose.yml
├── .env.example                  # variáveis consumidas pelo docker-compose
├── docs/
│   ├── architecture.md
│   └── implementation-plan.md
├── infrastructure/
│   └── postgres/init/            # roda uma única vez, no primeiro start
│       └── 01-init.sql           # CREATE EXTENSION postgis; cria o banco de teste
├── backend/
│   ├── .python-version           # 3.11.10
│   ├── .env.example
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/versions/
│   ├── app/
│   │   ├── main.py               # app factory, montagem de routers, CORS, handlers
│   │   ├── core/
│   │   │   ├── config.py         # Settings (pydantic-settings)
│   │   │   ├── security.py       # dependência do token administrativo
│   │   │   └── errors.py         # exceções de domínio -> respostas HTTP
│   │   ├── db/
│   │   │   ├── base.py           # DeclarativeBase
│   │   │   └── session.py        # engine, session factory, dependência get_db
│   │   ├── models/               # models SQLAlchemy (region.py, photo.py)
│   │   ├── schemas/              # modelos Pydantic de request e response
│   │   ├── services/             # regra de negócio, sem importar FastAPI
│   │   ├── storage/              # protocolo StorageBackend + implementação local
│   │   └── api/routes/           # health.py, regions.py, photos.py
│   ├── scripts/seed.py
│   ├── storage/                  # uploads locais (fora do Git)
│   └── tests/
└── frontend/
    ├── .nvmrc                    # 22.22.1
    ├── .env.example
    ├── vite.config.ts
    └── src/
        ├── pages/                # HomePage, MapPage, RegionPage, QrRedirectPage, NotFoundPage
        ├── components/
        │   ├── layout/           # Header, Layout
        │   ├── map/              # PlantingMap, RegionLayer, RegionPopup
        │   ├── photos/           # PhotoTimeline, PhotoCard, PhotoUploadForm
        │   └── feedback/         # LoadingState, ErrorState, EmptyState
        ├── services/             # apiClient, regions, photos — os únicos que chamam fetch
        ├── hooks/                # useRegions, useRegion, useRegionPhotos, useUploadPhoto
        ├── types/                # definições de tipo da API
        ├── utils/
        └── styles/index.css
```

**Regra de camada do backend:** as rotas validam e autorizam, os services
decidem, os models e o storage persistem. Service nunca importa nada de
`app.api`; rota nunca monta SQL. É isso que faz uma futura interface
administrativa, ou uma CLI, reaproveitarem as mesmas funções de service.

**Regra de camada do frontend:** componente nenhum chama `fetch`. Todo acesso à
rede passa por `src/services/`, embrulhado por hooks em `src/hooks/`. É isso que
mantém os componentes testáveis apenas com props.

---

## 4. Modelo de dados

### 4.1 Decisão de geometria: `geometry(Geometry, 4326)`

A coluna `regions.geom` é declarada como `geometry(Geometry, 4326)`, com uma
constraint CHECK que a restringe a `POINT`, `POLYGON` e `MULTIPOLYGON`.

**Por que um tipo genérico de geometria.** O MVP precisa funcionar antes de o
geógrafo entregar os dados oficiais (especificação §2). Um tipo permissivo deixa
um canteiro nascer como ponto placeholder ou polígono desenhado a mão e depois
ser substituído por um `MultiPolygon` levantado em campo, com um `UPDATE` simples
— sem migration de tipo de coluna, sem reescrita de dado, sem redesenho da
aplicação. A constraint CHECK mantém essa permissividade dentro de um limite: a
coluna nunca pode guardar algo que o mapa não sabe desenhar.

**Por que `geometry` e não `geography`.** O tipo `geometry` com SRID 4326 é a
escolha convencional em PostGIS e tem a superfície completa de funções, incluindo
tudo de que o `ST_AsGeoJSON` e o Leaflet precisam. O `geography` entrega
distância precisa em metros sem projeção, mas a área de plantio tem algumas
centenas de metros; nessa extensão, converter com `geom::geography` na consulta
rara de distância é exato o suficiente e não custa nada. O `geography` também
suporta um conjunto menor de funções, o que limitaria as consultas espaciais
listadas na especificação §5.

**Por que um centroide separado.** `centroid` é uma coluna
`geometry(Point, 4326)` gerada como `ST_Centroid(geom)` (armazenada; o
`ST_Centroid` é `IMMUTABLE`). Ela dá ao mapa uma âncora estável para o marcador e
transforma "qual canteiro está mais perto deste ponto?" numa consulta indexada
simples, sem recalcular centroide a cada requisição.

### 4.2 Tabela `regions`

| Coluna | Tipo | Observações |
|---|---|---|
| `id` | `uuid` PK | `gen_random_uuid()` |
| `slug` | `text` único, not null | Trecho da URL, legível por humanos, pode ser renomeado |
| `name` | `text` not null | Exibido ao usuário |
| `description` | `text` nulo | Texto curto opcional |
| `geom` | `geometry(Geometry, 4326)` not null | CHECK sobre `GeometryType(geom)`; índice GiST |
| `centroid` | `geometry(Point, 4326)` gerada e armazenada | Índice GiST |
| `status` | `text` not null, padrão `'active'` | CHECK em (`active`, `draft`, `archived`) |
| `qr_token` | `text` único, not null | Opaco, seguro para URL, estável por toda a vida do canteiro |
| `created_at` | `timestamptz` not null | |
| `updated_at` | `timestamptz` not null | |

### 4.3 Tabela `photos`

| Coluna | Tipo | Observações |
|---|---|---|
| `id` | `uuid` PK | |
| `region_id` | `uuid` FK -> `regions.id` | `ON DELETE CASCADE`, indexada |
| `storage_key` | `text` not null | Chave opaca, com significado apenas para o backend de storage |
| `original_filename` | `text` nulo | Guardado para exibição; nunca usado para montar caminho |
| `content_type` | `text` not null | Determinado decodificando a imagem, não pelo header do cliente |
| `byte_size` | `integer` not null | |
| `width`, `height` | `integer` not null | Permite reservar espaço no layout e evitar salto de página |
| `description` | `text` nulo | |
| `contributor_name` | `text` nulo | |
| `captured_at` | `timestamptz` nulo | Do EXIF `DateTimeOriginal`, quando existir |
| `uploaded_at` | `timestamptz` not null | Relógio do servidor |
| `location` | `geometry(Point, 4326)` nulo | Ver [§4.4](#44-decisão-de-localização-da-foto) |
| `location_source` | `text` nulo | `exif` hoje; `manual` e `browser` são valores futuros |
| `status` | `text` not null, padrão `'published'` | CHECK em (`published`, `hidden`) |
| `includes_identifiable_person_with_consent` | `boolean` not null, padrão `false` | Ver [§9](#9-segurança-e-moderação) — issue #38 |

Índice em `(region_id, uploaded_at DESC)` — a consulta da linha do tempo é o
caminho quente.

### 4.4 Decisão de localização da foto

A especificação sugere colunas `latitude` e `longitude`. Guardamos um único
`geometry(Point, 4326)` no lugar, e expomos `latitude` e `longitude` na resposta
da API. Duas colunas float soltas não conseguem responder "qual canteiro contém
esta foto?" sem construção improvisada a cada consulta; um ponto de verdade
consegue, pelo mesmo índice GiST que as regiões já usam. O contrato da API não
muda.

### 4.5 As colunas `status`

Nem `regions.status` nem `photos.status` têm interface no MVP. Elas existem
porque o produto envolve upload público feito por e sobre crianças, e o
organizador precisa de um jeito de tirar uma foto do ar **imediatamente** — um
`UPDATE` de uma linha desde o primeiro dia, em vez de uma migration de
emergência. Essa é a única coluna do schema olhando para o futuro; todas as
outras entidades futuras da especificação §7 (User, Contributor, Planting event,
Seed, Organization) estão deliberadamente ausentes.

### 4.6 Entidades futuras

`User`, `Contributor`, `PlantingEvent`, `Seed` e `Organization` não são
modeladas. Os caminhos que precisariam delas já estão isolados:
`contributor_name` é uma coluna de texto nula que um futuro `contributor_id` pode
suceder, e todo endpoint de escrita já passa por uma função de service onde uma
identidade autenticada pode ser injetada.

---

## 5. Desenho da API

REST, JSON, documentada automaticamente em `/docs` (OpenAPI).

O `{region}` nos caminhos abaixo aceita tanto o UUID quanto o slug. A resolução
acontece num único lugar, numa dependência compartilhada do FastAPI.

| Método | Caminho | Acesso | Resposta |
|---|---|---|---|
| `GET` | `/health` | público | `{status, database}` |
| `GET` | `/api/regions` | público | `FeatureCollection` GeoJSON |
| `GET` | `/api/regions/{region}` | público | `Feature` GeoJSON |
| `POST` | `/api/regions` | admin | `Feature` GeoJSON (201) |
| `PATCH` | `/api/regions/{region}` | admin | `Feature` GeoJSON |
| `POST` | `/api/regions/import` | admin | Resumo da importação — Fase 6 |
| `GET` | `/api/regions/{region}/photos` | público | Lista paginada de fotos |
| `POST` | `/api/regions/{region}/photos` | público | Foto criada (201), `multipart/form-data` |
| `GET` | `/api/regions/{region}/qr-code` | público | `image/png` ou `image/svg+xml` |
| `GET` | `/api/photos/{photo_id}/file` | público | Bytes da imagem |
| `GET` | `/api/qr/{qr_token}` | público | Resolve um token para o seu canteiro |

### 5.1 GeoJSON como representação do canteiro

Coleções de canteiros são devolvidas como uma `FeatureCollection` GeoJSON, que o
componente `<GeoJSON>` do `react-leaflet` consome direto, sem etapa de
transformação. Os atributos do canteiro viajam em `properties`:

```json
{
  "type": "Feature",
  "id": "0f1c...",
  "geometry": { "type": "Polygon", "coordinates": [[[-43.3129, -21.8843], "..."]] },
  "properties": {
    "slug": "canteiro-do-ipe",
    "name": "Canteiro do Ipê",
    "description": "...",
    "status": "active",
    "qr_token": "k3Zq8xR2mNvA",
    "photo_count": 12,
    "latest_photo_at": "2026-08-24T14:03:11Z",
    "created_at": "2026-08-01T10:00:00Z",
    "updated_at": "2026-08-24T14:03:11Z"
  }
}
```

A geometria é produzida pelo `ST_AsGeoJSON` dentro do banco, e não serializada em
Python, de modo que a saída de coordenadas tenha exatamente uma implementação.

`photo_count` e `latest_photo_at` são calculados por um agregado com
`LEFT JOIN LATERAL` na mesma consulta — o mapa precisa deles para todos os
canteiros, e um N+1 apareceria de imediato.

### 5.2 Entrega dos arquivos de foto

As imagens são sempre servidas por `GET /api/photos/{photo_id}/file`, nunca por
um caminho direto de storage. Assim a URL continua válida quando o backend de
armazenamento mudar: hoje o endpoint transmite do disco; amanhã ele devolve um
302 para uma URL assinada do S3. Chaves de storage nunca aparecem em resposta da
API.

### 5.3 Erros

Exceções de domínio (`RegionNotFound`, `InvalidImage`, `ImageTooLarge`) são
levantadas pelos services e traduzidas em respostas HTTP por handlers em
`app/main.py`. Corpo da resposta:

```json
{ "detail": "Não foi possível ler esta imagem.", "code": "invalid_image" }
```

O `detail` é texto em português voltado ao usuário, seguro para exibir direto. O
`code` é um identificador estável, em inglês, para o frontend decidir o que fazer.

Qualquer exceção que não seja uma `AppError` — conexão com o banco perdida, escrita
em `storage/` falhando por permissão, ou qualquer bug não previsto — também é
capturada, por um handler para `Exception` registrado em `app/core/errors.py`
(issue #36). O cliente recebe o mesmo formato acima, sempre com `code:
"internal_error"` e um `detail` genérico que ainda diz o que fazer ("tente
novamente em instantes"); a exceção real, com traceback, só é registrada no log do
servidor — nunca chega à resposta HTTP.

---

## 6. Armazenamento de fotos

```python
class StorageBackend(Protocol):
    def save(self, key: str, data: BinaryIO, content_type: str) -> None: ...
    def open(self, key: str) -> BinaryIO: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```

`LocalFilesystemStorage` é a única implementação do MVP, gravando em
`backend/storage/` (fora do Git). Ela é selecionada por `STORAGE_BACKEND=local` e
injetada como dependência do FastAPI, o que permite aos testes substituí-la por
uma instância em diretório temporário sem tocar no código dos services.

As chaves seguem `regions/{region_id}/{ano}/{uuid4}.{ext}` — livres de colisão,
nunca derivadas de input do usuário, e baratas de listar por prefixo de canteiro.

### 6.1 Validação do upload

Aplicada nesta ordem; a primeira falha rejeita a requisição:

1. **Tamanho.** `MAX_UPLOAD_BYTES` (padrão 10 MB), aplicado durante o streaming,
   antes de o arquivo ser inteiramente bufferizado.
2. **Formato real.** Os bytes são decodificados com o Pillow e o formato é lido da
   imagem decodificada. O `Content-Type` enviado pelo cliente e a extensão do
   arquivo são ambos ignorados nessa decisão. Aceitos: JPEG, PNG e WebP.
3. **Bomba de descompressão.** O `Image.MAX_IMAGE_PIXELS` recebe um limite, para
   que um arquivo pequeno e mal-intencionado não esgote a memória.
4. **Reescrita.** A imagem é reescrita antes de ser gravada. Isso normaliza o
   formato, aplica a orientação do EXIF e — o ponto crítico — produz um arquivo
   armazenado sem metadado nenhum (ver abaixo).

### 6.2 EXIF e privacidade

O arquivo de imagem armazenado sempre tem o bloco EXIF removido. Os metadados são
primeiro extraídos para colunas do banco, e só o que a pessoa concordou em
compartilhar é mantido:

- `DateTimeOriginal` -> `captured_at`. Sempre extraído; é o que dá sentido à
  linha do tempo.
- Tags de GPS -> `location`. Gravado **apenas** quando o envio inclui
  `share_location=true`.

O `share_location` é um checkbox de adesão explícita no formulário, **desmarcado
por padrão**, com texto em linguagem simples dizendo que a localização da foto
será registrada. Qualquer pessoa pode contribuir, inclusive crianças, então
coletar em silêncio a coordenada precisa de onde um menor estava não é aceitável.
Com a caixa desmarcada, as tags de GPS são lidas e descartadas, nunca gravadas.

Como o arquivo armazenado é limpo de qualquer forma, uma foto que vaze por
qualquer outro caminho também não carrega localização escondida.

### 6.3 Adiado

Geração de miniaturas e variantes responsivas ficam fora do MVP. O gancho já
existe: `width` e `height` são registrados no momento do upload, e o endpoint que
serve o arquivo é o único lugar onde um parâmetro `?size=` seria tratado depois.

---

## 7. QR Codes

O identificador estável é o `regions.qr_token`: uma string aleatória, opaca e
segura para URL, atribuída uma vez e nunca alterada. A imagem do QR codifica:

```
{PUBLIC_WEB_BASE_URL}/r/{qr_token}
```

O token é codificado em vez do slug, de propósito. Um QR Code impresso e
instalado fisicamente não é barato de reimprimir, então a URL que ele carrega
precisa sobreviver ao canteiro ser renomeado, ter o slug trocado ou mudar de
chave internamente. O `/r/{qr_token}` resolve através de
`GET /api/qr/{qr_token}` e redireciona para `/regions/{slug}`.

`GET /api/regions/{region}/qr-code` gera a imagem sob demanda (`?format=png|svg`,
`?size=`). Nada é gravado em disco — regerar é barato e não existe problema de
arquivo desatualizado. A folha de impressão, com o nome do canteiro embaixo de
cada código, é trabalho da Fase 6, produzido a partir do mesmo endpoint.

---

## 8. Arquitetura do frontend

| Rota | Página | Papel |
|---|---|---|
| `/` | `HomePage` | O que é o projeto, como participar, chamada para ação |
| `/mapa` | `MapPage` | Mapa interativo de todos os canteiros, em altura cheia |
| `/regions/:slug` | `RegionPage` | Detalhe do canteiro, linha do tempo, envio de foto |
| `/r/:qrToken` | `QrRedirectPage` | Resolve um token escaneado e redireciona |
| `*` | `NotFoundPage` | |

O caminho do canteiro permanece `/regions/:slug` (em inglês, como definido na
especificação §3), para que os QR Codes impressos e a especificação concordem
entre si. As demais rotas visíveis ao usuário são em português.

**Fluxo de dados.** O `services/apiClient.ts` é dono do `fetch`, da URL base e da
normalização de erros. `services/regions.ts` e `services/photos.ts` expõem
funções tipadas. Os hooks embrulham essas funções no TanStack Query. As páginas
chamam hooks e renderizam componentes; os componentes recebem props simples e
nunca buscam dados.

**Componentes de mapa.** O `PlantingMap` é dono do `MapContainer` e da camada de
tiles; o `RegionLayer` desenha a `FeatureCollection` e trata clique e ativação por
teclado; o `RegionPopup` mostra o resumo na seleção. O `PlantingMap` recebe a
altura explicitamente do layout do pai, nunca `100%` de um ancestral sem altura.

**Vocabulário.** A palavra usada na interface para uma região é **"canteiro"**. O
usuário nunca vê "region", "polígono", "GeoJSON" ou "token". Conforme a
especificação §14, todo texto de interface é em português do Brasil, enquanto
identificadores e comentários no código permanecem em inglês.

---

## 9. Segurança e moderação

Revisado ponta a ponta pela issue #37 (Fase 7): cada item abaixo foi testado contra
o backend rodando localmente (curl, upload real, simulação de `ENVIRONMENT=production`),
não só conferido pela leitura do código. Nenhuma divergência entre este documento e o
comportamento real foi encontrada, e nenhuma correção foi necessária.

Implementado no MVP:

- Limite de tamanho no upload, validação de formato real e proteção contra bomba
  de descompressão (§6.1). Confirmado: um upload de 11 MB (limite é 10 MB) é
  rejeitado com `422 image_too_large` antes de o arquivo ser bufferizado por
  inteiro; um arquivo não-imagem enviado com extensão `.jpg` e
  `Content-Type: image/jpeg` forjados é rejeitado com `422 invalid_image`, porque
  a decisão vem da decodificação real via Pillow, nunca do que o cliente declara.
- EXIF removido de todo arquivo armazenado; GPS gravado apenas mediante adesão
  explícita (§6.2).
- Endpoints administrativos de escrita (`POST` e `PATCH /api/regions` e
  `/api/plantings`) exigem um header `X-Admin-Token` que bata com
  `ADMIN_API_TOKEN`, comparado com `secrets.compare_digest`. Confirmado: o
  backend se recusa a **subir** (falha na importação de `app.core.config`, antes
  de qualquer request) com token padrão (`troque-isto-localmente`) ou vazio
  quando `ENVIRONMENT=production`; o token nunca aparece em log (`uvicorn`
  access log e os dois `logger.exception` do backend nunca incluem headers ou
  corpo da requisição) nem em resposta de erro (401 devolve texto genérico,
  nunca o valor recebido nem o esperado).
- CORS restrito a `CORS_ALLOWED_ORIGINS`, nunca `*` — é um campo obrigatório em
  `Settings`, sem valor default. Confirmado com preflight real: origem permitida
  recebe `Access-Control-Allow-Origin`; origem fora da lista não recebe o header
  (o navegador bloqueia a leitura da resposta).
- Chaves de storage e caminhos de arquivo nunca aparecem nas respostas.
  Confirmado inspecionando a resposta crua do upload e da listagem de fotos: o
  único identificador exposto é `photo_url` (`/api/photos/{id}/file`), nunca
  `storage_key`. `regions.qr_token` também aparece nas respostas públicas, mas
  por desenho (§7): é o mesmo valor impresso no QR Code físico, não um segredo.
- `photos.status` permite ao organizador esconder conteúdo imediatamente.
- **Consentimento para fotos de pessoas identificáveis (issue #38).** Decisão
  de política tomada: fotos com pessoas identificáveis (não só plantas) são
  permitidas, **com** consentimento. O formulário de envio (`PhotoUploadForm`)
  tem duas caixas de seleção: a primeira, sempre visível e desmarcada por
  padrão, declara "esta foto inclui uma ou mais pessoas identificáveis"; ao
  marcá-la, uma segunda aparece e se torna obrigatória para enviar: "confirmo
  que tenho autorização do responsável para publicar esta foto com pessoa(s)
  identificável(is)". Marcar a primeira sem a segunda bloqueia o envio no
  frontend com mensagem clara. O backend repete a mesma regra
  (`photo_upload_service.upload_photo`, erro estruturado
  `identifiable_person_consent_required`) — não confia só na validação do
  cliente, pelo mesmo motivo que a validação de formato de imagem (§6.1)
  também não confia no `Content-Type` declarado. O resultado é persistido
  como um único booleano em `photos.includes_identifiable_person_with_consent`
  (`true` só quando as duas caixas foram marcadas); o texto exato da
  declaração vive só no frontend/nesta documentação, não duplicado no banco —
  o carimbo de tempo já existe em `uploaded_at`.

  **Isso é consentimento autodeclarado, não verificado de verdade** — o
  mesmo espírito do `contributor_name`, que também é texto livre sem
  validação. Nada aqui confirma que a pessoa que marcou a caixa é de fato o
  responsável, ou que a autorização foi realmente dada; é uma mitigação
  razoável para o tamanho atual do projeto (comunitário, sem equipe jurídica,
  sem sistema de identidade), não uma verificação jurídica de consentimento.
  A moderação continua manual: o organizador da AAMA revisa e usa
  `photos.status` (`published`/`hidden`) para esconder qualquer foto
  problemática assim que perceber ou for avisado — **sem SLA formal**, dado o
  tamanho atual do projeto. Nenhum endpoint novo de moderação foi criado; a
  correção continua sendo um `UPDATE` direto no banco, como já era o caso
  para qualquer outro motivo de esconder uma foto (§4.5). Esta decisão foi
  tomada pelo responsável do projeto antes da implementação, como pré-requisito
  para qualquer lançamento público — não é uma escolha técnica desta issue.

Documentado e adiado de propósito:

- **Rate limiting.** Reavaliado nesta revisão (#37) e adiado de novo,
  deliberadamente — não é uma lacuna esquecida. O endpoint de upload continua
  público e sem limite por IP; ele segue sendo o vetor de abuso mais claro do
  sistema. Razão para adiar de novo: o projeto ainda não tem escala nem
  visibilidade pública que justifique a complexidade operacional de um limitador
  (armazenamento de contadores, decisão de janela/threshold, risco de bloquear
  IPs compartilhados como NAT de escola ou associação de bairro) sem evidência
  concreta de abuso. Retomar quando houver sinal real de abuso (picos de envio,
  spam de conteúdo) ou quando o projeto ganhar visibilidade pública que aumente
  esse risco — o que vier primeiro.
- **Moderação de imagem.** Não há fila de moderação automática (visão
  computacional, por exemplo). A moderação humana existe e está descrita
  acima, junto da decisão de consentimento que ela agora também cobre.
- **Autenticação.** Não há contas de usuário. O token administrativo é um
  paliativo, não um sistema de autenticação; os caminhos de escrita já estão
  isolados atrás de uma única dependência, então substituí-lo é uma mudança
  contida.
- **Nome do contribuinte.** Texto livre, sem validação, exibido publicamente. A
  interface pede apenas o primeiro nome.

---

## 10. Estratégia de testes

**Backend** (`pytest`): os testes rodam contra um PostGIS real — o comportamento
do PostGIS é justamente o que mais vale testar, então ele nunca é simulado. O
banco `community_roots_test` é criado pelo script de inicialização do Compose;
cada teste roda dentro de uma transação que é revertida ao final.

Cobertura: endpoint de saúde; listagem, detalhe, criação e atualização de
canteiro, incluindo o formato da saída GeoJSON; resolução por slug e por UUID;
exigência do token administrativo; caminho feliz do envio de foto; cada caminho de
rejeição (arquivo grande demais, formato errado, bytes corrompidos); remoção de
EXIF verificada relendo o arquivo gravado; GPS gravado somente com adesão;
endpoint de QR quanto ao content type e à URL codificada.

**Frontend** (Vitest + Testing Library + MSW): validação e estados do formulário
de envio; `RegionPage` nos estados de carregamento, erro, vazio e preenchido;
ordenação da `PhotoTimeline`. Os testes de mapa ficam rasos — `react-leaflet` no
jsdom dá muito atrito para pouco retorno, então o `RegionLayer` é testado pelas
props e handlers que repassa, com o `react-leaflet` simulado.

Os roteiros de teste manual ficam no README, um por fluxo de usuário da
especificação §15.

---

## 11. Configuração

Nenhum segredo no repositório. Cada serviço lê um `.env` criado a partir do seu
`.env.example`.

| Arquivo | Consumido por |
|---|---|
| `.env` (raiz) | `docker-compose.yml` |
| `backend/.env` | FastAPI (`pydantic-settings`) |
| `frontend/.env` | Vite (só variáveis com prefixo `VITE_` chegam ao navegador) |

O `backend/app/core/config.py` falha logo na inicialização quando uma variável
obrigatória está ausente ou inválida, com uma mensagem que diz qual é a variável.

---

## 12. Caminhos de evolução

O desenho deixa estas portas abertas de propósito:

- **Chegada dos polígonos reais.** O `POST /api/regions/import` aceita uma
  `FeatureCollection` GeoJSON e casa as features com os canteiros existentes pelo
  slug, atualizando o `geom`. Os QR Codes continuam válidos porque codificam o
  `qr_token`. Shapefiles são convertidos com `ogr2ogr` antes da importação, em vez
  de interpretados dentro da aplicação.
- **Armazenamento em objeto.** Implementar `S3Storage` contra o mesmo protocolo e
  trocar o `STORAGE_BACKEND`. O endpoint de arquivo passa de transmissão para
  redirecionamento.
- **Autenticação.** Substituir a dependência do token administrativo e adicionar
  `contributor_id` em `photos`, ao lado do `contributor_name` já existente.
- **Interface administrativa.** Os services já contêm a lógica; uma interface
  admin são rotas novas e uma área no frontend, sem mudança abaixo da camada de
  rotas.
- **Recursos espaciais.** "Qual canteiro contém este ponto?", "canteiro mais
  próximo" e interseção com um limite geográfico são consultas `ST_*` diretas
  contra as colunas já indexadas por GiST.
