"""Parse and write question files (txt / xlsx)."""

from __future__ import annotations

import json
import re
from io import BytesIO
from typing import Any

from openpyxl import Workbook, load_workbook

VALID_TYPES = {"open", "single", "multiple"}

TYPE_ALIASES = {
    "open": "open",
    "открытый": "open",
    "открытый вопрос": "open",
    "text": "open",
    "имя": "open",
    "single": "single",
    "один": "single",
    "один ответ": "single",
    "чекбокс": "single",
    "checkbox": "single",
    "radio": "single",
    "multiple": "multiple",
    "несколько": "multiple",
    "несколько ответов": "multiple",
    "multi": "multiple",
}

YES_VALUES = {"1", "yes", "y", "true", "да", "истина", "оценивается"}


def _norm(value: Any) -> str:
    return str(value or "").strip()


def _split_list(value: Any) -> list[str]:
    text = _norm(value)
    if not text:
        return []
    parts = re.split(r"\s*\|\s*", text)
    return [p.strip() for p in parts if p.strip()]


def _type(value: Any) -> str:
    key = _norm(value).lower()
    if key not in TYPE_ALIASES:
        raise ValueError(f"Неизвестный тип вопроса: {value!r}")
    return TYPE_ALIASES[key]


def _scored(value: Any, qtype: str) -> bool:
    text = _norm(value).lower()
    if not text:
        return qtype != "open"
    return text in YES_VALUES


def normalize_question(raw: dict[str, Any], index: int) -> dict[str, Any]:
    qtype = _type(raw.get("type"))
    prompt = _norm(raw.get("question"))
    if not prompt:
        raise ValueError(f"Вопрос #{index} без текста")
    options = _split_list(raw.get("options"))
    correct = _split_list(raw.get("correct"))
    scored = _scored(raw.get("scored"), qtype)

    if qtype in {"single", "multiple"} and len(options) < 2:
        raise ValueError(f"У вопроса «{prompt}» должно быть минимум 2 варианта")
    if qtype == "open":
        options = []
    if qtype == "single" and scored and len(correct) != 1:
        raise ValueError(f"У вопроса «{prompt}» (один ответ) должен быть ровно 1 правильный вариант")
    if qtype == "multiple" and scored and not correct:
        raise ValueError(f"У вопроса «{prompt}» не отмечены правильные ответы")
    if qtype != "open":
        unknown = [c for c in correct if c not in options]
        if unknown:
            raise ValueError(f"Правильные ответы не найдены в вариантах вопроса «{prompt}»: {unknown}")

    return {
        "sort_order": index,
        "qtype": qtype,
        "prompt": prompt,
        "options": options,
        "correct": correct,
        "scored": scored,
    }


def parse_txt(content: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", content.replace("\r\n", "\n").strip())
    questions: list[dict[str, Any]] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip() and not ln.strip().startswith("#")]
        if not lines:
            continue
        raw: dict[str, str] = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().upper()
            mapping = {"TYPE": "type", "Q": "question", "QUESTION": "question", "OPTIONS": "options", "CORRECT": "correct", "SCORED": "scored"}
            if key in mapping:
                raw[mapping[key]] = value.strip()
        if not raw:
            continue
        questions.append(normalize_question(raw, len(questions) + 1))
    if not questions:
        raise ValueError("В txt-файле не найдено ни одного вопроса")
    return questions


HEADER_MAP = {
    "type": "type",
    "тип": "type",
    "question": "question",
    "вопрос": "question",
    "options": "options",
    "варианты": "options",
    "варианты ответов": "options",
    "correct": "correct",
    "правильные": "correct",
    "правильный ответ": "correct",
    "scored": "scored",
    "оценивается": "scored",
}


def parse_xlsx(data: bytes) -> list[dict[str, Any]]:
    wb = load_workbook(BytesIO(data), data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel-файл пустой")
    headers = [_norm(h).lower() for h in rows[0]]
    mapped = [HEADER_MAP.get(h) for h in headers]
    if "type" not in mapped or "question" not in mapped:
        raise ValueError("В Excel нужны колонки type/тип и question/вопрос")
    questions: list[dict[str, Any]] = []
    for row in rows[1:]:
        if not row or all(v is None or str(v).strip() == "" for v in row):
            continue
        raw: dict[str, Any] = {}
        for key, value in zip(mapped, row):
            if key:
                raw[key] = value
        questions.append(normalize_question(raw, len(questions) + 1))
    if not questions:
        raise ValueError("В Excel не найдено ни одного вопроса")
    return questions


def parse_upload(filename: str, data: bytes) -> list[dict[str, Any]]:
    name = filename.lower()
    if name.endswith(".txt"):
        return parse_txt(data.decode("utf-8-sig"))
    if name.endswith(".xlsx"):
        return parse_xlsx(data)
    raise ValueError("Поддерживаются только файлы .txt и .xlsx")


def questions_to_xlsx(questions: list[dict[str, Any]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "questions"
    ws.append(["type", "question", "options", "correct", "scored"])
    for q in questions:
        options = q["options"] if isinstance(q["options"], list) else json.loads(q["options"] or "[]")
        correct = q["correct"] if isinstance(q["correct"], list) else json.loads(q["correct"] or "[]")
        ws.append(
            [
                q["qtype"],
                q["prompt"],
                " | ".join(options),
                " | ".join(correct),
                "yes" if q["scored"] else "no",
            ]
        )
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
