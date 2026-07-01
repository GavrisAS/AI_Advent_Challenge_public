"""Snapshot-local CLI for the reproducible Day 22 scenario."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_advent_agent.rag.embeddings import HashEmbeddingBackend, OllamaEmbeddingBackend
from ai_advent_agent.rag.llm import DeepSeekRagLLM, FakeLLM
from ai_advent_agent.rag.reports import run_rag_comparison


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 22 snapshot scenarios")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    demo = subparsers.add_parser("first-rag-query-demo")
    demo.add_argument("--corpus-dir", type=Path, default=Path("../corpus"))
    demo.add_argument("--questions-json", type=Path, default=Path("../eval/control-questions.json"))
    demo.add_argument("--output-dir", type=Path, default=Path("../artifacts"))
    demo.add_argument("--embedding-backend", choices=("ollama", "hash"), default="ollama")
    demo.add_argument("--embedding-model", default="nomic-embed-text")
    demo.add_argument("--ollama-url", default="http://localhost:11434")
    demo.add_argument("--hash-dim", type=int, default=128)
    demo.add_argument("--llm-provider", choices=("deepseek", "fake"), default="deepseek")
    demo.add_argument("--model", default="deepseek-v4-flash")
    demo.add_argument("--top-k", type=int, default=4)
    demo.add_argument("--rebuild-index", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    backend = (
        HashEmbeddingBackend(args.hash_dim)
        if args.embedding_backend == "hash"
        else OllamaEmbeddingBackend(args.embedding_model, args.ollama_url)
    )
    llm = FakeLLM() if args.llm_provider == "fake" else DeepSeekRagLLM(args.model)
    payload = run_rag_comparison(
        args.corpus_dir,
        args.questions_json,
        args.output_dir,
        backend,
        llm,
        top_k=args.top_k,
        rebuild_index=args.rebuild_index,
    )
    report_path = args.output_dir / "rag-comparison.md"
    print(f"Готово: {len(payload['questions'])} вопросов, отчёт {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
