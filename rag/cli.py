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
        result = rag.query(question)
        print(result)
    elif command == "clean":
        rag.cleanup()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
