"""Snapshot-local CLI воспроизводимого сценария Day 23."""

from __future__ import annotations

import argparse
from pathlib import Path

from ai_advent_agent.rag.embeddings import HashEmbeddingBackend, OllamaEmbeddingBackend
from ai_advent_agent.rag.llm import DeepSeekRagLLM, FakeLLM
from ai_advent_agent.rag.reports_day23 import run_day23_comparison


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Day 23 snapshot scenarios")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    demo = subparsers.add_parser("reranking-filtering-demo")
    demo.add_argument("--corpus-dir", type=Path, default=Path("../corpus"))
    demo.add_argument("--questions-json", type=Path, default=Path("../eval/control-questions.json"))
    demo.add_argument("--output-dir", type=Path, default=Path("../artifacts"))
    demo.add_argument("--embedding-backend", choices=("ollama", "hash"), default="ollama")
    demo.add_argument("--embedding-model", default="nomic-embed-text")
    demo.add_argument("--ollama-url", default="http://localhost:11434")
    demo.add_argument("--hash-dim", type=int, default=128)
    demo.add_argument("--llm-provider", choices=("deepseek", "fake"), default="deepseek")
    demo.add_argument("--model", default="deepseek-v4-flash")
    demo.add_argument("--rewrite-mode", choices=("none", "heuristic", "llm"), default="heuristic")
    demo.add_argument(
        "--rerank-mode",
        choices=("none", "similarity_threshold", "heuristic"),
        default="heuristic",
    )
    demo.add_argument("--top-k-plain", type=int, default=4)
    demo.add_argument("--top-k-before", type=int, default=8)
    demo.add_argument("--top-k-after", type=int, default=4)
    demo.add_argument("--similarity-threshold", type=float, default=0.25)
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
    payload = run_day23_comparison(
        args.corpus_dir,
        args.questions_json,
        args.output_dir,
        backend,
        llm,
        plain_top_k=args.top_k_plain,
        improved_top_k_before=args.top_k_before,
        improved_top_k_after=args.top_k_after,
        similarity_threshold=args.similarity_threshold,
        rewrite_mode=args.rewrite_mode,
        rerank_mode=args.rerank_mode,
        rebuild_index=args.rebuild_index,
    )
    aggregate = payload["aggregate"]
    print(
        f"Готово: {len(payload['questions'])} вопросов; "
        f"source hits {aggregate['plain_expected_source_hits']} -> "
        f"{aggregate['improved_expected_source_hits']}; "
        f"отчёт {args.output_dir / 'day23-comparison.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
