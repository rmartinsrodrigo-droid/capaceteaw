# Publicar o Capacete AW no Vercel — pelo seu Mac

O Vercel não deixa eu subir os arquivos daqui (segurança deles). Mas o deploy é
literalmente **um comando** no seu Mac. Sem GitHub. Vou te levar passo a passo.

---

## Antes: o que muda no Vercel (importante)

O Vercel não guarda banco nem arquivos sozinho — ele liga isso com dois "plugins"
de um clique no painel. Então o deploy acontece em duas fases:
1. Subir o app (fica no ar, mas ainda sem memória).
2. Ligar o banco (Postgres) e o armazenamento de artes (Blob) no painel.

Eu já adaptei todo o código pra funcionar assim. Você só segue os cliques.

---

## Fase 1 — subir o app (Terminal)

Descompacte o zip numa pasta. Abra o **Terminal** e cole, uma linha por vez:

```bash
npm install -g vercel
```

Depois entre na pasta do app. O jeito sem errar: digite `cd ` (com espaço) e
**arraste a pasta `capaceteaw_vercel` pra dentro do Terminal**, e dê Enter:

```bash
cd  <a pasta aparece aqui ao arrastar>
```

Agora:

```bash
vercel
```

Na primeira vez ele vai:
- Pedir pra você fazer login (abre o navegador, você confirma).
- Perguntar **"Set up and deploy?"** → responda `y` (Enter).
- Perguntar a conta (**scope**) → escolha a sua.
- **"Link to existing project?"** → `n`.
- **Project name** → Enter (aceita `capaceteaw`).
- **In which directory is your code?** → Enter (aceita `./`).
- Detectar as configurações → Enter pra aceitar.

Ele constrói e te dá um endereço tipo `https://capaceteaw-xxxx.vercel.app`.
Já está no ar (a página inicial abre). Falta dar memória pra ele.

---

## Fase 2 — ligar banco e arquivos (painel, sem terminal)

Entre em **vercel.com**, abra o projeto **capaceteaw**:

**Banco de dados (Postgres):**
1. Aba **Storage** → **Create Database** → escolha **Postgres** (Neon).
2. Dê um nome qualquer e crie. Conecte ao projeto **capaceteaw** quando perguntar.
   O Vercel injeta a conexão sozinho — você não copia senha nenhuma.

**Armazenamento das artes (Blob):**
3. Ainda em **Storage** → **Create** → **Blob**. Crie e conecte ao projeto.

**Chave de segurança:**
4. Aba **Settings** → **Environment Variables** → adicione:
   - Nome: `SECRET_KEY`  | Valor: qualquer frase longa e aleatória sua.

**E-mail (opcional, pra o código de login chegar na caixa):**
5. Ainda em Environment Variables, adicione `SMTP_HOST = smtp.office365.com`,
   `SMTP_PORT = 587`, `SMTP_USER` e `SMTP_PASS` (seu e-mail e senha de app do M365),
   `SMTP_FROM` (o mesmo e-mail). Sem isso, o código aparece nos logs do Vercel.

---

## Fase 3 — republicar pra valer

Depois de ligar as coisas acima, volte ao Terminal, na mesma pasta, e rode:

```bash
vercel --prod
```

Pronto — agora o app está no ar **com memória**: guarda pedidos, logins e artes.

Sempre que você (ou eu) mudar algum arquivo, é só rodar `vercel --prod` de novo.

---

## Como testar que deu certo

No endereço do app, abra **/docs** no final (ex: `.../docs`). Ali dá pra testar tudo:
pedir o código de login, entrar, criar pedido, mudar status. Os 4 perfis de teste já
existem (marketing@, compras@, fornecedor@, solicitante@athiewohnrath.com.br).

---

## O que ainda falta (honesto)

- **Tela de login bonita**: o login funciona pela `/docs`; a telinha visual ainda não
  existe. É o próximo passo se você quiser cara de produto.
- **Custo**: o Postgres e o Blob do Vercel têm um nível grátis generoso pra começar;
  se o uso crescer, eles cobram por consumo. Sem cartão pra testar.
