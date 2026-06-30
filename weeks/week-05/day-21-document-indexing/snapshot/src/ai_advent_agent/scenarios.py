"""Snapshot-local CLI scenario Day 21."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from ai_advent_agent.rag.compare import DEFAULT_SAMPLE_QUERIES, run_indexing_pipeline
from ai_advent_agent.rag.embeddings import HashEmbeddingBackend, OllamaEmbeddingBackend


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-advent-scenarios")
    subparsers = parser.add_subparsers(dest="scenario", required=True)
    demo = subparsers.add_parser("document-indexing-demo")
    demo.add_argument("--corpus-dir", required=True)
    demo.add_argument("--output-dir", required=True)
    demo.add_argument("--embedding-backend", choices=("ollama", "hash"), default="ollama")
    demo.add_argument("--embedding-model", default="nomic-embed-text")
    demo.add_argument("--ollama-base-url", default="http://localhost:11434")
    demo.add_argument("--fixed-chunk-size", type=int, default=1600)
    demo.add_argument("--fixed-overlap", type=int, default=200)
    demo.add_argument("--structure-max-chunk-size", type=int, default=2400)
    demo.add_argument("--structure-overlap", type=int, default=200)
    demo.add_argument("--top-k", type=int, default=3)
    demo.add_argument("--sample-query", action="append")
    demo.add_argument("--hash-dim", type=int, default=128)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.embedding_backend == "ollama":
        backend = OllamaEmbeddingBackend(
            model=args.embedding_model,
            base_url=args.ollama_base_url,
        )
    else:
        backend = HashEmbeddingBackend(args.hash_dim)
    queries = tuple(args.sample_query) if args.sample_query else DEFAULT_SAMPLE_QUERIES
    try:
        summary = run_indexing_pipeline(
            args.corpus_dir,
            args.output_dir,
            backend,
            fixed_chunk_size=args.fixed_chunk_size,
            fixed_overlap=args.fixed_overlap,
            structure_max_chunk_size=args.structure_max_chunk_size,
            structure_overlap=args.structure_overlap,
            top_k=args.top_k,
            sample_queries=queries,
        )
    except (RuntimeError, ValueError) as error:
        print(f"Document indexing failed: {error}")
        return 1
    print(
        "Document indexing completed: "
        f"{summary['corpus']['document_count']} documents, "
        f"{summary['indexes']['fixed']['chunk_count']} fixed chunks, "
        f"{summary['indexes']['structure']['chunk_count']} structure chunks."
    )
    print(f"Artifacts: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
