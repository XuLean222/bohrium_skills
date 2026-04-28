#!/usr/bin/env python3
"""
Run batch SN searches from a CSV or JSON file.
"""
import json
import csv
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def load_queries(filepath):
    """Load queries from CSV or JSON file."""
    filepath = Path(filepath)

    if not filepath.exists():
        logging.error(f"File not found: {filepath}")
        sys.exit(1)

    if filepath.suffix == '.json':
        with open(filepath, 'r', encoding='utf-8') as f:
            queries = json.load(f)

        if not isinstance(queries, list):
            logging.error("JSON file must contain a list of query objects")
            sys.exit(1)

        for i, q in enumerate(queries):
            if 'query' not in q:
                logging.error(f"Query object at index {i} missing 'query' field")
                sys.exit(1)

    elif filepath.suffix == '.csv':
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            queries = list(reader)

        if not queries:
            logging.error("CSV file is empty")
            sys.exit(1)

        if 'query' not in queries[0]:
            logging.error("CSV file must have a 'query' column")
            sys.exit(1)
    else:
        logging.error(f"Unsupported file format: {filepath.suffix}. Use .json or .csv")
        sys.exit(1)

    return queries


def run_batch(token, queries_file, output_dir="."):
    """Run batch searches from CSV or JSON file."""
    script_dir = Path(__file__).parent
    sys.path.insert(0, str(script_dir))

    try:
        from run_search import run_single_search
    except ImportError:
        logging.error("Cannot import run_single_search. Make sure run_search.py is in the same directory.")
        sys.exit(1)

    queries = load_queries(queries_file)

    logging.info(f"Loaded {len(queries)} queries from {queries_file}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    results = []
    failed = []

    for i, item in enumerate(queries, 1):
        query = item['query']
        discipline = item.get('discipline', 'All')
        journal_type = item.get('journal_type', 'both')

        logging.info(f"\n[{i}/{len(queries)}] Processing: {query}")

        try:
            result_file = run_single_search(token, query, discipline, journal_type, output_dir)
            results.append(str(result_file))
        except Exception as e:
            logging.error(f"Failed to process query '{query}': {e}")
            failed.append({'query': query, 'error': str(e)})
            continue

    print("\n" + "="*60)
    print(f"Completed {len(results)}/{len(queries)} searches")

    if results:
        print("\nResults saved to:")
        for r in results:
            print(f"  - {r}")

    if failed:
        print(f"\nFailed {len(failed)} searches:")
        for f_item in failed:
            print(f"  - {f_item['query']}: {f_item['error']}")

    print("="*60)


def main():
    if len(sys.argv) < 3:
        print("Usage: python batch_search.py <token> <queries_file> [output_dir]")
        print()
        print("Supported file formats:")
        print("  - JSON: [{'query': '...', 'discipline': '...', 'journal_type': '...'}, ...]")
        print("  - CSV: query,discipline,journal_type")
        print()
        print("discipline:    All (default) | NS | ET | LS | PSS")
        print("journal_type:  both (default) | foreign | chinese | chinese_tech")
        print()
        print("Example:")
        print('  python batch_search.py "your-token" queries.json ./results')
        sys.exit(1)

    token = sys.argv[1]
    queries_file = sys.argv[2]
    output_dir = sys.argv[3] if len(sys.argv) > 3 else "."

    run_batch(token, queries_file, output_dir)


if __name__ == "__main__":
    main()
