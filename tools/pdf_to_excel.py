#!/usr/bin/env python3
"""Extract multiple-choice questions from PDFs into an app-importable XLSX file."""

from __future__ import annotations

import argparse
import html
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pdfplumber


HEADERS = [
    "题库",
    "题型",
    "题干",
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "答案",
    "解析",
    "标签",
    "来源文件",
    "页码",
]


ANSWER_RE = re.compile(r"^(?:参考答案|答案|正确答案)\s*[:：]?\s*([A-Ha-h]+)\b")
QUESTION_START_RE = re.compile(r"(?m)^\s*(\d{1,3})[\.、．]\s*")
OPTION_RE = re.compile(r"^\s*([A-Ha-h])(?:[\.\、．]\s*|\s+)(.+)$")
NOISE_RE = re.compile(r"版权所有|面试笔试辅导热线|Charis_3385|友情提醒")
STOP_MARKER_RE = re.compile(r"历年题库重复考点分析|参考答案")
SECTION_RE = re.compile(r"(单选题|多选题)")


def clean_line(line: str) -> str:
    line = html.unescape(line)
    line = line.replace("\u2010", "-").replace("\u2011", "-")
    line = re.sub(r"\s+", " ", line).strip()
    return line


def extract_pages(pdf_path: Path) -> list[tuple[int, str]]:
    pages: list[tuple[int, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1.5, y_tolerance=3) or ""
            stop_match = STOP_MARKER_RE.search(text)
            if stop_match:
                text = text[: stop_match.start()]
            lines = [clean_line(line) for line in text.splitlines()]
            lines = [line for line in lines if line and not NOISE_RE.search(line)]
            page_text = "\n".join(lines)
            if page_text:
                pages.append((index, page_text))
            if stop_match:
                break
    return pages


def split_question_blocks(pages: list[tuple[int, str]]) -> list[tuple[int, str, str]]:
    joined_parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for page_no, text in pages:
        offsets.append((cursor, page_no))
        joined_parts.append(text)
        cursor += len(text) + 1
    joined = "\n".join(joined_parts)
    matches = list(QUESTION_START_RE.finditer(joined))
    blocks: list[tuple[int, str, str]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(joined)
        page_no = 1
        for offset, candidate_page in offsets:
            if offset <= start:
                page_no = candidate_page
            else:
                break
        section_text = joined[:start]
        section = ""
        for section_match in SECTION_RE.finditer(section_text):
            section = section_match.group(1)
        blocks.append((page_no, section, joined[start:end].strip()))
    return blocks


def parse_block(block: str, bank: str, source: str, page_no: int, section: str = "") -> dict[str, str] | None:
    lines = [clean_line(line) for line in block.splitlines() if clean_line(line)]
    if not lines:
        return None

    answer = ""
    explanation_lines: list[str] = []
    body_lines: list[str] = []
    in_explanation = False

    for line in lines:
        answer_match = ANSWER_RE.match(line)
        if answer_match:
            answer = normalize_answer(answer_match.group(1))
            in_explanation = False
            continue
        if re.match(r"^解析\s*[:：]?", line):
            explanation_lines.append(re.sub(r"^解析\s*[:：]?\s*", "", line).strip())
            in_explanation = True
            continue
        if in_explanation:
            explanation_lines.append(line)
        else:
            body_lines.append(line)

    stem_parts: list[str] = []
    options: dict[str, str] = {}
    current_key = ""
    for line in body_lines:
        option_match = OPTION_RE.match(line)
        if option_match:
            current_key = option_match.group(1).upper()
            options[current_key] = option_match.group(2).strip()
        elif current_key:
            options[current_key] = f"{options[current_key]} {line}".strip()
        else:
            stem_parts.append(line)

    stem = "\n".join(stem_parts)
    stem = re.sub(r"^\s*\d{1,3}[\.、．]\s*", "", stem).strip()
    if not stem:
        return None

    if len(options) < 2:
        qtype = "text"
    elif "多选" in section:
        qtype = "multiple"
    elif "单选" in section:
        qtype = "single"
    else:
        qtype = "multiple" if len(answer) > 1 else "single"
    row = {
        "题库": bank,
        "题型": qtype,
        "题干": stem,
        "答案": answer,
        "解析": " ".join(explanation_lines).strip(),
        "标签": "",
        "来源文件": source,
        "页码": str(page_no),
    }
    for key in "ABCDEFGH":
        row[key] = options.get(key, "")
    return row


def normalize_answer(answer: str) -> str:
    return "".join(sorted(set(re.findall(r"[A-H]", answer.upper()))))


def extract_questions(pdf_paths: list[Path], bank: str) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for pdf_path in pdf_paths:
        pages = extract_pages(pdf_path)
        for page_no, section, block in split_question_blocks(pages):
            parsed = parse_block(block, bank, pdf_path.name, page_no, section)
            if parsed:
                questions.append(parsed)
    return questions


def cell_ref(row: int, col: int) -> str:
    letters = ""
    while col:
        col, rem = divmod(col - 1, 26)
        letters = chr(65 + rem) + letters
    return f"{letters}{row}"


def inline_cell(row: int, col: int, value: str) -> str:
    ref = cell_ref(row, col)
    value = escape(str(value or ""))
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{value}</t></is></c>'


def write_xlsx(rows: list[dict[str, str]], output: Path) -> None:
    data = [HEADERS] + [[row.get(header, "") for header in HEADERS] for row in rows]
    sheet_rows = []
    for row_index, row in enumerate(data, start=1):
        cells = "".join(inline_cell(row_index, col_index, value) for col_index, value in enumerate(row, start=1))
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')
    worksheet = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <cols>
    <col min="1" max="2" width="14" customWidth="1"/>
    <col min="3" max="3" width="54" customWidth="1"/>
    <col min="4" max="11" width="26" customWidth="1"/>
    <col min="12" max="14" width="14" customWidth="1"/>
    <col min="15" max="16" width="20" customWidth="1"/>
  </cols>
  <sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>'''

    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="题库" sheetId="1" r:id="rId1"/></sheets>
</workbook>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Codex</Application></Properties>'''
    core = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>题库</dc:title></cp:coreProperties>'''

    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("docProps/app.xml", app)
        zf.writestr("docProps/core.xml", core)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", worksheet)


def resolve_inputs(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            paths.extend(sorted(path.glob("*.pdf")))
        elif path.is_file() and path.suffix.lower() == ".pdf":
            paths.append(path)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract PDF questions to XLSX.")
    parser.add_argument("inputs", nargs="+", help="PDF files or folders containing PDFs")
    parser.add_argument("-o", "--output", default="题库导入.xlsx", help="Output .xlsx path")
    parser.add_argument("-b", "--bank", default="笔试题库", help="Question bank name")
    args = parser.parse_args()

    pdf_paths = resolve_inputs(args.inputs)
    if not pdf_paths:
        print("No PDF files found.", file=sys.stderr)
        return 1

    questions = extract_questions(pdf_paths, args.bank)
    write_xlsx(questions, Path(args.output))
    print(f"PDF files: {len(pdf_paths)}")
    print(f"Questions: {len(questions)}")
    print(f"Output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
