"""Convert numbered regression-test HTML/JSON pairs into product Markdown files."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field, replace
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable


SECTION_NAMES = {
    "setup": "Setup",
    "setup steps": "Setup",
    "action": "Action",
    "action steps": "Action",
    "cleanup": "Cleanup",
    "cleanup steps": "Cleanup",
}


class FragmentTextParser(HTMLParser):
    """Extract readable text from exported HTML fragments."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"p", "div", "li", "tr"}:
            self.parts.append("\n")


def html_to_text(source: str) -> str:
    parser = FragmentTextParser()
    parser.feed(source)
    parser.close()
    return html.unescape("".join(parser.parts))


def clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.replace("\xa0", " ").strip()
        if line:
            lines.append(line)
    return lines


def parse_steps(source: str) -> dict[str, list[str]]:
    """Split HTML text into known sections while preserving source order."""
    sections: dict[str, list[str]] = {"setup": [], "action": [], "cleanup": [], "unclassified": []}
    current = "unclassified"
    heading_pattern = re.compile(r"^\s*(setup(?:\s+steps)?|action(?:\s+steps)?|cleanup(?:\s+steps)?)\s*:?\s*$", re.IGNORECASE)

    for line in clean_lines(html_to_text(source)):
        heading = heading_pattern.match(line)
        if heading:
            current = SECTION_NAMES[heading.group(1).lower()]
            current = current.lower()
            continue
        sections[current].append(line)
    return sections


def attribute_values(metadata: dict, name: str) -> list[str]:
    attributes = metadata.get("attributes", {})
    values = attributes.get(name, []) if isinstance(attributes, dict) else []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value).strip()]
    return [str(values).strip()] if str(values).strip() else []


def slugify_name(name: str) -> str:
    normalized = name.upper().replace("&", " AND ")
    normalized = re.sub(r"[^A-Z0-9._-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_.-")
    return normalized or "UNNAMED_TEST"


def markdown_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


@dataclass
class TestRecord:
    source_id: str
    name: str
    product: str
    execution_level: str
    execution_mode: str
    status: str
    description: str
    preconditions: str
    steps: dict[str, list[str]]
    html_file: str
    json_file: str
    test_id: str = ""


@dataclass
class ConversionReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pair_count: int = 0
    product_counts: dict[str, int] = field(default_factory=dict)


def discover_pairs(root: Path, report: ConversionReport) -> list[tuple[str, Path, Path]]:
    html_files = {path.stem: path for path in root.glob("*.html") if path.stem.isdigit()}
    json_files = {path.stem: path for path in root.glob("*.JSON") if path.stem.isdigit()}
    all_stems = sorted(set(html_files) | set(json_files), key=lambda value: (not value.isdigit(), value))
    pairs: list[tuple[str, Path, Path]] = []
    for stem in all_stems:
        if stem not in html_files:
            report.errors.append(f"Missing HTML sidecar for {stem}.JSON")
        elif stem not in json_files:
            report.errors.append(f"Missing JSON sidecar for {stem}.html")
        else:
            pairs.append((stem, html_files[stem], json_files[stem]))
    report.pair_count = len(pairs)
    return pairs


def load_record(stem: str, html_path: Path, json_path: Path, allow_multiple_products: bool = False) -> list[TestRecord]:
    with json_path.open("r", encoding="utf-8-sig") as stream:
        metadata = json.load(stream)
    products = attribute_values(metadata, "Product")
    if not products or (len(products) > 1 and not allow_multiple_products):
        raise ValueError(f"{json_path.name}: expected exactly one Product, found {products or 'none'}")

    with html_path.open("r", encoding="utf-8-sig") as stream:
        source_html = stream.read()
    attributes = metadata.get("attributes", {})
    description = html_to_text(str(metadata.get("description", ""))).strip()
    preconditions = html_to_text(str(metadata.get("preconditions", ""))).strip()
    record = TestRecord(
        source_id=str(metadata.get("id", stem)),
        name=markdown_text(str(metadata.get("name", "")).strip() or f"Test {stem}"),
        product=products[0],
        execution_level=", ".join(attribute_values(metadata, "Execution Level")),
        execution_mode=", ".join(attribute_values(metadata, "Execution Mode")),
        status=", ".join(attribute_values(metadata, "status")),
        description=description,
        preconditions=preconditions,
        steps=parse_steps(source_html),
        html_file=html_path.name,
        json_file=json_path.name,
    )
    return [record] + [replace(record, product=product) for product in products[1:]]


