"""Build the FAISS index over the financial knowledge base.

Usage:  python scripts/build_index.py

Costs one embedding request per batch of chunks, not per query, so it is cheap
and rarely run. Re-run it after editing anything in data/financial_knowledge/.
"""

import sys

import _bootstrap  # noqa: F401  # must precede any app import

from app.rag.ingestion import IngestionError, build_index


def main() -> int:
    try:
        count = build_index()
    except IngestionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"\nindexed {count} chunks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
