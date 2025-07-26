#!/usr/bin/env python3
import json
import os
import argparse

def get_setlist_path():
    parser = argparse.ArgumentParser(description="Validate setlist paths from a JSON file.")
    parser.add_argument(
        "json_path",
        nargs="?",
        default=os.path.join(os.path.dirname(__file__), "setlist.json"),
        help="Path to setlist JSON file (default: setlist.json in script directory)"
    )
    args = parser.parse_args()
    return args.json_path

def main():
    setlist_file = get_setlist_path()
    with open(setlist_file, "r") as f:
        data = json.load(f)
    sets = data.get("sets", [])
    missing = []
    for s in sets:
        path = s.get("path")
        if path and not os.path.exists(path):
            missing.append(path)
    if missing:
        print("VALIDATION FAILED")
        for path in missing:
            print(f"Missing: {path}")
        # Raise an exception to indicate failure
        raise Exception("Some paths are missing:\n\n" + "\n * ".join(missing))
    else:
        exit(0)

if __name__ == "__main__":
    main()
