# Pivô de modelo de domínio: Region + Planting

Data: 2026-08-30

## Problema

O `Region` construído nas Fases 2–6 (merged em `main`) conflata dois
conceitos que deveriam ser entidades separadas: hoje `Region` é a entidade
final — tem `qr_token`, geometria e fotos (via `region_id`). Isso não
serve ao objetivo central do produto (`PROJECT_BOOTSTRAP.md`): criar senso
de pertencimento em quem planta, incentivando a pessoa a voltar e cuidar
da própria muda ao longo do tempo. Isso só funciona se o QR Code e a
linha do tempo de fotos forem por muda individual, não por
canteiro/polígono grande — os polígonos de canteiro já construídos são
grandes demais para representar o espaço de uma única muda.

## Modelo de domínio

```
Region (mantém o nome — só muda o significado semântico)
  id, slug, name, description
  geom (POINT | POLYGON | MULTIPOLYGON)
  centroid (computado via ST_Centroid, persisted)
  status
  → agrupa várias Plantings (ex.: "AAMA — Matias Barbosa";
    uma cidade pode ter várias regiões assim)

Planting (nova entidade)
  id, region_id (FK → Region, obrigatório)
  geom (POINT | POLYGON | MULTIPOLYGON) — mesma flexibilidade da Region,
    hoje representa um ponto, mas permite virar polígono no futuro sem
    precisar alterar o schema
  species (opcional) — texto livre, ex. "Ipê-amarelo"
  nickname (opcional) — nome que a pessoa dá pra própria muda
  planted_by (opcional), planted_at (opcional) — ambos opcionais, sem
    conta/login; nem todo plantio vai ter esse dado registrado
  status
  → dona das fotos e do próprio QR Code

QrCode (nova entidade compartilhada)
  id, token (unique)
  region_id (nullable FK), planting_id (nullable FK)
  CHECK: exatamente um dos dois preenchido (region_id IS NOT NULL) !=
    (planting_id IS NOT NULL)
  → tanto Region quanto Planting podem ter QR Code; na prática o uso
    principal é por Planting, mas a Region mantém a possibilidade (ex.:
    placa na entrada da área física, levando a uma página de overview)

Photo (muda a FK, resto igual)
  planting_id (FK → Planting, ondelete CASCADE) — substitui region_id
  storage_key, original_filename, content_type, byte_size, width, height,
  description, contributor_name, captured_at, uploaded_at, location,
  location_source, status
```

**Decisão de design — QrCode com duas FKs opcionais + CHECK, em vez de
referência polimórfica (`target_type` + `target_id`):** mantém integridade
referencial real do Postgres (FK de verdade), aceitando o custo de ter
que adicionar uma coluna nova se um terceiro tipo de entidade precisar de
QR Code no futuro. Preferido a uma referência polimórfica porque a
checagem de integridade ficaria só na aplicação, não no banco.

**Decisão de design — geometria flexível em ambas as entidades:** tanto
`Region.geom` quanto `Planting.geom` aceitam POINT, POLYGON ou
MULTIPOLYGON (mesmo CHECK constraint que `Region` já usa hoje). Facilita
o georreferenciamento futuro pelos profissionais da área sem exigir
redesenho de schema quando uma muda passar a ser mapeada como polígono
(ex.: canteiro individual) em vez de ponto.

**Decisão de design — fotos só em Planting:** `Photo` referencia
exclusivamente `Planting` (não há FK opcional pra `Region`). Mantém o
objetivo do produto focado — a linha do tempo é sempre por muda
individual.

**Decisão de design — Region mantém o nome:** apesar do significado
mudar (de "canteiro individual" pra "agrupamento maior"), o nome `Region`
é mantido no código (model, tabela, rotas `/api/regions`,
`RegionPage`/`RegionLayer` no frontend) para minimizar churn. Só
comentários e documentação são atualizados para refletir o novo
significado.

## Backend

**Reaproveitado quase sem mudança:**
- `region_service.py` — CRUD de Region continua igual, só muda a
  interpretação semântica dos dados que manipula.
- `qr_service.py` — a lógica de gerar/validar token não muda; passa a
  operar sobre `QrCode` em vez de escrever direto em `Region.qr_token`.
  Vira o service compartilhado usado tanto por Region quanto por
  Planting.
- `photo_upload_service.py`, `exif_processing.py`, `image_processing.py`
  — inalterados, são agnósticos de qual entidade "dona" a foto tem.

**Novo, espelhando o padrão existente:**
- `planting_service.py` — CRUD de Planting, seguindo o mesmo formato de
  `region_service.py`.
- `app/schemas/planting.py` — espelha `region.py`, com os campos
  específicos de Planting.
- `app/models/planting.py`, `app/models/qr_code.py`.

**Muda:**
- `photo_service.py` / `app/schemas/photo.py` — troca `region_id` por
  `planting_id` nas queries e no schema.
- Rotas: `POST /api/regions/{id}/photos` vira
  `POST /api/plantings/{id}/photos` (idem para `GET .../photos`).
  `GET .../qr-code` passa a existir tanto em
  `/api/regions/{id}/qr-code` quanto em `/api/plantings/{id}/qr-code`,
  ambos usando o `qr_service` compartilhado.
