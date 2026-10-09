# Créditos das imagens de `frontend/public/brand/`

Imagens de identidade dos tenants, servidas em `/brand/`. Toda imagem de
terceiro entra aqui com origem, autor e licença — e, quando a licença exigir
atribuição, o crédito também vai em `tenant.imagem_login_credito`, que é o que
aparece na tela de login.

| Arquivo | O que é | Origem | Autor | Licença |
|---|---|---|---|---|
| `itaitinga-brasao.png` | Brasão de Itaitinga (recorte quadrado de `itaitinga-logo.png`) | https://www.itaitinga.ce.gov.br/imagens/logo.png | Prefeitura Municipal de Itaitinga | Símbolo oficial do município |
| `itaitinga-logo.png` | Marca da Prefeitura de Itaitinga | https://www.itaitinga.ce.gov.br/imagens/logo.png | Prefeitura Municipal de Itaitinga | Símbolo oficial do município |
| `itaitinga-serra.jpg` | Serra de Itaitinga, reduzida a 1920 px de largura | https://commons.wikimedia.org/wiki/File:Serra_de_Itaitinga_-_CE.jpg | Lourenco e Silva | [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/) |
| `aprimora-logo.png` | Marca da Aprimora (o produto), recortada na caixa de tinta | `public/img/logo-aprimora.png` do repositório `jalcoforado/aprimora` | Aprimora | Marca própria |
| `aprimora-logo-escuro.png` | A mesma marca para o tema escuro: o navy do wordmark trocado por claro, laranja intacto | derivada de `aprimora-logo.png` | Aprimora | Marca própria |

As duas da Aprimora têm só 211×30 px (é o que existia no sistema antigo). Servem
até ~24 px de altura; para uso maior é preciso o vetor original.

A tela de login exibe `itaitinga-serra.jpg` em tons de cinza, tingida na cor do
tenant por CSS. O arquivo em si não é alterado além do redimensionamento.
