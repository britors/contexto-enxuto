# Changelog

## 1.0.0 — 10/11/2026

- Hook `PostToolUse`:
  - avisa quando um resultado passa de ~8 mil tokens, com a dica certa para cada ferramenta;
  - alerta uma vez quando o contexto cruza 60% e 80% da janela e sugere `/compact` com resumo;
  - os alertas recomeçam depois de compactar.
- `scripts/enxuto.py relatorio`: o que mais pesou no contexto no seu histórico, por ferramenta e comando (`--dias`, `--projeto`, `--top`, `--md`).
- Skill `contexto-enxuto`: hábitos para gastar menos contexto e como compactar.
- Usa o tamanho da janela gravado pelo estimar-tokens, quando existe.
- Testes e CI.
