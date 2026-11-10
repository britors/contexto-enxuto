---
name: contexto-enxuto
description: Esta skill deve ser usada quando o hook contexto-enxuto avisar de um resultado grande ou do contexto cheio, antes de ler muitos arquivos ou logs, e quando o usuário perguntar "o que está enchendo o contexto", "por que a sessão ficou cara", "quando compactar" ou pedir para "compactar". This skill should be used when the contexto-enxuto hook warns about a large result or a full context, before reading many files or logs, and when the user asks "what is filling the context", "why is this session expensive" or "when should I compact".
---

# Contexto enxuto

Cada resultado de ferramenta fica no contexto até compactar, e **cada resposta seguinte relê o contexto inteiro**. Um log de 30 mil tokens lido no início de uma sessão de 50 respostas custa 1,5 milhão de tokens processados.

O script fica em `scripts/enxuto.py`, ao lado deste SKILL.md. Use o caminho absoluto.

## Hábitos

- **Bash:** filtre sempre com `| head -n 50`, `| tail -n 50`, `grep`, `wc -l`, `--jq` ou `--stat`. Para logs de CI, pegue só as linhas de erro.
- **Arquivos:** procure com Grep antes e leia com `offset` e `limit`. Ler um arquivo inteiro só vale a pena quando ele é curto ou quando você vai editá-lo todo.
- **Grep:** comece com `output_mode: files_with_matches` ou `head_limit`.
- **Web:** no `prompt` do WebFetch, peça só a informação que precisa.
- **Não releia** o que já está na conversa.

## Quando o hook avisar

- **Resultado grande:** não repita a chamada. Siga com o que já tem e use a dica nas próximas.
- **Contexto em 60% ou mais:** na próxima pausa natural, proponha ao usuário um `/compact` com instruções. Por exemplo:

  ```
  /compact Manter: objetivo <...>; decisões <...>; arquivos alterados <...>; o que falta <...>. Descartar: logs, buscas já resolvidas, tentativas que falharam.
  ```

- **Contexto em 80% ou mais:** termine a etapa num estado consistente (commit, arquivo salvo) antes de propor o `/compact`, ou proponha recomeçar numa sessão nova com um resumo.

## Relatório

Para mostrar o que mais pesou no contexto:

```
python3 <pasta desta skill>/scripts/enxuto.py relatorio [--dias 30] [--projeto <trecho>] [--top 15] [--md relatorio.md]
```

O relatório lê o histórico em `~/.claude/projects` e agrupa as chamadas por ferramenta e comando, com o total, a mediana, a maior e como reduzir. Mostre ao usuário as três primeiras linhas e o hábito que mais economizaria.
