"""Testes do contexto-enxuto: hook e relatório, com HOME temporário."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "contexto-enxuto" / "scripts" / "enxuto.py"


class Enxuto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.transcricao = self.home / "sessao.jsonl"
        self.contexto(10_000)

    def tearDown(self):
        self.tmp.cleanup()

    def contexto(self, n):
        uso = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": n}
        self.transcricao.write_text(json.dumps({"type": "assistant", "message": {"id": "m", "usage": uso}}) + "\n")

    def config(self, **kv):
        (self.home / ".claude").mkdir(exist_ok=True)
        (self.home / ".claude" / "contexto-enxuto.json").write_text(json.dumps(kv))

    def rodar(self, *args, entrada=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], input=entrada, capture_output=True, text=True,
            env={**os.environ, "HOME": str(self.home)},
        )

    def hook(self, nome="Bash", entrada=None, resposta="ok"):
        dados = {
            "session_id": "s1", "transcript_path": str(self.transcricao), "tool_name": nome,
            "tool_input": entrada or {"command": "ls"}, "tool_response": resposta,
        }
        return self.rodar("hook", entrada=json.dumps(dados))

    # Resultados grandes
    def test_resultado_pequeno(self):
        r = self.hook()
        self.assertEqual((r.returncode, r.stderr), (0, ""))

    def test_resultado_grande_bash(self):
        r = self.hook(entrada={"command": "cd x && git diff HEAD~3"}, resposta={"stdout": "x" * 40_000})
        self.assertEqual(r.returncode, 2)
        self.assertIn("Bash: git diff", r.stderr)
        self.assertIn("| head -n", r.stderr)

    def test_resultado_grande_read(self):
        r = self.hook("Read", {"file_path": "/a.py"}, "x" * 40_000)
        self.assertIn("Read: arquivo inteiro", r.stderr)
        self.assertIn("offset", r.stderr)

    def test_limite_configuravel(self):
        self.config(limite_resultado_tokens=100)
        self.assertEqual(self.hook(resposta="x" * 1000).returncode, 2)

    # Contexto cheio
    def test_alerta_uma_vez_por_limite(self):
        self.config(janela_tokens=100_000)
        self.contexto(65_000)
        r = self.hook()
        self.assertEqual(r.returncode, 2)
        self.assertIn("~65% da janela", r.stderr)
        self.assertIn("Na próxima pausa natural", r.stderr)
        self.assertEqual(self.hook().returncode, 0)

        self.contexto(85_000)
        r = self.hook()
        self.assertIn("Termine a etapa atual", r.stderr)
        self.assertEqual(self.hook().returncode, 0)

    def test_compactar_zera_os_alertas(self):
        self.config(janela_tokens=100_000)
        self.contexto(65_000)
        self.hook()
        self.contexto(20_000)
        self.assertEqual(self.hook().returncode, 0)
        self.contexto(66_000)
        self.assertEqual(self.hook().returncode, 2)

    def test_janela_do_estimar_tokens(self):
        pasta = self.home / ".claude" / "estimar-tokens"
        pasta.mkdir(parents=True)
        (pasta / "saldo.json").write_text(json.dumps({"contexto_tamanho": 1_000_000}))
        self.contexto(150_000)  # 75% de 200 mil, mas 15% de 1 milhão
        self.assertEqual(self.hook().returncode, 0)

    # Relatório
    def test_relatorio(self):
        proj = self.home / ".claude" / "projects" / "p"
        proj.mkdir(parents=True)
        linhas = []
        for i, (nome, entrada, tam) in enumerate([
            ("Bash", {"command": "gh run view 1 --log"}, 40_000),
            ("Bash", {"command": "gh run view 2 --log"}, 20_000),
            ("Read", {"file_path": "/a.py", "offset": 1, "limit": 10}, 400),
        ]):
            linhas.append({"type": "assistant", "message": {"content": [
                {"type": "tool_use", "id": f"t{i}", "name": nome, "input": entrada}]}})
            linhas.append({"type": "user", "message": {"content": [
                {"type": "tool_result", "tool_use_id": f"t{i}", "content": "x" * tam}]}})
        (proj / "s.jsonl").write_text("\n".join(json.dumps(l) for l in linhas) + "\n")

        md = self.home / "r.md"
        r = self.rodar("relatorio", "--md", str(md))
        self.assertEqual(r.returncode, 0, r.stderr)
        texto = md.read_text()
        self.assertIn("| Bash: gh run view | 2 | 15,0 mil | 99% |", texto)
        self.assertIn("| Read: trecho | 1 | 0,1 mil |", texto)
        self.assertIn("\\| head -n", texto)


if __name__ == "__main__":
    unittest.main()
