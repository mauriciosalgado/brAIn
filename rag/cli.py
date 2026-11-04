import sys
import rag


def main():
    if len(sys.argv) < 2:
        print("Usage: rag <command> [args]")
        print("Commands: sync, query, clean")
        sys.exit(1)
    command = sys.argv[1]
    if command == "sync":
        rag.sync()
    elif command == "query":
        if len(sys.argv) < 3:
            print("Usage: rag query 'your question'")
            sys.exit(1)
        question = " ".join(sys.argv[2:])
        for hit in rag.query(question):
            print(f"Source:  {hit['source']}")
            print(f"Section: {hit['header_path']}")
            print(f"\n{hit['text']}\n{'-' * 40}\n")
    elif command == "clean":
        rag.cleanup()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
