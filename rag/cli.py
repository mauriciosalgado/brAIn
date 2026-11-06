import argparse
import logging
import sys

from rag import config
from rag.index import embeddings, indexer, search


def _sync(_args) -> int:
    stats = indexer.sync()
    print(f"{stats.indexed} indexed ({stats.chunks} chunks), {stats.removed} removed")
    for source, reason in stats.failed.items():
        print(f"skipped {source}: {reason}", file=sys.stderr)
    return 1 if stats.failed else 0


def _query(args) -> int:
    for hit in search.query(" ".join(args.question)):
        print(f"Source:  {hit['source']}")
        print(f"Section: {hit['header_path']}")
        print(f"Score:   {hit['score']:.2f}")
        print(f"\n{hit['text']}\n{'-' * 40}\n")
    return 0


def _status(_args) -> int:
    status = indexer.status()
    indexed = (status.indexed_commit or "nothing")[:7]
    print(f"{status.notes} notes indexed ({status.chunks} chunks), {status.pending} to update")
    print(f"index at {indexed}, {config.BRANCH} at {status.branch_tip[:7]}")
    return 1 if status.pending or status.indexed_commit is None else 0


def _model(_args) -> int:
    embeddings.ensure_model()
    print("The embedding model is ready")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rag", description="Search your notes.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser("sync", help="index what changed on the searched branch").set_defaults(
        run=_sync
    )
    query = commands.add_parser("query", help="show the passages that best match a question")
    query.add_argument("question", nargs="+")
    query.set_defaults(run=_query)
    commands.add_parser("status", help="say whether the index is up to date").set_defaults(
        run=_status
    )
    commands.add_parser("model", help="download the search model, or repair it").set_defaults(
        run=_model
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = _parser().parse_args()
    try:
        code = args.run(args)
    except (ValueError, RuntimeError) as error:  # a clear message, not a traceback
        print(f"rag: {error}", file=sys.stderr)
        code = 1
    sys.exit(code)
