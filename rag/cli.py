import logging
import sys

import rag
from rag import config, embeddings

USAGE = """Usage: rag <command> [args]
Commands:
  sync            index the notes main added or modified, drop the ones it deleted
  query <text>    show the notes most similar to the text
  status          compare the index with git (changes nothing)
  model           download the embedding model, or repair a missing or damaged one"""


def _sync(_args: list[str]) -> int:
    stats = rag.sync()
    print(f"{stats.indexed} indexed ({stats.chunks} chunks), {stats.removed} removed")
    for source, reason in stats.failed.items():
        print(f"skipped {source}: {reason}", file=sys.stderr)
    return 1 if stats.failed else 0


def _query(args: list[str]) -> int:
    if not args:
        return _usage()
    for hit in rag.query(" ".join(args)):
        print(f"Source:  {hit['source']}")
        print(f"Section: {hit['header_path']}")
        print(f"Score:   {hit['score']:.2f}")
        print(f"\n{hit['text']}\n{'-' * 40}\n")
    return 0


def _status(_args: list[str]) -> int:
    status = rag.status()
    indexed = (status.indexed_commit or "nothing")[:7]
    print(f"{status.notes} notes indexed ({status.chunks} chunks), {status.pending} to update")
    print(f"index at {indexed}, {config.BRANCH} at {status.main_commit[:7]}")
    return 1 if status.pending or status.indexed_commit is None else 0


def _model(_args: list[str]) -> int:
    embeddings.ensure_model()
    print("The embedding model is ready")
    return 0


def _usage(_args: list[str] | None = None) -> int:
    print(USAGE)
    return 1


COMMANDS = {"sync": _sync, "query": _query, "status": _status, "model": _model}


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    command, *args = sys.argv[1:] or [""]
    try:
        code = COMMANDS.get(command, _usage)(args)
    except (ValueError, RuntimeError) as error:  # a clear message, not a traceback
        print(f"rag: {error}", file=sys.stderr)
        code = 1
    sys.exit(code)
