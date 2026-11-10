#!/usr/bin/env python3
"""Mantém o contexto enxuto: avisa resultados grandes, alerta o contexto cheio e mostra o que mais pesou.

    enxuto.py hook                       # PostToolUse (lê o JSON do Claude Code na entrada padrão)
    enxuto.py relatorio [--dias 30] [--projeto TRECHO] [--top 15] [--md arquivo.md]

Configuração opcional em ~/.claude/contexto-enxuto.json:
    {"limite_resultado_tokens": 8000, "alertas_pct": [60, 80], "janela_tokens": null}

Tokens são estimados como caracteres ÷ 4.
"""

import argparse
import collections
import json
import re
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HOME = Path.home()
PROJETOS = HOME / ".claude" / "projects"
ESTADO = HOME / ".claude" / "contexto-enxuto"
SALDO_ESTIMAR_TOKENS = HOME / ".claude" / "estimar-tokens" / "saldo.json"
PADRAO = {"limite_resultado_tokens": 8000, "alertas_pct": [60, 80], "janela_tokens": None}
JANELA_PADRAO = 200_000
TOKENS_IMAGEM = 1500
CAUDA_TRANSCRICAO = 512 * 1024
COMANDOS_COMPOSTOS = {"git", "gh", "npm", "pnpm", "yarn", "docker", "kubectl", "cargo", "go", "uv", "pip", "make", "dotnet"}
DICAS = {
    "Bash": "filtre a saída com `| head -n`, `| tail -n`, `grep`, `wc -l` ou `--jq`; nunca despeje log ou diff inteiro",
    "Read": "leia só o trecho necessário com `offset` e `limit`, ou procure antes com Grep",
    "Grep": "use `head_limit`, `output_mode: files_with_matches` ou um padrão mais específico",
    "Glob": "restrinja o padrão a uma pasta",
    "WebFetch": "peça no `prompt` só a informação que precisa",
}
DICA_GERAL = "peça só o necessário ou filtre o resultado"


def tokens(texto):
    return len(texto) // 4


