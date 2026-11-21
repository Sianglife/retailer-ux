#!/usr/bin/env python3
"""Convert local absolute URLs in dist to relative URLs.

Usage:
    python convert_paths.py --dry-run
    python convert_paths.py
    python convert_paths.py path/to/dist
    python convert_paths.py --base-path /another-site/

Place this script in the project root. The default input is dist beside it,
regardless of the current working directory. Both /images/milk.jpg and
/retailer-ux/images/milk.jpg become ./images/milk.jpg in index.html and
JavaScript data. --base-path identifies an existing prefix to strip; it is
never added to output URLs. CSS URLs and module imports are relative to their
containing file. JavaScript data URLs are relative to the root index.html.
External URLs and existing relative URLs are preserved.
Only references to existing local files/directories are converted. No packages
are required. Run after each Astro build.
"""

import argparse
import os
from pathlib import Path
import re
from urllib.parse import unquote


TEXT_EXTENSIONS = {".html", ".htm", ".css", ".js", ".mjs", ".svg", ".json", ".webmanifest"}
QUOTED_URL = re.compile(r'''(?P<quote>["'`])(?P<url>/(?!/)[^"'`\s<>\\]*)(?P=quote)''')
CSS_URL = re.compile(r'''(?P<prefix>\burl\(\s*)(?P<url>/(?!/)[^\s)'"\\]+)(?P<suffix>\s*\))''', re.IGNORECASE)
MODULE_URL = re.compile(
    r'''(?P<prefix>\b(?:from\s*|import\s*(?:\(\s*)?))'''
    r'''(?P<quote>["'])(?P<url>/(?!/)[^"'\s\\]*)(?P=quote)'''
)


def relative_url(url: str, base: Path, root: Path, base_path: str) -> str:
    """Keep URL encoding, query strings, fragments, and trailing slashes intact."""
    path, *suffix = re.split(r"(?=[?#])", url, maxsplit=1)
    if path == base_path.rstrip("/"):
        path = "/"
    elif base_path != "/" and path.startswith(base_path):
        path = "/" + path[len(base_path):]
    decoded = unquote(path)
    # Backslashes can behave as separators in browsers and on Windows.
    if "\\" in decoded or decoded.startswith("//"):
        return url
    target = (root / decoded.lstrip("/")).resolve()
    if not target.is_relative_to(root) or not target.exists():
        return url
    # Use the encoded spelling for output so percent escapes remain intact.
    result = Path(os.path.relpath(root / path.lstrip("/"), base)).as_posix()
    if not result.startswith(("./", "../")):
        result = "./" + result
    if path.endswith("/") and not result.endswith("/"):
        result += "/"
    return result + "".join(suffix)


def convert_text(text: str, file: Path, root: Path, base_path: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match, base: Path) -> str:
        nonlocal count
        original = match.group("url")
        replacement = relative_url(original, base, root, base_path)
        if replacement == original:
            return match.group(0)
        count += 1
        start = match.start("url") - match.start()
        end = match.end("url") - match.start()
        return match.group(0)[:start] + replacement + match.group(0)[end:]

    extension = file.suffix.lower()
    if extension in {".js", ".mjs"}:
        text = MODULE_URL.sub(lambda match: replace(match, file.parent), text)
    if extension in {".css", ".html", ".htm", ".svg"}:
        text = CSS_URL.sub(lambda match: replace(match, file.parent), text)
    base = root if extension in {".js", ".mjs", ".json", ".webmanifest"} else file.parent
    text = QUOTED_URL.sub(lambda match: replace(match, base), text)
    return text, count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", nargs="?", type=Path, default=Path(__file__).resolve().parent / "dist")
    parser.add_argument("--base-path", default="/retailer-ux/", help="Existing URL prefix to strip (default: /retailer-ux/)")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()
    base_path = "/" + args.base_path.strip("/") + "/"
    if (not args.base_path.startswith("/") or args.base_path.startswith("//")
            or any(char.isspace() or char in "?#\\" for char in args.base_path)
            or any(unquote(part) in {".", ".."} for part in args.base_path.split("/"))):
        parser.error("--base-path must be a URL path such as /retailer-ux/")
    if args.base_path == "/":
        base_path = "/"
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"Not a directory: {root}")

    files_changed = total = 0
    for file in sorted(root.rglob("*")):
        if not file.is_file() or file.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if file.is_symlink() or not file.resolve().is_relative_to(root):
            continue
        original = file.read_bytes()
        try:
            text = original.decode("utf-8")
        except UnicodeDecodeError:
            print(f"Skipped non-UTF-8 file: {file.relative_to(root)}")
            continue
        converted, count = convert_text(text, file, root, base_path)
        if count:
            if not args.dry_run:
                file.write_bytes(converted.encode("utf-8"))
            files_changed += 1
            total += count
            print(f"{'Would update' if args.dry_run else 'Updated'} {file.relative_to(root)}: {count} URL(s)")
    print(f"{'Would convert' if args.dry_run else 'Converted'} {total} URL(s) in {files_changed} file(s).")


if __name__ == "__main__":
    main()
