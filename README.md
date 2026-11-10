# claude-fonte

Troca de onde o Claude Code tira o acesso, com um comando:

| Fonte | O que é |
|---|---|
| `portal` | Proxy oficial da Seazone (ia.seazone.dev) |
| `login` | Login normal do Claude Code (`/login`) |
| `switcher` | Conta do pool do claude-switcher, com troca automática quando bate o limite |

## Instalar

```sh
git clone <este repo> ~/claude-fonte
ln -s ~/claude-fonte/claude-fonte ~/.local/bin/claude-fonte
```

Precisa de Python 3.10+. Para `portal`, rode antes o instalador do portal (`curl -fsSL https://ia.seazone.dev/install.sh | sh`). Para `switcher`, o comando `switcher` precisa estar instalado.

## Usar

| Comando | O que faz |
|---|---|
| `claude-fonte` | Mostra a fonte atual e o que falta (login do switcher, chave do portal) |
| `claude-fonte usar portal` / `login` / `switcher` | Troca a fonte |
| `claude-fonte testar` | Faz uma pergunta curta e diz se respondeu e em quanto tempo |
| `claude-fonte login-switcher` | Login Google do switcher num servidor sem navegador (veja abaixo) |
| `claude-fonte reabrir` | Para quem usa agent-deck: reabre as sessões paradas para pegarem a fonte nova |

Depois de trocar, feche e abra o Claude Code (as sessões abertas continuam na fonte antiga).

## Login do switcher dá "conexão recusada"?

Acontece quando o Claude roda num servidor (VPS) e o navegador está no seu computador. O Google devolve o login para `127.0.0.1:<porta>`, que no navegador é o seu computador, mas quem espera é o servidor.

```sh
claude-fonte login-switcher
```

1. Abra o link que ele mostra e entre com a conta Seazone.
2. Vai aparecer "conexão recusada". É normal.
3. Copie o endereço inteiro da barra do navegador e cole no terminal.
4. Pronto: `claude-fonte usar switcher`.

Funciona sem nenhum Claude disponível.

## Cuidados que o comando já toma

- Faz backup do `~/.claude/settings.json` antes de cada troca (`~/.local/state/claude-fonte/backup`). Só mexe em `apiKeyHelper`, `env.ANTHROPIC_BASE_URL` e no gancho de limite do switcher.
- Nunca abre `.credentials.json`, sessão do switcher nem chave.
- Saindo do switcher com conta do pool em uso: desliga o heartbeat, devolve a conta (`switcher logout`) e avisa para rodar `/login`. Uma conta do pool renovada por dois lugares cai para a empresa toda.
- Nunca roda `switcher login` sem `--somente-login`: o login não pega conta do pool sozinho.

## Testes

```sh
python3 -m unittest discover -s testes
```

Rodam num HOME descartável, com systemctl, switcher e agent-deck falsos.
