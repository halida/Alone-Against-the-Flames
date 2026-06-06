#!/usr/bin/env python3
"""Convert book.md into structured JSON for a web game."""

from __future__ import annotations

import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
BOOK_PATH = BASE_DIR / "book.md"
SCRIPT_OUTPUT_PATH = BASE_DIR / "book.js"

SECTION_RE = re.compile(r"^##\s+(\d+)\s*$", re.MULTILINE)
TARGET_RE = re.compile(r"(?:前\s*往|到|去|进入)\s*(?:\*\*)?\^?\(?\s*(\d{1,3})\s*\)?(?:\*\*)?")
ANY_TARGET_RE = re.compile(r"(?:\*\*)?\^?\(?\s*(\d{1,3})\s*\)?(?:\*\*)?")

ARTIFACT_PATTERNS = [
    re.compile(r"^```\s*$"),
    re.compile(r"^#\s*七宫涟个人汉化\s*$"),
    re.compile(r"^#####\s*(?:ALONE AGAINST THE FLAMES|向火独行)\s*$"),
    re.compile(r"^#####\s*[IVXLCDM]+\s*$"),
]


def is_artifact(line: str) -> bool:
    stripped = line.strip()
    return any(pattern.match(stripped) for pattern in ARTIFACT_PATTERNS)


def normalize_markup(text: str) -> str:
    text = text.replace("　", "")
    text = re.sub(r"\*\*(\d{1,3})\*\*", r"\1", text)
    text = re.sub(r"\^(\d{1,3})", r"\1", text)
    text = re.sub(r"\(\s*(\d{1,3})\s*\)", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = re.sub(r"\s+([，。！？；：、）])", r"\1", text)
    text = re.sub(r"([（])\s+", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_lines(raw: str) -> list[str]:
    lines = []
    for line in raw.splitlines():
        if is_artifact(line):
            continue
        lines.append(line.rstrip())
    return lines


def lines_to_paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(normalize_markup("".join(current)))
                current = []
            continue
        current.append(stripped)

    if current:
        paragraphs.append(normalize_markup("".join(current)))

    return [paragraph for paragraph in paragraphs if paragraph]


def sentence_like_chunks(paragraph: str) -> list[str]:
    chunks = re.split(r"(?<=[。！？；])", paragraph)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def choice_label(text: str, target: int) -> str:
    text = normalize_markup(text)
    text = re.sub(r"[：:，,；;。]?\s*(?:现在)?(?:请)?(?:前\s*往|到|去|进入)\s*" + str(target) + r"\s*[。.]?$", "", text)
    text = re.sub(r"[：:，,；;。]?\s*(?:现在)?(?:请)?(?:前\s*往|到|去|进入)\s*\(?\s*" + str(target) + r"\s*\)?\s*[。.]?$", "", text)
    text = re.sub(r"^(?:现在|否则)?你可以[:：]", "", text)
    text = text.strip(" ：:，,；;。-—")
    return text or "继续"


def extract_choices(paragraphs: list[str]) -> tuple[list[dict], list[str], list[dict]]:
    choices: list[dict] = []
    body: list[str] = []
    links: list[dict] = []

    for paragraph in paragraphs:
        targets = [int(match.group(1)) for match in TARGET_RE.finditer(paragraph)]
        if not targets:
            body.append(paragraph)
            continue

        unique_targets = []
        for target in targets:
            if target not in unique_targets:
                unique_targets.append(target)
            links.append({"target": target, "text": f"前往 {target}", "source": paragraph})

        # Direct transition paragraph, usually displayed as a continue button.
        if len(unique_targets) == 1 and re.fullmatch(r"(?:现在)?(?:请)?前往\s*\d{1,3}\s*[。.]?", paragraph):
            choices.append({"label": "继续", "target": unique_targets[0], "kind": "goto", "source": paragraph})
            continue

        chunks = sentence_like_chunks(paragraph)
        choice_count_before = len(choices)
        non_choice_chunks: list[str] = []

        for chunk in chunks:
            chunk_targets = [int(match.group(1)) for match in TARGET_RE.finditer(chunk)]
            if not chunk_targets:
                non_choice_chunks.append(chunk)
                continue
            for target in chunk_targets:
                choices.append({
                    "label": choice_label(chunk, target),
                    "target": target,
                    "kind": "choice" if len(unique_targets) > 1 else "goto",
                    "source": chunk,
                })

        if non_choice_chunks:
            body.append("".join(non_choice_chunks))
        elif len(choices) == choice_count_before:
            body.append(paragraph)

    return choices, body, links


def parse_preface(text: str, first_section_start: int) -> dict:
    preface_raw = text[:first_section_start]
    preface_lines = clean_lines(preface_raw)
    paragraphs = lines_to_paragraphs(preface_lines)
    choices, body, links = extract_choices(paragraphs)
    return {
        "body": body,
        "choices": choices,
        "links": links,
    }


def parse_sections(text: str) -> dict[str, dict]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, dict] = {}

    for index, match in enumerate(matches):
        section_id = int(match.group(1))
        if not 1 <= section_id <= 270:
            continue

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        if section_id == 270:
            appendix = re.search(r"^####\s+附录", text[start:end], re.MULTILINE)
            if appendix:
                end = start + appendix.start()

        raw = text[start:end]
        paragraphs = lines_to_paragraphs(clean_lines(raw))
        choices, body, links = extract_choices(paragraphs)
        is_ending = any("剧终" in paragraph for paragraph in paragraphs) or not choices

        sections[str(section_id)] = {
            "id": section_id,
            "body": body,
            "choices": choices,
            "links": links,
            "ending": is_ending,
            "text": "\n\n".join(paragraphs),
        }

    return dict(sorted(sections.items(), key=lambda item: int(item[0])))


def validate_sections(sections: dict[str, dict]) -> dict:
    ids = {int(section_id) for section_id in sections}
    referenced = sorted({choice["target"] for section in sections.values() for choice in section["choices"]})
    missing = [target for target in referenced if target not in ids]
    no_choices = sorted(int(section_id) for section_id, section in sections.items() if not section["choices"])
    endings = sorted(int(section_id) for section_id, section in sections.items() if section["ending"])
    return {
        "sectionCount": len(sections),
        "firstSection": min(ids),
        "lastSection": max(ids),
        "referencedSectionCount": len(referenced),
        "missingReferencedSections": missing,
        "sectionsWithoutChoices": no_choices,
        "endingSections": endings,
    }


def main() -> None:
    text = BOOK_PATH.read_text(encoding="utf-8")
    first_section = SECTION_RE.search(text)
    if not first_section:
        raise SystemExit("No numbered sections found")

    sections = parse_sections(text)
    data = {
        "title": "向火独行",
        "originalTitle": "Alone Against the Flames",
        "language": "zh-Hans",
        "startSection": 1,
        "source": {
            "markdown": "book.md",
            "note": "由 book.md 清理并转换；仅保留 1-270 的游戏正文，附录未写入 sections。",
        },
        "schema": {
            "section.body": "去掉页眉、页码、代码围栏和跳转语句后的段落，适合直接显示。",
            "section.choices": "从“前往 N”等跳转语句提取的网页按钮数据。",
            "section.text": "清理后的完整段落文本，保留原跳转语句，便于校对。",
        },
        "intro": parse_preface(text, first_section.start()),
        "sections": sections,
    }
    data["validation"] = validate_sections(sections)

    script_text = "window.BOOK_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n"

    SCRIPT_OUTPUT_PATH.write_text(script_text, encoding="utf-8")
    print(f"wrote {SCRIPT_OUTPUT_PATH}")
    print(json.dumps(data["validation"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