def config():
    cfg = dict(PADRAO)
    try:
        cfg.update(json.loads((HOME / ".claude" / "contexto-enxuto.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def mil(n):
    return f"{n / 1000:,.1f} mil".replace(",", "X").replace(".", ",").replace("X", ".")


def assinatura(nome, entrada):
    """Rótulo curto da chamada: o comando no Bash, o modo no Read e no Grep, o domínio no WebFetch."""
    entrada = entrada or {}
    if nome == "Bash":
        partes = [p.strip() for p in re.split(r"&&|\|\||;|\||\n", entrada.get("command", ""))]
        partes = [p for p in partes if p and not p.startswith(("cd ", "export ", "set "))]
        palavras = [w for w in (partes[0].split() if partes else []) if "=" not in w or w.startswith("-")]
        if not palavras:
            return "Bash"
        rotulo = [palavras[0].rsplit("/", 1)[-1]]
        if rotulo[0] in COMANDOS_COMPOSTOS:
            rotulo += [w for w in palavras[1:3] if not w.startswith("-")][: 2 if rotulo[0] == "gh" else 1]
        elif rotulo[0].startswith("python") and palavras[1:2] == ["-m"]:
            rotulo += palavras[1:3]
        return "Bash: " + " ".join(rotulo)
    if nome == "Read":
        return "Read: " + ("trecho" if entrada.get("offset") or entrada.get("limit") else "arquivo inteiro")
    if nome == "Grep":
        return "Grep: " + entrada.get("output_mode", "files_with_matches")
    if nome == "WebFetch":
        return "WebFetch: " + (urlparse(entrada.get("url", "")).netloc or "?")
    return nome


def tamanho_resultado(conteudo):
    if isinstance(conteudo, str):
        return tokens(conteudo)
    if isinstance(conteudo, list):
        total = 0
        for c in conteudo:
            if isinstance(c, dict) and c.get("type") == "image":
                total += TOKENS_IMAGEM
            elif isinstance(c, dict):
                total += tokens(c.get("text", "") or json.dumps(c, ensure_ascii=False))
            else:
                total += tokens(str(c))
        return total
    return tokens(json.dumps(conteudo, ensure_ascii=False)) if conteudo else 0


# Hook

def contexto_da_transcricao(caminho):
    """Contexto da última resposta do assistente, lido do fim do registro da sessão."""
    try:
        with open(caminho, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - CAUDA_TRANSCRICAO))
            linhas = f.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for linha in reversed(linhas):
        try:
            d = json.loads(linha)
        except ValueError:
            continue
        uso = (d.get("message") or {}).get("usage") if d.get("type") == "assistant" else None
        if uso:
            return uso.get("input_tokens", 0) + uso.get("cache_creation_input_tokens", 0) + uso.get("cache_read_input_tokens", 0)
    return None


def janela(cfg):
    if cfg.get("janela_tokens"):
        return cfg["janela_tokens"]
    try:
        return json.loads(SALDO_ESTIMAR_TOKENS.read_text()).get("contexto_tamanho") or JANELA_PADRAO
    except (OSError, ValueError):
        return JANELA_PADRAO


def alerta_contexto(dados, cfg, extra):
    """Avisa uma vez a cada limite cruzado; zera quando o contexto cai (depois de compactar)."""
    sid, caminho = dados.get("session_id"), dados.get("transcript_path")
    if not sid or not caminho:
        return None
    ctx = contexto_da_transcricao(caminho)
    if ctx is None:
        return None
    pct = (ctx + extra) * 100 / janela(cfg)
    arq = ESTADO / "sessoes" / f"{sid}.json"
    try:
        avisado = json.loads(arq.read_text()).get("avisado", 0)
    except (OSError, ValueError):
        avisado = 0
    limites = sorted(cfg["alertas_pct"])
    cruzado = max([l for l in limites if pct >= l], default=0)
    if cruzado <= avisado and not (pct < limites[0] - 10 and avisado):
        return None
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps({"avisado": cruzado}))
    if cruzado <= avisado:  # o contexto caiu: só zera
        return None
    urgencia = "Termine a etapa atual num ponto consistente e" if cruzado >= limites[-1] else "Na próxima pausa natural,"
    return (
        f"[contexto-enxuto] O contexto está em ~{pct:.0f}% da janela ({mil(ctx + extra)} tokens). {urgencia} "
        "proponha ao usuário rodar `/compact` com um resumo do que manter: objetivo, decisões, arquivos tocados, "
        "o que falta e o que já foi descartado."
    )


def hook():
    try:
        dados = json.load(sys.stdin)
    except ValueError:
        return 0
    cfg = config()
    nome = dados.get("tool_name", "?")
    resposta = dados.get("tool_response")
    tam = tamanho_resultado(resposta if not isinstance(resposta, dict) else json.dumps(resposta, ensure_ascii=False))
    avisos = []
    if tam > cfg["limite_resultado_tokens"]:
        rotulo = assinatura(nome, dados.get("tool_input"))
        avisos.append(
            f"[contexto-enxuto] O resultado de {rotulo} trouxe ~{mil(tam)} tokens ao contexto, e cada resposta "
            f"seguinte relê tudo. Da próxima vez, {DICAS.get(nome, DICA_GERAL)}."
        )
    alerta = alerta_contexto(dados, cfg, tam)
    if alerta:
        avisos.append(alerta)
    if not avisos:
        return 0
    print("\n".join(avisos), file=sys.stderr)
    return 2


# Relatório

def chamadas(arquivo):
    """(assinatura, tokens do resultado) de cada chamada de ferramenta do registro."""
    pedidos = {}
    with open(arquivo, encoding="utf-8", errors="replace") as f:
        for linha in f:
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            conteudo = (d.get("message") or {}).get("content")
            if not isinstance(conteudo, list):
                continue
            for c in conteudo:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    pedidos[c.get("id")] = assinatura(c.get("name", "?"), c.get("input"))
                elif c.get("type") == "tool_result" and c.get("tool_use_id") in pedidos:
                    yield pedidos.pop(c["tool_use_id"]), tamanho_resultado(c.get("content"))


def relatorio(argv):
    ap = argparse.ArgumentParser(prog="enxuto.py relatorio", description="O que mais pesou no contexto.")
    ap.add_argument("--dias", type=int, default=30)
    ap.add_argument("--projeto", default="", help="só projetos cujo diretório contém este trecho")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--md", help="grava o relatório neste arquivo Markdown")
    a = ap.parse_args(argv)

    limite = time.time() - a.dias * 86400
    arquivos = [
        p for p in PROJETOS.glob("**/*.jsonl")
        if p.stat().st_mtime >= limite and a.projeto in str(p.relative_to(PROJETOS))
    ]
    grupos = collections.defaultdict(list)
    for arq in arquivos:
        for rotulo, tam in chamadas(arq):
            grupos[rotulo].append(tam)
    if not grupos:
        sys.exit(f"Nenhuma chamada de ferramenta em {PROJETOS} nos últimos {a.dias} dias.")

    total = sum(sum(v) for v in grupos.values())
    ordem = sorted(grupos.items(), key=lambda kv: -sum(kv[1]))
    linhas = [
        f"# O que mais pesou no contexto ({time.strftime('%d/%m/%Y')}, últimos {a.dias} dias)",
        "",
        f"{sum(len(v) for v in grupos.values())} chamadas em {len(arquivos)} registros trouxeram "
        f"~{mil(total)} tokens de resultados ao contexto.",
        "",
        "| Ferramenta ou comando | Chamadas | Total | % | Mediana | Maior | Como reduzir |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for rotulo, v in ordem[: a.top]:
        dica = DICAS.get(rotulo.split(":")[0], DICA_GERAL).replace("|", "\\|")
        linhas.append(
            f"| {rotulo} | {len(v)} | {mil(sum(v))} | {sum(v) * 100 / total:.0f}% | "
            f"{mil(statistics.median(v))} | {mil(max(v))} | {dica} |"
        )
    linhas += [
        "",
        "Cada resultado continua no contexto até compactar, e cada resposta seguinte o relê. "
        "Tokens estimados como caracteres ÷ 4.",
    ]
    texto = "\n".join(linhas) + "\n"
    print(texto)
    if a.md:
        Path(a.md).write_text(texto, encoding="utf-8")
        print(f"Gravado em {a.md}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["hook"]:
        sys.exit(hook())
    if sys.argv[1:2] == ["relatorio"]:
        sys.exit(relatorio(sys.argv[2:]))
    sys.exit(__doc__)
