# Guia do organizador

Este guia é para quem organiza a área de plantio no dia a dia — não é preciso
saber programar para segui-lo. Ele cobre as quatro tarefas que o organizador
precisa fazer fora do app: cadastrar um canteiro (e as mudas dentro dele),
obter o QR Code de cada um, imprimir e instalar os códigos, e esconder uma
foto problemática.

O Community Roots ainda não tem uma tela de administração (isso está descrito
como um passo futuro em [`docs/architecture.md`](./architecture.md), §4.5 e
§12). Até lá, essas quatro tarefas são feitas por comandos de terminal — este
guia dá o comando pronto para copiar e colar em cada uma, e explica o que cada
parte dele faz.

Todos os comandos abaixo foram testados de ponta a ponta contra o backend
rodando localmente ao escrever este guia.

---

## Antes de começar

Você vai precisar de três coisas:

1. **O projeto rodando localmente** (banco de dados, backend e, se for
   conferir visualmente, o frontend) — siga
   ["Instalação" no README](../README.md#instalação) se ainda não tiver feito
   isso.
2. **Um terminal.** No Linux e no Mac, é o aplicativo "Terminal". No Windows,
   pode ser o PowerShell ou o terminal do WSL.
3. **O token administrativo.** É uma senha que autoriza ações de organizador
   (criar/editar canteiros e mudas). Ela está na variável `ADMIN_API_TOKEN`,
   dentro do arquivo `backend/.env` do projeto — abra esse arquivo com
   qualquer editor de texto para ver o valor. Nos exemplos abaixo, o valor de
   desenvolvimento é `troque-isto-localmente`; troque pelo valor real do seu
   `.env`.

Nos exemplos, o backend está em `http://localhost:8000` (o padrão de
desenvolvimento). Se o projeto já estiver publicado (em produção), troque essa
parte da URL pelo endereço real do backend.

> **Sobre os comandos `curl`.** `curl` é um programinha de linha de comando
> para "conversar" com o backend, do mesmo jeito que o navegador conversa com
> ele ao abrir uma página. Cada bloco de comando abaixo pode ser copiado e
> colado inteiro no terminal, ajustando só as partes marcadas em
> `MAIÚSCULO_COM_COMENTÁRIO`.

---

## 1. Criar um canteiro (região)

Um "canteiro", no banco de dados, se chama `Region` — é a área física maior
(por exemplo, "AAMA — Matias Barbosa"), dentro da qual ficam as mudas
individuais.

Rode este comando, trocando `nome`, `descrição` e as coordenadas do polígono
pelas do canteiro real (veja a nota sobre coordenadas logo abaixo):

```bash
curl -X POST http://localhost:8000/api/regions \
  -H "X-Admin-Token: troque-isto-localmente" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Nome do canteiro",
    "description": "Descrição opcional do canteiro",
    "geometry": {
      "type": "Polygon",
      "coordinates": [[
        [-43.312559, -21.883959],
        [-43.312359, -21.883959],
        [-43.312359, -21.883759],
        [-43.312559, -21.883759],
        [-43.312559, -21.883959]
      ]]
    }
  }'
```

O que a resposta traz — vale guardar o `id` e o `slug`, você vai usá-los nos
próximos passos:

```json
{
  "id": "97c7dc33-232f-4894-b3a3-568220f8d55b",
  "properties": {
    "slug": "nome-do-canteiro",
    "qr_token": "eTJJ5Z4ieV11",
    ...
  }
}
```

- `slug` é a versão do nome usada na URL (`/regions/nome-do-canteiro`) — gerada
  automaticamente a partir do `name`, você não escolhe.
- `qr_token` também é gerado automaticamente; é o código que vai dentro do QR
  Code (passo 2). Nunca precisa ser digitado manualmente.
- Se você esquecer o header `X-Admin-Token` (ou digitar o valor errado), a
  resposta é `401` e nenhum canteiro é criado — isso é esperado, é a proteção
  contra qualquer pessoa criar canteiros sem autorização.

**Sobre as coordenadas.** `geometry.coordinates` é uma lista de pontos
`[longitude, latitude]` (nessa ordem — é o padrão GeoJSON, invertido em
relação ao que normalmente se vê num mapa) que desenha o contorno do
canteiro, terminando no mesmo ponto em que começou. Enquanto o levantamento
geográfico real não existir, um retângulo aproximado — como o do exemplo
acima, ao redor de Matias Barbosa — já é suficiente; ele pode ser substituído
depois sem invalidar o QR Code já impresso (`docs/implementation-plan.md`,
Fase 6). Se preferir desenhar o contorno visualmente em vez de digitar
coordenadas à mão, sites como [geojson.io](https://geojson.io) exportam o
formato exato que esse campo espera.

### Cadastrar as mudas dentro do canteiro

Cada muda individual (`Planting`) é o que normalmente recebe um QR Code
físico no chão, ao lado dela — o QR do canteiro (acima) é mais para uma placa
na entrada da área, levando à visão geral. Para cadastrar uma muda dentro do
canteiro criado acima:

```bash
curl -X POST http://localhost:8000/api/plantings \
  -H "X-Admin-Token: troque-isto-localmente" \
  -H "Content-Type: application/json" \
  -d '{
    "region_id": "97c7dc33-232f-4894-b3a3-568220f8d55b",
    "geometry": {"type": "Point", "coordinates": [-43.312459, -21.883859]},
    "nickname": "Apelido da muda, ex.: Pé de Ipê-Amarelo",
    "species": "Nome da espécie, opcional"
  }'
```

Troque `region_id` pelo `id` do canteiro do passo anterior, e as coordenadas
pela posição real da muda (também `[longitude, latitude]`). A resposta traz o
`id` da muda e o `qr_token` dela, do mesmo jeito que a do canteiro.

---

## 2. Obter o QR Code de um canteiro (ou de uma muda)

Com o `slug` (ou `id`) em mãos, baixe a imagem do QR Code direto no
navegador ou por linha de comando.

**Pelo navegador:** abra
`http://localhost:8000/api/regions/{slug-ou-id}/qr-code` — a imagem aparece na
tela; clique com o botão direito para salvar. Para a muda, é
`http://localhost:8000/api/plantings/{id}/qr-code`.

**Por linha de comando**, salvando direto num arquivo:

```bash
curl "http://localhost:8000/api/regions/nome-do-canteiro/qr-code" -o qr-canteiro.png
curl "http://localhost:8000/api/plantings/ID-DA-MUDA/qr-code" -o qr-muda.png
```

Detalhes úteis:

- Funciona tanto com o `slug` (`nome-do-canteiro`) quanto com o `id` (UUID) na
  URL — os dois resolvem para o mesmo canteiro.
- Adicione `?format=svg` para receber um vetor em vez de PNG (melhor qualidade
  para impressão em tamanhos grandes): `.../qr-code?format=svg`.
- Adicione `?size=` para controlar o tamanho da imagem, de `1` até `100`
  (o número controla pixels por "módulo" do código — o padrão já produz um
  código legível; `size=20` ou mais é indicado para impressão).
- Esse endpoint **não** exige o token administrativo — qualquer pessoa com o
  link pode baixar o QR Code de um canteiro que já existe, mas ninguém
  consegue criar ou editar canteiros sem o token (passo 1).
- O QR Code nunca fica desatualizado se você renomear o canteiro depois: ele
  codifica o `qr_token` (um valor fixo, gerado uma única vez), não o nome nem
  o slug. Renomear não obriga reimprimir nada.

---

## 3. Imprimir a folha de QR Codes

**Estado atual: não existe ainda uma tela pronta no app para gerar uma folha
de impressão com vários QR Codes de uma vez** (um card por muda, formatado
para papel A4). Essa funcionalidade foi planejada, mas a issue original (#32)
foi fechada sem implementação quando o modelo de dados mudou de "canteiro
único" para "canteiro + mudas individuais" (o pivô Region/Planting), e nunca
foi refeita depois — acompanhe em
[issue #135](https://github.com/iagorosa/community-roots/issues/135).

Até essa tela existir, o caminho que funciona hoje:

1. Baixe a imagem do QR Code de cada muda (passo 2 acima, uma imagem por
   muda — prefira `?format=svg` para melhor qualidade de impressão).
2. Cole cada imagem num editor de texto ou apresentação comum (Google Docs,
   LibreOffice, Canva, etc.), um card por muda, com o apelido dela escrito ao
   lado.
3. Exporte para PDF e imprima em papel resistente à umidade, se possível —
   os códigos ficam expostos ao tempo na área de plantio.
4. **Antes de instalar em campo, teste cada código impresso escaneando com a
   câmera de um celular comum**, exatamente como alguém visitando a área
   faria — confirme que abre a muda certa antes de fixá-lo no chão.

---

## 4. Esconder uma foto

Às vezes uma foto enviada precisa sair do ar rapidamente — por exemplo, se
mostrar uma pessoa sem autorização, ou for imprópria. O projeto foi desenhado
para isso ser possível **imediatamente**, sem esperar por uma atualização do
app: existe uma coluna `status` na tabela de fotos, e o organizador desliga
uma foto trocando esse valor direto no banco de dados
(`docs/architecture.md`, §4.5 e §9). Não existe uma tela para isso ainda — é
proposital: a prioridade foi ter *algum* jeito de agir na hora, mesmo que seja
um comando, em vez de esperar uma tela de moderação completa.

### Passo 1 — descubra o `id` da foto

Toda foto pública aparece na resposta de
`GET /api/plantings/{id-da-muda}/photos`, com o seu próprio `id`:

```bash
curl "http://localhost:8000/api/plantings/ID-DA-MUDA/photos"
```

```json
{
  "items": [
    {
      "id": "3641ccf6-8a6b-49b2-b735-178959751b9f",
      "description": "Foto de teste do guia",
      "uploaded_at": "2026-09-01T21:09:03.091106Z",
      ...
    }
  ]
}
```

Anote o `id` da foto que precisa sair do ar.

### Passo 2 — esconda a foto com um comando no banco

Com o banco de dados rodando via Docker (`docker compose up -d`, como na
seção de instalação do README), rode, a partir da raiz do projeto:

```bash
docker compose exec -T db psql -U community_roots -d community_roots \
  -c "UPDATE photos SET status = 'hidden' WHERE id = 'ID-DA-FOTO';"
```

Troque `ID-DA-FOTO` pelo `id` anotado no passo 1, e `community_roots`
(usuário e nome do banco) pelos valores reais do seu `.env`, se tiverem sido
alterados. Uma resposta `UPDATE 1` confirma que a foto foi encontrada e
alterada.

**O que acontece depois desse comando**, confirmado rodando os comandos
acima contra o backend local:

- A foto some imediatamente da linha do tempo pública
  (`GET /api/plantings/{id}/photos` não a lista mais).
- O arquivo da foto também para de ser servido: `GET /api/photos/{id}/file`
  passa a responder `404`, como se a foto não existisse.
- Nada é apagado — a foto continua no banco de dados e no disco, só marcada
  como oculta. É possível reverter trocando `'hidden'` de volta para
  `'published'` no mesmo comando.

Se preferir uma ferramenta visual em vez de linha de comando, qualquer
cliente de PostgreSQL (DBeaver, TablePlus, pgAdmin) conectado com os dados de
`backend/.env` (`DATABASE_URL`) consegue fazer o mesmo `UPDATE` clicando na
linha da foto.

---

## Referência rápida

| Tarefa | Comando/URL |
|---|---|
| Criar canteiro | `POST /api/regions` com `X-Admin-Token` |
| Criar muda dentro de um canteiro | `POST /api/plantings` com `X-Admin-Token` |
| Baixar QR Code do canteiro | `GET /api/regions/{slug-ou-id}/qr-code` |
| Baixar QR Code da muda | `GET /api/plantings/{id}/qr-code` |
| Listar fotos de uma muda (achar o `id`) | `GET /api/plantings/{id}/photos` |
| Esconder uma foto | `UPDATE photos SET status = 'hidden' WHERE id = '...'` no banco |

Para o roteiro completo de teste desses fluxos, veja
[`docs/manual-testing.md`](./manual-testing.md), Fluxo C.
