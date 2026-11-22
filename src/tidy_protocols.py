"""
One-off repository tidy (November 21, 2026): moves every protocol from the
top level into protocols/, with its history kept (git mv), and rewrites the
links that point to them in the repository's Markdown documents and the
dashboard's footer link to the live tracker protocol.

Nothing in src/ or .github/ opens a protocol file; scripts and results name
protocols only in comments and labels, so no code changes. The protocols'
own text is not edited, because they are pre-registration records; none of
them contains a relative link, so moving them breaks nothing inside them.

Run from the repository root:  python src/tidy_protocols.py
"""
import os
import re
import subprocess
import sys

DEST = "protocols"
EXPECTED = 13

# Prose that says where the protocols are, replaced exactly once each.
PROSE = {
    "README.md": [
        ("Every protocol is at the top level,",
         "Every protocol is in [`protocols/`](protocols/),"),
        ("- **Protocols** (top level):",
         "- **Protocols** ([`protocols/`](protocols/)):"),
    ],
    "reports/Model evolution.md": [
        ("Every protocol named here is at the top level of the repository,",
         "Every protocol named here is in [`protocols/`](<../protocols/>),"),
    ],
    "docs/QUICKSTART.md": [
        ("with the protocol for each at the top level.",
         "with the protocol for each in [`protocols/`](<../protocols/>)."),
    ],
}

LINK = re.compile(r"\]\((<[^>]+>|[^)\s]+)\)")


def git(*args):
    subprocess.run(["git", *args], check=True)


def main():
    names = sorted(f for f in os.listdir(".")
                   if os.path.isfile(f) and f.endswith(".md") and "protocol" in f)
    if len(names) != EXPECTED:
        sys.exit(f"Expected {EXPECTED} protocols at the top level, found {len(names)}: {names}")
    moved = set(names)

    os.makedirs(DEST, exist_ok=True)
    for n in names:
        git("mv", n, os.path.join(DEST, n))
    print(f"Moved {len(names)} protocols into {DEST}/.")

    tracked = subprocess.run(["git", "ls-files", "*.md"], check=True,
                             capture_output=True, text=True).stdout.splitlines()
    changed = {}
    for path in tracked:
        if path.startswith(DEST + "/"):
            continue
        here = os.path.dirname(path)
        text = open(path, encoding="utf-8").read()

        def repoint(m):
            raw = m.group(1)
            target = raw[1:-1] if raw.startswith("<") else raw
            base, _, anchor = target.partition("#")
            if not base or base.startswith(("http:", "https:", "mailto:")):
                return m.group(0)
            resolved = os.path.normpath(os.path.join(here, base))
            if resolved not in moved:
                return m.group(0)
            new = os.path.relpath(os.path.join(DEST, resolved), here or ".").replace(os.sep, "/")
            if anchor:
                new += "#" + anchor
            return "](<" + new + ">)" if (raw.startswith("<") or " " in new) else "](" + new + ")"

        new_text, n_links = LINK.subn(repoint, text)
        n_links = sum(1 for a, b in zip(LINK.findall(text), LINK.findall(new_text)) if a != b)
        for old, new in PROSE.get(path, []):
            if new_text.count(old) != 1:
                sys.exit(f"{path}: expected the passage once: {old!r}")
            new_text = new_text.replace(old, new)
        if new_text != text:
            open(path, "w", encoding="utf-8").write(new_text)
            changed[path] = n_links
    for p, n in sorted(changed.items()):
        print(f"Updated {p}: {n} link(s) repointed")
    # The dashboard's footer links the live tracker protocol by full URL.
    page = "docs/index.html"
    old_url = "blob/main/live%20tracker%20protocol.md"
    new_url = "blob/main/protocols/live%20tracker%20protocol.md"
    text = open(page, encoding="utf-8").read()
    if text.count(old_url) != 1:
        sys.exit(f"{page}: expected the protocol URL once")
    open(page, "w", encoding="utf-8").write(text.replace(old_url, new_url))
    print(f"Updated {page}: protocol URL repointed")
    missing = [p for p in PROSE if p not in changed]
    if missing:
        sys.exit(f"Expected changes not made in: {missing}")


if __name__ == "__main__":
    main()
