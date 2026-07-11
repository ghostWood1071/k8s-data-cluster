from __future__ import annotations

import ast
from pathlib import Path


AIRFLOW_PACKAGE = Path("/home/airflow/.local/lib/python3.11/site-packages/airflow")
KEYWORD = "read_dags_from_db"


def line_offsets(text: str) -> list[int]:
    offsets = [0]
    for index, char in enumerate(text):
        if char == "\n":
            offsets.append(index + 1)
    return offsets


def absolute_index(offsets: list[int], line: int, column: int) -> int:
    return offsets[line - 1] + column


def is_dagbag_call(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "DagBag"


def patch_file(path: Path) -> int:
    original = path.read_text()
    try:
        tree = ast.parse(original, filename=str(path))
    except SyntaxError:
        return 0

    offsets = line_offsets(original)
    insertions: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not is_dagbag_call(node):
            continue
        if any(keyword.arg == KEYWORD for keyword in node.keywords):
            continue

        call_end = absolute_index(offsets, node.end_lineno, node.end_col_offset)
        close_paren = call_end - 1
        if close_paren < 0 or original[close_paren] != ")":
            continue
        prefix = ", " if node.args or node.keywords else ""
        insertions.append((close_paren, f"{prefix}{KEYWORD}=True"))

    if not insertions:
        return 0

    patched = original
    for index, value in sorted(insertions, reverse=True):
        patched = patched[:index] + value + patched[index:]

    path.with_suffix(path.suffix + ".codex-bak").write_text(original)
    path.write_text(patched)
    return len(insertions)


def main() -> None:
    restored = 0
    for backup in AIRFLOW_PACKAGE.rglob("*.py.codex-bak"):
        target = Path(str(backup)[: -len(".codex-bak")])
        target.write_text(backup.read_text())
        restored += 1

    total = 0
    changed_files: list[tuple[str, int]] = []
    for path in AIRFLOW_PACKAGE.rglob("*.py"):
        count = patch_file(path)
        if count:
            total += count
            changed_files.append((str(path), count))

    for path, count in changed_files:
        print(f"{path}: patched {count}")
    print(f"RESTORED_BACKUPS={restored}")
    print(f"TOTAL_PATCHED_CALLS={total}")


if __name__ == "__main__":
    main()
