"""Terminal commands; defer engine imports so help stays lightweight."""

import argparse
import logging
import sys


def _sync() -> int:
    from rag.index import indexer

    stats = indexer.sync()
    print(f"RAG: {stats.indexed} indexed ({stats.chunks} chunks), {stats.removed} removed")
    return 1 if stats.failed else 0


def _query(question: str) -> int:
    from rag.index import search
    from rag.index.store import open_index

    with open_index() as store:
        commit = store.indexed_commit()
        hits = search.query(question, store)
    print(f"Indexed snapshot: Git commit {commit}")
    if not hits:
        print("No passages meet the configured search score thresholds. Try a different query.")
    for hit in hits:
        print(f"Source:  {hit['source']}")
        print(f"Section: {hit['header_path']}")
        print(f"Score:   {hit['score']:.2f}")
        if hit["context"]:
            print(f"Context: {hit['context']}")
        print(f"\n{hit['text']}\n{'-' * 40}\n")
    return 0


def _status() -> int:
    from rag import config
    from rag.index import indexer

    status = indexer.status()
    indexed = (status.indexed_commit or "nothing")[:7]
    print(f"{status.notes} notes indexed ({status.chunks} chunks), {status.pending} to update")
    print(f"index at {indexed}, {config.REMOTE}/{config.BRANCH} at {status.branch_tip[:7]}")
    return 0 if status.indexed_commit == status.branch_tip else 1


def _reset() -> int:
    from rag.index.store import delete_index

    delete_index()
    print("The index is deleted. Run 'uv run rag sync' to rebuild it")
    return 0


def _model() -> int:
    from rag.index import embeddings

    embeddings.ensure_model()
    print("The embedding model is ready")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag", description="Search your notes.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser("sync", help="index what changed on the searched branch")
    query = commands.add_parser("query", help="show the passages that best match a question")
    query.add_argument("question", nargs="+", help="question, quoted or unquoted")
    commands.add_parser("status", help="say whether the index is up to date")
    commands.add_parser("reset", help="delete the index; the next sync rebuilds it")
    commands.add_parser("model", help="download the search model, or repair it")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = _parser().parse_args()
    commands = {
        "sync": _sync,
        "query": lambda: _query(" ".join(args.question)),
        "status": _status,
        "reset": _reset,
        "model": _model,
    }
    try:
        code = commands[args.command]()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"rag: {error}", file=sys.stderr)
        code = 1
    sys.exit(code)
