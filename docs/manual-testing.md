# Community Roots — Roteiros de teste manual

Passo a passo dos três fluxos do [PROJECT_BOOTSTRAP.md §15](../PROJECT_BOOTSTRAP.md),
para validar manualmente que o app funciona de ponta a ponta antes de um
lançamento ou depois de uma mudança relevante. O README tem a versão resumida
([seção "Teste manual"](../README.md#teste-manual)); este documento existe para
quem vai efetivamente rodar o teste e precisa saber o que clicar e o que
conferir em cada passo.

Pré-requisitos: backend, frontend e banco de dados rodando localmente (veja
["Instalação" no README](../README.md#instalação)), com pelo menos uma região
e uma muda cadastradas — o `scripts/seed.py` resolve isso.

Rode os três fluxos numa tela de celular de verdade sempre que possível. Se só
tiver o navegador do computador, abra o DevTools e simule uma viewport de
360 px de largura — é a pior largura de tela realista, e a que a maioria de
quem contribui vai usar de pé, na área de plantio.

---

## Fluxo A — Explorar o mapa

Alguém curioso chega ao site sem saber nada do projeto e quer entender do que
se trata.

| # | Passo | O que conferir | Resultado esperado |
|---|---|---|---|
| 1 | Abra a página inicial (`/`). | O texto explica o que é o projeto em linguagem simples, sem jargão técnico. | Fica claro, em poucos segundos de leitura, que é um projeto de plantio comunitário com um mapa das mudas. |
| 2 | Siga a chamada para ação da página inicial. | Existe um botão ou link óbvio levando ao mapa. | Você chega em `/mapa` sem precisar adivinhar a URL. |
| 3 | Observe o mapa carregando. | O mapa cobre a tela sem faixa cinza nem scroll horizontal, mesmo em 360 px de largura. | O mapa ocupa o espaço disponível e é utilizável imediatamente. |
| 4 | Localize os marcadores/clusters de mudas. | Existe pelo menos uma muda visível (do seed ou de dados reais). | Os marcadores aparecem sobre o mapa do OpenStreetMap, sem geometria "grudada" na origem `(0,0)`. |
| 5 | Toque num marcador (ou num cluster, se as mudas estiverem agrupadas). | Ao tocar num cluster, o mapa aproxima e separa os marcadores; ao tocar numa muda individual, abre o painel/gaveta de detalhe. | A gaveta de detalhe (desktop: lateral; celular: por baixo) mostra o nome/apelido da muda. |
| 6 | Abra a página da muda a partir da gaveta. | Existe um link "ver detalhes" ou equivalente. | A URL muda para a página da muda e a linha do tempo de fotos aparece (vazia ou com fotos, dependendo dos dados). |
| 7 | Volte ao mapa e repita com o teclado, sem mouse/touch. | Navegue até um marcador com Tab e ative com Enter/Espaço. | O marcador focado tem um contorno de foco visível, e a ativação por teclado abre o mesmo painel do passo 5. |

**Fluxo A passou** se uma pessoa sem contexto nenhum consegue, sozinha, entender
o projeto, abrir o mapa e chegar à linha do tempo de uma muda.

---

## Fluxo B — Contribuir pelo QR Code

Alguém está fisicamente na área de plantio, escaneia o QR Code de uma muda e
envia uma foto.

| # | Passo | O que conferir | Resultado esperado |
|---|---|---|---|
| 1 | Obtenha o QR Code de uma muda: `GET /api/plantings/{planting_id}/qr-code` (ou o de uma região, `GET /api/regions/{region}/qr-code`). Veja o [guia do organizador](./organizer-guide.md#2-obter-o-qr-code-de-um-canteiro-ou-de-uma-muda) para como pegar um `planting_id`/slug real. | O endpoint responde com uma imagem (`png` por padrão). | Uma imagem de QR Code válida é devolvida, sem erro. |
| 2 | Exiba essa imagem numa tela (ou imprima-a) e escaneie com a câmera do celular, como alguém no campo faria. | O celular reconhece o QR Code e oferece abrir o link. | O link aponta para `{PUBLIC_WEB_BASE_URL}/r/{qr_token}`. |
| 3 | Toque no link. | O app abre a rota `/r/:qrToken`. | Você é redirecionado automaticamente para a página da muda (ou da região) correspondente, sem passar pelo mapa. |
| 4 | Observe a linha do tempo. | Fotos anteriores (se houver) aparecem, mais recentes primeiro. | Nenhuma foto com `status: hidden` aparece (não dá pra confirmar isso só olhando a tela — ver a nota abaixo). |
| 5 | Toque em "Enviar uma foto". | O formulário de envio abre. | Campos: seleção de arquivo, observação opcional, nome opcional, e as caixas de seleção de localização/consentimento (ver arquitetura §6.2 e §9). |
| 6 | Selecione uma foto do rolo da câmera. | Aparece uma prévia imediata da imagem escolhida. | A prévia bate com o arquivo selecionado antes mesmo de enviar. |
| 7 | Preencha uma observação opcional e envie. | O botão mostra um estado de progresso e fica desabilitado durante o envio, evitando envio duplicado. | O envio conclui sem erro. |
| 8 | Confirme que a foto apareceu. | A linha do tempo se atualiza sozinha, sem precisar recarregar a página. | A foto enviada aparece no topo da linha do tempo. |
| 9 (opcional) | Repita o envio marcando "esta foto inclui pessoa(s) identificável(is)" sem marcar a confirmação de autorização. | O formulário bloqueia o envio com uma mensagem clara. | Não é possível enviar sem marcar as duas caixas juntas (architecture.md §9). |

Nota sobre o passo 4: como o status `hidden` de uma foto só existe no banco
(não há filtro visível na tela), confirmar que uma foto oculta realmente não
aparece exige inspecionar a resposta de `GET /api/plantings/{id}/photos`
diretamente (ou usar os testes automatizados de
`backend/tests/test_photo_routes.py::test_list_photos_hides_photos_marked_hidden`,
que já cobrem esse caso).

**Fluxo B passou** se uma foto tirada na hora, sem nenhum conhecimento prévio
do app, aparece na linha do tempo pública em menos de um minuto.

---

## Fluxo C — Organizador

O organizador cria um canteiro (região) ou uma muda, obtém o QR Code e prepara
a instalação física. Este fluxo é detalhado passo a passo no
[Guia do organizador](./organizer-guide.md) — aqui vai só o roteiro de
validação rápida.

| # | Passo | O que conferir | Resultado esperado |
|---|---|---|---|
| 1 | Crie uma região via `POST /api/regions` com o header `X-Admin-Token`. | A resposta é `201` com a `Feature` GeoJSON da região criada. | `qr_token` já vem preenchido — foi gerado automaticamente, não precisa ser enviado no payload. |
| 2 | Repita sem o header `X-Admin-Token`. | A resposta é `401`. | O texto do erro não vaza o token esperado nem detalhe técnico (architecture.md §9). |
| 3 | Obtenha o QR Code da região criada. | `GET /api/regions/{region}/qr-code` responde com uma imagem. | A imagem abre normalmente num visualizador de imagens. |
| 4 | Escaneie o QR Code impresso (ou numa tela) com a câmera de um celular comum. | O link decodificado funciona (mesma checagem do Fluxo B, passo 2–3). | Abre o canteiro certo. |
| 5 | Marque uma foto existente como oculta (`UPDATE photos SET status = 'hidden' WHERE id = '...'`, ver o guia do organizador). | A foto some da linha do tempo pública. | `GET /api/plantings/{id}/photos` não lista mais essa foto; `GET /api/photos/{photo_id}/file` responde `404` para o arquivo dela. |

**Fluxo C passou** se o organizador consegue, sem ajuda de quem programou o
projeto, criar um canteiro, imprimir o QR Code dele e escondê-lo de novo caso
precise — usando só o [Guia do organizador](./organizer-guide.md).

---

## Notas gerais

- Teste sempre numa viewport de 360 px de largura — é a experiência principal
  para quem está de pé na área de plantio (README, "Convenções do projeto").
- Nenhum fluxo deve expor stack trace, string em inglês, ou detalhe técnico
  (URL de storage, nome de coluna do banco) para quem está usando o app.
- Se algum desses passos falhar, o comportamento esperado está descrito com
  mais detalhe em [`docs/architecture.md`](./architecture.md) — em especial as
  seções 4.5 (colunas `status`), 5 (desenho da API), 6.2 (EXIF/privacidade) e 9
  (segurança e moderação).
