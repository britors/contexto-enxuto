# contexto-enxuto

[Português](#português) · [English](#english)

## Português

Plugin do [Claude Code](https://claude.com/claude-code) que mantém o contexto enxuto. Cada resultado de ferramenta fica no contexto até compactar, e **cada resposta seguinte relê tudo**: um log de 30 mil tokens lido cedo numa sessão de 50 respostas vira 1,5 milhão de tokens processados.

### O que ele faz

- **Avisa os resultados grandes.** Quando uma chamada traz mais de ~8 mil tokens, o Claude recebe um aviso com a dica para aquela ferramenta: `head`, `grep` ou `--jq` no Bash; `offset` e `limit` no Read; `head_limit` no Grep.
- **Alerta o contexto cheio a tempo.** Ao cruzar 60% e 80% da janela, o Claude é avisado uma vez e propõe um `/compact` com um resumo do que manter. Depois de compactar, os alertas recomeçam.
- **Mostra o que mais pesou** no seu histórico, por ferramenta e comando, com o total, a mediana, o maior resultado e como reduzir.

Fora desses momentos, o hook fica em silêncio e não gasta tokens.

### Instalação

No Claude Code 2.1.275 ou mais novo, dentro de uma sessão:

```
/plugin install contexto-enxuto --marketplace britors/contexto-enxuto
```

Em versões anteriores:

```
/plugin marketplace add britors/contexto-enxuto
/plugin install contexto-enxuto@contexto-enxuto
```

Precisa de `python3` no PATH.

### Relatório

```
python3 skills/contexto-enxuto/scripts/enxuto.py relatorio [--dias 30] [--projeto trecho] [--top 15] [--md relatorio.md]
```

Exemplo real:

| Ferramenta ou comando | Chamadas | Total | % | Mediana | Maior |
| --- | ---: | ---: | ---: | ---: | ---: |
| Read: arquivo inteiro | 826 | 1.300,9 mil | 42% | 0,8 mil | 14,2 mil |
| Bash: cat | 292 | 472,6 mil | 15% | 1,2 mil | 7,3 mil |
| Bash: sed | 312 | 275,9 mil | 9% | 0,6 mil | 4,6 mil |

Você também pode pedir ao Claude: "o que está enchendo o contexto?".

### Configuração

Opcional, em `~/.claude/contexto-enxuto.json`:

```json
{"limite_resultado_tokens": 8000, "alertas_pct": [60, 80], "janela_tokens": null}
```

Sem `janela_tokens`, o plugin usa o tamanho gravado pela status line do [estimar-tokens](https://github.com/britors/estimar-tokens), se você o usa; senão, 200 mil. Os tokens são estimados como caracteres ÷ 4.

### Estrutura

```
.claude-plugin/plugin.json                    manifesto
.claude-plugin/marketplace.json               marketplace de um plugin só
skills/contexto-enxuto/SKILL.md               hábitos e como compactar
skills/contexto-enxuto/scripts/enxuto.py      hook e relatório
hooks/hooks.json                              PostToolUse
tests/test_enxuto.py                          testes
```

Para rodar os testes: `python3 -m unittest discover -s tests`.

## English

[Claude Code](https://claude.com/claude-code) plugin that keeps the context lean. Every tool result stays in context until compaction and is reread on every following turn.

- Warns Claude when a tool result exceeds ~8k tokens, with a tool-specific tip (`head`/`grep`/`--jq`, `offset`/`limit`, `head_limit`).
- Alerts once when the context crosses 60% and 80% of the window and suggests `/compact` with a summary of what to keep.
- `enxuto.py relatorio` ranks what filled your context the most in your local history, by tool and command, with an optional Markdown export.

Install with `/plugin install contexto-enxuto --marketplace britors/contexto-enxuto`.

## Licença / License

[GPL-3.0](LICENSE)