- `GET /api/regions/{id}` deixa de retornar fotos; passa a retornar
  `planting_count` (contagem real de plantings ativas na região, para a
  sidebar). A lista completa de plantings de uma região é obtida à parte,
  via `GET /api/plantings?region_id={id}` — endpoint dedicado, em vez de
  embutir a lista na resposta de Region, mantendo cada resposta enxuta e
  evitando duplicar a lógica de consulta de `planting_service` dentro de
  `region_service`.

## Frontend

**Mapa (`MapPage`, `PlantingMap`, `RegionLayer`, `RegionPopup`):**
- `RegionLayer` continua desenhando os polígonos/pontos de Region como
  hoje (contorno + preenchimento leve).
- Novo `PlantingClusterLayer` desenha os pins de Planting dentro de cada
  Region, com clustering (`react-leaflet-cluster` ou
  `leaflet.markercluster`): mostra um contador (ex. "🌱 32") quando o
  mapa está afastado, e "explode" nos pins individuais ao aproximar o
  zoom.
- `RegionPopup` vira um popup simples com nome + contagem de plantings;
  o clique detalhado passa a acontecer no pin da Planting.

**Detalhe — drawer (desktop) / bottom sheet (mobile):**
- Novo componente `PlantingDetailPanel` com o conteúdo que hoje mora em
  `RegionPage` (nome, apelido, espécie, quem plantou, `PhotoTimeline`,
  `PhotoUploadForm`).
- Desktop: abre como drawer lateral direito.
- Mobile: abre como bottom sheet usando uma lib pronta (`vaul` ou
  `react-spring-bottom-sheet`) em vez de implementar o gesto de
  arrastar/snap do zero — mantém o mapa visível atrás do painel,
  preservando o contexto espacial que reforça a conexão física ↔
  digital central ao produto.
- `RegionPage` (`/regions/{id}`) é mantida, mas repaginada como overview
  simples da Region: nome, descrição, lista/mapa das plantings dali,
  botão de baixar o QR Code da região. Justificativa: sem essa página, o
  QR Code de Region (mantido para uma eventual placa física na entrada
  da área) fica sem um destino útil.
- `QrRedirectPage` passa a resolver tanto QR de Region quanto de
  Planting (o token já indica pra qual das duas entidades ele aponta).

**Sidebar esquerda (novo componente `RegionSidebar`):**
- Recolhível/escondível.
- Lista regiões com busca/filtro por região e por cidade.
- Cada item mostra a contagem de plantings daquela região (ex.: "AAMA —
  32 mudas").
- Estrutura pensada para depois receber uma aba de "atividade recente"
  (feed das últimas fotos enviadas) sem precisar refazer o layout — não
  implementada agora, fora de escopo deste MVP.

**Reaproveitado sem mudança:** `PhotoCard`, `PhotoUploadForm`,
`PhotoTimeline`, `Header`, `Layout`, `LoadingState`/`ErrorState`/
`EmptyState`.

## Migração de dados

Confirmado com o usuário: não há dados reais em produção hoje, apenas
seed fictício de desenvolvimento. A migration do Alembic pode ser
destrutiva, sem lógica de preservação de linhas existentes:

- Nova migration: cria `plantings` e `qr_codes`; adiciona `planting_id`
  em `photos` (remove `region_id` dela); remove `qr_token` de `regions`
  (vira registro em `qr_codes`).
- `scripts/seed.py` é reescrito para criar Regions com Plantings dentro
  (em vez de Regions "achatadas"), mantendo o padrão idempotente já
  existente.

## Testes

Segue o padrão já estabelecido no repo (um arquivo de teste por
model/service/rota):

- Novo: `test_planting_model.py`, `test_planting_service.py`,
  `test_planting_routes.py`, `test_qr_code_model.py` (cobrindo o CHECK
  de exclusividade region_id/planting_id).
- Testes existentes (`test_region_*.py`, `test_photo_*.py`,
  `test_qr_service.py`) são ajustados (fixtures passam a usar
  `planting_id` em vez de `region_id` onde aplicável) e servem de base
  direta para os testes novos de Planting, por analogia.
- Frontend: testes de componente para `PlantingClusterLayer`,
  `PlantingDetailPanel`, `RegionSidebar`, seguindo o padrão `.test.tsx`
  já usado no repo.

## Escopo de retrabalho

Nada do que foi mergeado nas Fases 2–6 é descartado — é estendido
(`Planting` espelha `Region`) ou redirecionado (`Photo`/QR mudam de
dono). O trabalho genuinamente novo é: clustering no mapa, bottom sheet
mobile, sidebar com filtro/contagem.

## Fora de escopo deste pivô

- Feed de atividade recente na sidebar (planejado para depois do MVP).
- Autenticação/contas de usuário (já fora de escopo desde o
  `PROJECT_BOOTSTRAP.md` original).
- Importação de GeoJSON/Shapefile reais do geógrafo (a arquitetura de
  geometria flexível já viabiliza isso, mas a importação em si não é
  parte deste pivô).