def assign_test_ids(records: Iterable[TestRecord]) -> None:
    used: set[str] = set()
    for record in sorted(records, key=lambda item: (item.product.casefold(), item.name.casefold(), item.source_id)):
        base_id = f"TEST_{slugify_name(record.name)}"
        test_id = base_id
        if test_id in used:
            test_id = f"{base_id}_{slugify_name(record.source_id)}"
        counter = 2
        while test_id in used:
            test_id = f"{base_id}_{record.source_id}_{counter}"
            counter += 1
        record.test_id = test_id
        used.add(test_id)


def render_details(summary: str, lines: list[str]) -> str:
    body = "\n".join(lines) if lines else "No steps recorded."
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"


def render_record(record: TestRecord) -> str:
    metadata = [
        f"- Source ID: `{record.source_id}`",
        f"- Product: `{record.product}`",
        f"- Source files: `{record.json_file}`, `{record.html_file}`",
    ]
    blocks = [
        f"**{record.test_id}**",
        record.name,
        "",
        f"Status: `{record.status or 'Not specified'}`",
        "",
        render_details("Metadata", metadata),
    ]
    if record.description:
        blocks.extend(["", "**Description**", "", record.description])
    if record.preconditions:
        blocks.extend(["", "**Preconditions**", "", record.preconditions])
    for section in ("setup", "action", "cleanup"):
        blocks.extend(["", render_details(section.title(), record.steps[section])])
    if record.steps["unclassified"]:
        blocks.extend(["", render_details("Unclassified source content", record.steps["unclassified"])])
    return "\n".join(blocks)


def render_products(records: list[TestRecord]) -> dict[str, str]:
    grouped: dict[str, list[TestRecord]] = defaultdict(list)
    for record in records:
        grouped[record.product].append(record)
    output: dict[str, str] = {}
    for product, product_records in sorted(grouped.items(), key=lambda item: item[0].casefold()):
        product_records.sort(key=lambda item: (item.name.casefold(), item.source_id))
        header = f"# {product} Regression Tests\n\nGenerated from the numbered HTML/JSON regression-test export."
        output[product] = header + "\n\n" + "\n\n---\n\n".join(render_record(record) for record in product_records) + "\n"
    return output


def convert(root: Path, output_dir: Path, dry_run: bool = False, allow_multiple_products: bool = False) -> ConversionReport:
    report = ConversionReport()
    pairs = discover_pairs(root, report)
    records: list[TestRecord] = []
    for stem, html_path, json_path in pairs:
        try:
            records.extend(load_record(stem, html_path, json_path, allow_multiple_products))
        except (OSError, ValueError, json.JSONDecodeError) as error:
            report.errors.append(str(error))

    assign_test_ids(records)
    report.product_counts = dict(sorted(((product, sum(record.product == product for record in records)) for product in {record.product for record in records}), key=lambda item: item[0].casefold()))
    rendered = render_products(records)
    if not dry_run and not report.errors:
        output_dir.mkdir(parents=True, exist_ok=True)
        for product, content in rendered.items():
            (output_dir / f"{product}.md").write_text(content, encoding="utf-8")
        report_path = output_dir / "conversion-report.json"
        report_path.write_text(json.dumps({"pairs": report.pair_count, "products": report.product_counts, "warnings": report.warnings}, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent, help="Directory containing numbered HTML/JSON pairs")
    parser.add_argument("--output", type=Path, default=None, help="Output directory, default: ROOT/markdown")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing Markdown")
    parser.add_argument("--allow-multiple-products", action="store_true", help="Duplicate records with multiple Products into each product file")
    args = parser.parse_args()
    root = args.root.resolve()
    output_dir = (args.output or root / "markdown").resolve()
    report = convert(root, output_dir, args.dry_run, args.allow_multiple_products)
    print(f"Pairs: {report.pair_count}")
    for product, count in report.product_counts.items():
        print(f"{product}: {count}")
    for warning in report.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    for error in report.errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if not report.errors and not args.dry_run:
        print(f"Wrote Markdown to {output_dir}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
