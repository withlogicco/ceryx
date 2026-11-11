#!/usr/bin/env python3
"""Render pytest JUnit XML reports as a GitHub Actions job summary table."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

STATUS_ICONS = {
    "passed": "✅",
    "failed": "❌",
    "error": "💥",
    "skipped": "⏭️",
    "missing": "—",
}
STATUS_PRIORITY = {
    "missing": 0,
    "passed": 1,
    "skipped": 2,
    "failed": 3,
    "error": 4,
}
BACKENDS = ("sqlite", "redis", "redis-password")
BACKEND_LABELS = {
    "redis": "Redis",
    "redis-password": "Redis with password",
    "sqlite": "SQLite",
}


@dataclass(frozen=True)
class TestCaseResult:
    file: str
    name: str
    classname: str
    status: str
    time: float
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reports-dir", default="test-results")
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--sha", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument(
        "--server-url",
        default=os.environ.get("GITHUB_SERVER_URL", "https://github.com"),
    )
    parser.add_argument(
        "--workspace", default=os.environ.get("GITHUB_WORKSPACE", os.getcwd())
    )
    return parser.parse_args()


def normalize_file_path(raw_file: str, classname: str) -> str:
    if raw_file:
        path = raw_file
    else:
        parts = classname.split(".")
        if len(parts) > 1 and parts[-1].startswith("Test"):
            parts = parts[:-1]
        path = "/".join(parts) + ".py"

    path = path.replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    if "/tests/" in path:
        path = "tests/" + path.split("/tests/", 1)[1]
    return path


def normalize_test_name(name: str, classname: str) -> str:
    class_name = classname.rsplit(".", 1)[-1]
    if class_name.startswith("test_"):
        return name

    for backend, suffix in BACKEND_LABELS.items():
        if class_name.endswith(suffix):
            return class_name[: -len(suffix)] + "." + name
    return class_name + "." + name if class_name else name


def result_status(case: ET.Element) -> tuple[str, str]:
    failure = case.find("failure")
    if failure is not None:
        return "failed", failure.get("message") or (failure.text or "").strip()

    error = case.find("error")
    if error is not None:
        return "error", error.get("message") or (error.text or "").strip()

    skipped = case.find("skipped")
    if skipped is not None:
        return "skipped", skipped.get("message") or (skipped.text or "").strip()

    return "passed", ""


def parse_report(report: Path) -> list[TestCaseResult]:
    root = ET.parse(report).getroot()
    cases = root.findall(".//testcase")
    results: list[TestCaseResult] = []

    for case in cases:
        classname = case.get("classname", "")
        name = case.get("name", "")
        status, message = result_status(case)
        file_path = normalize_file_path(case.get("file", ""), classname)
        results.append(
            TestCaseResult(
                file=file_path,
                name=normalize_test_name(name, classname),
                classname=classname,
                status=status,
                time=float(case.get("time") or 0),
                message=message,
            )
        )

    return results


def read_reports(
    reports_dir: Path,
) -> dict[str, dict[tuple[str, str], TestCaseResult]]:
    matrix: dict[str, dict[tuple[str, str], TestCaseResult]] = defaultdict(
        dict
    )
    report_re = re.compile(r"^(?P<backend>sqlite|redis|redis-password)\.xml$")

    for report in sorted(reports_dir.glob("*.xml")):
        match = report_re.match(report.name)
        if not match:
            continue

        backend = match.group("backend")
        for case in parse_report(report):
            key = (case.file, case.name)
            existing = matrix[backend].get(key)
            if (
                existing is None
                or STATUS_PRIORITY[case.status] >= STATUS_PRIORITY[existing.status]
            ):
                matrix[backend][key] = case

    return dict(matrix)


def totals_for(results: dict[tuple[str, str], TestCaseResult]) -> dict[str, int]:
    totals = {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "missing": 0}
    for result in results.values():
        totals[result.status] += 1
    return totals


def status_cell(result: TestCaseResult | None) -> str:
    if result is None:
        return STATUS_ICONS["missing"]

    icon = STATUS_ICONS[result.status]
    seconds = f"{result.time:.2f}s"
    label = result.status
    if result.message and result.status in {"failed", "error", "skipped"}:
        message = html.escape(" ".join(result.message.split()))
        return f"{icon}<br><sub>{seconds}</sub><br><sub>{label}: {message}</sub>"
    return f"{icon}<br><sub>{seconds}</sub>"


def test_line(workspace: Path, file_path: str, test_name: str) -> int | None:
    path = workspace / file_path
    if not path.exists():
        return None

    function_name = test_name.rsplit(".", 1)[-1]
    pattern = re.compile(rf"^\s*def\s+{re.escape(function_name)}\s*\(")
    try:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if pattern.search(line):
                return line_number
    except UnicodeDecodeError:
        return None

    return None


def test_permalink(
    repo: str,
    sha: str,
    server_url: str,
    workspace: Path,
    file_path: str,
    test_name: str,
) -> str:
    label = f"{file_path}::{test_name}"
    escaped_label = html.escape(label)
    if not repo or not sha:
        return f"`{escaped_label}`"

    line_number = test_line(workspace, file_path, test_name)
    anchor = f"#L{line_number}" if line_number else ""
    return f"[`{escaped_label}`]({server_url}/{repo}/blob/{sha}/{file_path}{anchor})"


def markdown_table(
    matrix: dict[str, dict[tuple[str, str], TestCaseResult]],
    repo: str,
    sha: str,
    server_url: str,
    workspace: Path,
) -> str:
    all_tests = sorted(
        {
            key
            for backend_results in matrix.values()
            for key in backend_results.keys()
        }
    )

    lines = [
        "## Test suite matrix",
        "",
        "Each cell shows the result and runtime for one storage backend.",
        "Test links point at the checked-out commit for this workflow run.",
        "",
        "| Test | " + " | ".join(BACKEND_LABELS[b] for b in BACKENDS) + " |",
        "|---" + "|---" * len(BACKENDS) + "|",
    ]

    for file_path, test_name in all_tests:
        row = [test_permalink(repo, sha, server_url, workspace, file_path, test_name)]
        for backend in BACKENDS:
            row.append(status_cell(matrix.get(backend, {}).get((file_path, test_name))))
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def markdown_overview(
    matrix: dict[str, dict[tuple[str, str], TestCaseResult]],
) -> str:
    lines = [
        "# Ceryx CI test results",
        "",
        "| Backend | Passed | Failed | Errors | Skipped | Total |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for backend in BACKENDS:
        results = matrix.get(backend, {})
        totals = totals_for(results)
        total = sum(totals.values()) - totals["missing"]
        lines.append(
            "| "
            + " | ".join(
                [
                    BACKEND_LABELS[backend],
                    str(totals["passed"]),
                    str(totals["failed"]),
                    str(totals["error"]),
                    str(totals["skipped"]),
                    str(total),
                ]
            )
            + " |"
        )

    return "\n".join(lines)


def write_summary(summary_file: str | None, content: str) -> None:
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as summary:
            summary.write(content)
            summary.write("\n")
    else:
        print(content)


def main() -> int:
    args = parse_args()
    reports_dir = Path(args.reports_dir)
    if not reports_dir.exists():
        write_summary(
            args.summary_file,
            "# Ceryx CI test results\n\nNo pytest JUnit XML reports were found.",
        )
        return 0

    matrix = read_reports(reports_dir)
    if not matrix:
        write_summary(
            args.summary_file,
            "# Ceryx CI test results\n\nNo pytest JUnit XML reports were found.",
        )
        return 0

    content = "\n\n".join(
        [
            markdown_overview(matrix),
            markdown_table(
                matrix,
                args.repo,
                args.sha,
                args.server_url,
                Path(args.workspace),
            ),
        ]
    )
    write_summary(args.summary_file, content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
