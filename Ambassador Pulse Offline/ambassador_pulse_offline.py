#!/usr/bin/env python3
"""
Generate an offline Ambassador Pulse Brief from a local CSV export.

This script does not connect to the portal and does not require internet.
If AI drafting is enabled, it calls only local Ollama at:
http://localhost:11434/api/generate
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT_SECONDS = 420
DEFAULT_INPUT = "cases_last_7_days.csv"
DEFAULT_MODEL = "deepseek-r1:8b"
REPORT_FILE = "ambassador_pulse_report.md"
SUMMARY_FILE = "ambassador_pulse_summary.json"
DOCX_FILE = "ambassador_pulse_report.docx"

THEMES = [
    "Family / Dependent Visa Restrictions",
    "Visit Visa Restrictions",
    "KOC Gate Pass / GP Validity",
    "Differential Treatment by Nationality",
    "Labour / Salary / Employer Dispute",
    "Legal / Detention / Police Matter",
    "Passport / NADRA / Consular Services",
    "Nurses / Health Worker Welfare",
    "Death / Mortal Remains",
    "Domestic Worker / Shelter / Abuse",
    "OPF / Insurance / Compensation",
    "General Welfare / Guidance",
    "Other / Unclassified",
]

HIGH_SENSITIVITY_THEMES = {
    "Family / Dependent Visa Restrictions",
    "Visit Visa Restrictions",
    "KOC Gate Pass / GP Validity",
    "Differential Treatment by Nationality",
    "Legal / Detention / Police Matter",
    "Death / Mortal Remains",
    "Domestic Worker / Shelter / Abuse",
}

MEDIUM_SENSITIVITY_THEMES = {
    "Labour / Salary / Employer Dispute",
    "Nurses / Health Worker Welfare",
    "OPF / Insurance / Compensation",
}

KEYWORD_RULES: Sequence[Tuple[str, Sequence[str]]] = [
    (
        "OPF / Insurance / Compensation",
        (
            "opf",
            "opf card",
            "opf membership",
            "overseas pakistanis foundation",
            "insurance",
            "compensation",
            "pension",
            "death grant",
            "financial assistance",
        ),
    ),
    (
        "Family / Dependent Visa Restrictions",
        (
            "family visa",
            "dependent visa",
            "wife visa",
            "parents visa",
            "mother visa",
            "father visa",
            "bring my family",
            "family here in kuwait",
        ),
    ),
    (
        "Visit Visa Restrictions",
        (
            "visit visa",
            "family visit",
            "visit visa extension",
            "visit visa closed",
        ),
    ),
    (
        "KOC Gate Pass / GP Validity",
        (
            "koc",
            "gate pass",
            "gp",
            "drilling",
            "oil field",
            "contractor",
            "validity",
            "three months",
        ),
    ),
    (
        "Death / Mortal Remains",
        (
            "death",
            "dead body",
            "deceased",
            "mortal remains",
            "burial",
            "janaza",
            "funeral",
            "mortuary",
            "death certificate",
        ),
    ),
    (
        "Domestic Worker / Shelter / Abuse",
        (
            "domestic worker",
            "housemaid",
            "maid",
            "shelter",
            "abuse",
            "beaten",
            "violence",
            "harassment",
            "sexual abuse",
            "runaway",
            "escape from employer",
            "confiscated passport",
        ),
    ),
    (
        "Legal / Detention / Police Matter",
        (
            "deportation center",
            "deportation cell",
            "arrested",
            "arrest",
            "jail",
            "police",
            "cid",
            "court",
            "case in court",
            "lawyer",
            "advocate",
            "travel ban",
            "criminal case",
            "civil case",
            "legal notice",
        ),
    ),
    (
        "Labour / Salary / Employer Dispute",
        (
            "salary",
            "unpaid salary",
            "indemnity",
            "employer",
            "company",
            "sponsor",
            "kafeel",
            "release from company",
            "visa transfer due to company",
            "labour court",
            "labor court",
            "labour law",
            "labor law",
            "employee",
            "notice period",
            "dues",
        ),
    ),
    (
        "Nurses / Health Worker Welfare",
        (
            "nurse",
            "nursing",
            "moh",
            "hospital",
            "hostel",
            "accommodation",
            "health worker",
        ),
    ),
    (
        "Passport / NADRA / Consular Services",
        (
            "passport",
            "nadra",
            "cnic",
            "nicop",
            "poc",
            "attestation",
            "degree attestation",
            "consular",
            "power of attorney",
            "affidavit",
            "frc",
            "b-form",
        ),
    ),
    (
        "Differential Treatment by Nationality",
        (
            "nationality",
            "pakistani only",
            "pakistanis only",
            "pakistani nationals",
            "other nationality",
            "other nationalities",
            "discrimination",
            "discriminatory",
            "differential treatment",
            "different treatment",
            "not for pakistanis",
            "ban on pakistanis",
        ),
    ),
    (
        "General Welfare / Guidance",
        (
            "help",
            "guidance",
            "assistance",
            "support",
            "complaint",
            "problem",
            "welfare",
        ),
    ),
]

THEME_ACTIONS = {
    "Family / Dependent Visa Restrictions": "Track affected references and prepare consolidated policy note for senior review.",
    "Visit Visa Restrictions": "Consolidate cases and monitor whether refusals reflect a wider policy pattern.",
    "KOC Gate Pass / GP Validity": "Coordinate with relevant company liaison or project focal point for GP validity clarification.",
    "Differential Treatment by Nationality": "Escalate pattern evidence for senior diplomatic assessment, using only verified case references.",
    "Labour / Salary / Employer Dispute": "Refer for labour follow-up and document employer, salary, and contract issues where present.",
    "Legal / Detention / Police Matter": "Prioritize consular welfare check and legal-status verification through appropriate channels.",
    "Passport / NADRA / Consular Services": "Route to consular service desk for document-specific follow-up.",
    "Nurses / Health Worker Welfare": "Track healthcare worker cases separately and identify common employer or facility issues.",
    "Death / Mortal Remains": "Prioritize next-of-kin coordination and required documentation for remains or death-related process.",
    "Domestic Worker / Shelter / Abuse": "Prioritize protection response, shelter coordination, and welfare follow-up.",
    "OPF / Insurance / Compensation": "Route to welfare or OPF focal point and track claim evidence.",
    "General Welfare / Guidance": "Handle through routine welfare guidance and close once clear advice is provided.",
    "Other / Unclassified": "Review manually and assign an operational owner if further detail is needed.",
}

THEME_AUTHORITIES = {
    "Family / Dependent Visa Restrictions": ["Residency Affairs / Ministry of Interior"],
    "Visit Visa Restrictions": ["Residency Affairs / Ministry of Interior"],
    "KOC Gate Pass / GP Validity": ["Kuwait Oil Company / site access focal point"],
    "Differential Treatment by Nationality": ["Relevant Kuwaiti authority named in case text, if any", "Embassy senior leadership"],
    "Labour / Salary / Employer Dispute": ["Public Authority for Manpower", "Employer / sponsor"],
    "Legal / Detention / Police Matter": ["Police / courts / detention authority"],
    "Passport / NADRA / Consular Services": ["Embassy consular section", "NADRA / passport service desk"],
    "Nurses / Health Worker Welfare": ["Ministry of Health", "Employer / health facility"],
    "Death / Mortal Remains": ["Hospital / mortuary", "Civil affairs / police authority if required"],
    "Domestic Worker / Shelter / Abuse": ["Shelter / protection focal point", "Police or labour authority if required"],
    "OPF / Insurance / Compensation": ["OPF / insurance provider", "Embassy welfare section"],
    "General Welfare / Guidance": ["Embassy welfare section"],
    "Other / Unclassified": ["Embassy case officer"],
}

THEME_ISSUE_TYPES = {
    "Family / Dependent Visa Restrictions": "Policy / Diplomatic",
    "Visit Visa Restrictions": "Policy / Diplomatic",
    "KOC Gate Pass / GP Validity": "Policy / Diplomatic",
    "Differential Treatment by Nationality": "Policy / Diplomatic",
    "Legal / Detention / Police Matter": "Legal / Protection",
    "Death / Mortal Remains": "Legal / Protection",
    "Domestic Worker / Shelter / Abuse": "Legal / Protection",
    "OPF / Insurance / Compensation": "Operational / Service",
    "Passport / NADRA / Consular Services": "Operational / Service",
    "Nurses / Health Worker Welfare": "Operational / Service",
    "Labour / Salary / Employer Dispute": "Operational / Service",
    "General Welfare / Guidance": "Operational / Service",
    "Other / Unclassified": "Watch Item",
}

THEME_RECURRENCE_AUTHORITIES = {
    "Family / Dependent Visa Restrictions": "MOI Kuwait / Residency Affairs",
    "Visit Visa Restrictions": "MOI Kuwait / Residency Affairs",
    "KOC Gate Pass / GP Validity": "KOC / Employer / Concerned Kuwaiti Authority",
    "Differential Treatment by Nationality": "Relevant Kuwaiti Authority / Employer",
    "Legal / Detention / Police Matter": "Police / Courts / Deportation Centre / Legal Authorities",
    "Death / Mortal Remains": "Hospital / Mortuary / Local Authorities",
    "Domestic Worker / Shelter / Abuse": "Sponsor / Shelter / Police",
    "OPF / Insurance / Compensation": "OPF / Pakistan-side Institution",
    "Passport / NADRA / Consular Services": "Embassy Consular Section",
    "Nurses / Health Worker Welfare": "MOH / Employer / Facility",
    "Labour / Salary / Employer Dispute": "PAM / Labour Department / Employer",
    "General Welfare / Guidance": "Community Welfare Wing",
    "Other / Unclassified": "Unclear / To be reviewed",
}

THEME_RECURRENCE_ACTIONS = {
    "Family / Dependent Visa Restrictions": (
        "Compile current case references and seek official clarification on current "
        "family/dependent visa policy for Pakistani nationals if reports are verified."
    ),
    "Visit Visa Restrictions": (
        "Compile current reports and verify visit visa policy or extension practice "
        "before external representation."
    ),
    "KOC Gate Pass / GP Validity": (
        "Verify the report with complainant/company and consider clarification with "
        "the concerned authority if substantiated."
    ),
    "Differential Treatment by Nationality": (
        "Review evidence carefully and avoid external representation until facts are verified."
    ),
    "Legal / Detention / Police Matter": (
        "Ensure legal desk follow-up and senior visibility for cases involving detention, "
        "deportation, CID, or court proceedings."
    ),
    "Death / Mortal Remains": (
        "Ensure urgent welfare handling, family communication, and documentation follow-up."
    ),
    "Domestic Worker / Shelter / Abuse": (
        "Prioritize protection, shelter, and legal follow-up."
    ),
    "OPF / Insurance / Compensation": (
        "Prepare clearer OPF card guidance, FAQ, upload instructions, and standard reply "
        "template to reduce repeated queries."
    ),
    "Passport / NADRA / Consular Services": (
        "Review whether public guidance and branch contact information are sufficiently clear."
    ),
    "Nurses / Health Worker Welfare": (
        "Review cases with CWA/AP desk and identify repeated facility or accommodation concerns."
    ),
    "Labour / Salary / Employer Dispute": (
        "Monitor employers and ensure legal/labour desk follow-up where needed."
    ),
    "General Welfare / Guidance": (
        "Continue desk-level handling and identify whether repeated queries need public guidance."
    ),
    "Other / Unclassified": (
        "Review manually if repeated or linked to a sensitive authority."
    ),
}

THEME_VERIFICATION_NEEDED = {
    "Family / Dependent Visa Restrictions": True,
    "Visit Visa Restrictions": True,
    "KOC Gate Pass / GP Validity": True,
    "Differential Treatment by Nationality": True,
    "Legal / Detention / Police Matter": False,
    "Death / Mortal Remains": False,
    "Domestic Worker / Shelter / Abuse": False,
    "OPF / Insurance / Compensation": False,
    "Passport / NADRA / Consular Services": False,
    "Nurses / Health Worker Welfare": False,
    "Labour / Salary / Employer Dispute": False,
    "General Welfare / Guidance": False,
    "Other / Unclassified": True,
}

ENTITY_PATTERNS: Sequence[Tuple[str, Sequence[str]]] = (
    (
        "MOI / Ministry of Interior / Residency Affairs",
        (
            r"\bmoi\b",
            r"\bministry\s+of\s+interior\b",
            r"\bresidency\s+affairs\b",
            r"\bresidency\b",
        ),
    ),
    ("KOC", (r"\bkoc\b", r"\bkuwait\s+oil\s+company\b")),
    ("CID", (r"\bcid\b",)),
    (
        "Deportation Centre / Deportation Cell",
        (
            r"deportation\s+centre",
            r"deportation\s+center",
            r"deportation\s+cell",
        ),
    ),
    (
        "PAM / Labour Department",
        (
            r"\bpam\b",
            r"\blabour\s+department\b",
            r"\blabor\s+department\b",
            r"\bpublic\s+authority\s+for\s+manpower\b",
            r"\bmanpower\b",
            r"\blabour\s+court\b",
            r"\blabor\s+court\b",
        ),
    ),
    (
        "MOH / Ministry of Health",
        (
            r"\bmoh\b",
            r"\bministry\s+of\s+health\b",
            r"\bhospital\b",
        ),
    ),
    ("OPF", (r"\bopf\b", r"\boverseas\s+pakistanis\s+foundation\b")),
    (
        "Embassy Consular Section",
        (
            r"\bconsular\b",
            r"\bembassy\b",
        ),
    ),
    ("Police", (r"\bpolice\b",)),
    ("Court", (r"\bcourt\b",)),
)

SENSITIVE_ENTITIES = {
    "KOC",
    "CID",
    "Deportation Centre / Deportation Cell",
}

STRONG_LEGAL_TERMS = (
    "deportation center",
    "deportation cell",
    "arrested",
    "arrest",
    "jail",
    "police",
    "cid",
    "court",
    "case in court",
    "lawyer",
    "advocate",
    "travel ban",
    "criminal case",
    "civil case",
    "legal notice",
)

DISCRIMINATION_TERMS = (
    "discrimination",
    "discriminatory",
    "nationality",
    "pakistani only",
    "pakistanis only",
    "not for pakistanis",
    "different treatment",
    "differential treatment",
)

SENSITIVE_COLUMNS = {
    "phone",
    "mobile",
    "telephone",
    "email",
    "passport",
    "passport_no",
    "passport_number",
    "civil_id",
    "civilid",
    "cnic",
    "nicop",
    "requester_name",
    "name",
}

TEXT_COLUMNS = (
    "subject",
    "details",
    "category",
    "case_type",
    "module",
    "status",
    "assigned_to",
)

CLASSIFICATION_TEXT_COLUMNS = (
    "details",
    "subject",
    "category",
    "case_type",
    "module",
)

OPERATIONAL_THEMES = {
    "OPF / Insurance / Compensation",
    "Passport / NADRA / Consular Services",
    "General Welfare / Guidance",
    "Nurses / Health Worker Welfare",
    "Labour / Salary / Employer Dispute",
}

BAD_AI_PHRASES = (
    "what would you like me to do",
    "i can see you've provided",
    "i can see you have provided",
    "i've reviewed the provided dataset",
    "i have reviewed the provided dataset",
    "appears to be a structured dataset",
    "this dataset seems useful",
    "do you have any specific questions",
    "specific questions about this dataset",
    "let me know what you need",
    "how can i help",
    "performance of consular services",
    "confirmed discrimination",
    "definitely discriminating",
    "authorities are discriminating",
    "consular services continue to handle visa",
    "handle routine requests efficiently",
)

KOC_CORE_TERMS = (
    "koc",
    "gate pass",
    "gp",
    "drilling",
    "oil field",
)

KOC_SUPPORT_TERMS = (
    "contractor",
    "validity",
    "three months",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate an offline Ambassador Pulse Brief from a local CSV export."
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT,
        help=f"CSV file path. Defaults to {DEFAULT_INPUT}. Relative paths are resolved from this script's folder.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Local Ollama model name. Defaults to {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Reporting window label in days. Defaults to 7.",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Generate deterministic Markdown only and do not call local Ollama.",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help=(
            "End date YYYY-MM-DD for the report window. "
            "Defaults to the latest valid created_at date in the CSV, "
            "or today's date if no valid dates exist."
        ),
    )
    parser.add_argument(
        "--docx",
        action="store_true",
        help=(
            "Also export the Markdown report as ambassador_pulse_report.docx using Pandoc "
            "if it is installed locally."
        ),
    )
    return parser.parse_args()


def script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(script_dir(), path)


def normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def first_present(row: Dict[str, str], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        normalized = normalize_key(key)
        if normalized in row and row[normalized] not in (None, ""):
            return str(row[normalized]).strip()
    return default


def read_cases(csv_path: str) -> Tuple[List[Dict[str, str]], List[str]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"CSV file not found: {csv_path}\n"
            "Place cases_last_7_days.csv in the same folder as this script, or pass --input /path/to/file.csv."
        )

    with open(csv_path, "r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(handle, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError(f"CSV file has no header row: {csv_path}")

        original_headers = [header or "" for header in reader.fieldnames]
        normalized_headers = [normalize_key(header or "") for header in reader.fieldnames]

        rows: List[Dict[str, str]] = []
        for raw_row in reader:
            row: Dict[str, str] = {}
            for original, normalized in zip(original_headers, normalized_headers):
                value = raw_row.get(original, "")
                row[normalized] = "" if value is None else str(value).strip()
            rows.append(row)

    return rows, original_headers


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def mask_last_four(value: str) -> str:
    digits = digits_only(value)
    if not digits:
        return ""
    return "***" + digits[-4:]


def mask_email(value: str) -> str:
    value = (value or "").strip()
    if not value or "@" not in value:
        return ""
    local, domain = value.split("@", 1)
    if not local:
        return "***@" + domain
    return f"{local[0]}***@{domain}"


def mask_name(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    parts = [part for part in re.split(r"\s+", value) if part]
    if not parts:
        return ""
    masked = []
    for part in parts:
        if len(part) <= 1:
            masked.append(part[0] + "*" if part else "")
        else:
            masked.append(part[0] + "***")
    return " ".join(masked)


def redact_inline_identifiers(text: str) -> str:
    if not text:
        return ""

    redacted = text
    redacted = re.sub(
        r"([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})",
        r"\1***\2",
        redacted,
    )

    def redact_labeled_digits(match: re.Match[str]) -> str:
        label = match.group(1)
        number = match.group(2)
        last_four = digits_only(number)[-4:]
        if not last_four:
            return match.group(0)
        return f"{label} ***{last_four}"

    def redact_passport(match: re.Match[str]) -> str:
        label = match.group(1)
        value = match.group(2)
        last_four = digits_only(value)[-4:]
        if not last_four:
            return match.group(0)
        return f"{label} ***{last_four}"

    redacted = re.sub(
        r"\b(phone|mobile|telephone|civil\s*id|civilid|cnic|nicop)\s*[:#-]?\s*([+()0-9][0-9\s().-]{5,}[0-9])",
        redact_labeled_digits,
        redacted,
        flags=re.IGNORECASE,
    )
    redacted = re.sub(
        r"\b(passport)\s*[:#-]?\s*([A-Z0-9-]{5,})",
        redact_passport,
        redacted,
        flags=re.IGNORECASE,
    )

    def redact_unlabeled_number(match: re.Match[str]) -> str:
        value = match.group(0)
        stripped = value.strip()
        if re.fullmatch(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", stripped):
            return value
        if re.fullmatch(r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}", stripped):
            return value
        digits = digits_only(value)
        if len(digits) < 8:
            return value
        return "***" + digits[-4:]

    redacted = re.sub(r"\+?\d[\d\s().-]{6,}\d", redact_unlabeled_number, redacted)
    return redacted


def redact_row(row: Dict[str, str]) -> Dict[str, str]:
    redacted: Dict[str, str] = {}
    for key, value in row.items():
        if key in {"phone", "mobile", "telephone"}:
            redacted[key] = mask_last_four(value)
        elif key in {"passport", "passport_no", "passport_number", "civil_id", "civilid", "cnic", "nicop"}:
            redacted[key] = mask_last_four(value)
        elif key == "email":
            redacted[key] = mask_email(value)
        elif key in {"requester_name", "name"}:
            redacted[key] = mask_name(value)
        elif key in TEXT_COLUMNS:
            redacted[key] = redact_inline_identifiers(value)
        else:
            redacted[key] = redact_inline_identifiers(value) if key in SENSITIVE_COLUMNS else value
    return redacted


def combined_case_text(row: Dict[str, str], include_module: bool = True) -> str:
    columns = CLASSIFICATION_TEXT_COLUMNS if include_module else tuple(
        column for column in CLASSIFICATION_TEXT_COLUMNS if column != "module"
    )
    values = [first_present(row, [column]) for column in columns]
    return " ".join(value for value in values if value).strip()


def contains_keyword(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    keyword = keyword.lower()
    if re.fullmatch(r"[a-z0-9]{1,4}", keyword):
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
    return keyword in text


def contains_any_keyword(text: str, keywords: Sequence[str]) -> bool:
    return any(contains_keyword(text, keyword) for keyword in keywords)


def classify_theme(row: Dict[str, str]) -> str:
    text = combined_case_text(row).lower()
    content_text = combined_case_text(row, include_module=False).lower()
    if not text:
        return "Other / Unclassified"
    for theme, keywords in KEYWORD_RULES:
        search_text = content_text if theme == "OPF / Insurance / Compensation" else text
        if theme == "KOC Gate Pass / GP Validity":
            if contains_any_keyword(search_text, KOC_CORE_TERMS):
                return theme
            if contains_any_keyword(search_text, KOC_SUPPORT_TERMS) and contains_any_keyword(search_text, KOC_CORE_TERMS):
                return theme
            continue
        if theme == "Legal / Detention / Police Matter" and contains_any_keyword(
            search_text, ("labour court", "labor court", "labour law", "labor law")
        ):
            continue
        if contains_any_keyword(search_text, keywords):
            return theme
    return "Other / Unclassified"


def assign_sensitivity(theme: str, row: Dict[str, str]) -> str:
    text = combined_case_text(row).lower()
    if theme == "OPF / Insurance / Compensation":
        return "Medium"
    if theme in HIGH_SENSITIVITY_THEMES:
        return "High"
    if contains_any_keyword(text, DISCRIMINATION_TERMS):
        return "High"
    if contains_any_keyword(text, STRONG_LEGAL_TERMS):
        return "High"
    if theme in MEDIUM_SENSITIVITY_THEMES:
        return "Medium"
    return "Low"


def short_excerpt(row: Dict[str, str], max_chars: int = 260) -> str:
    subject = first_present(row, ["subject"])
    details = first_present(row, ["details"])
    category = first_present(row, ["category"])
    text = " | ".join(part for part in [subject, details, category] if part)
    text = redact_inline_identifiers(re.sub(r"\s+", " ", text).strip())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def case_reference(row: Dict[str, str], index: int) -> str:
    reference = first_present(row, ["reference", "ref", "case_reference", "case_id", "id"])
    return reference or f"ROW-{index:04d}"


def parse_date(value: str) -> Optional[dt.datetime]:
    value = (value or "").strip()
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(normalized)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    )
    for fmt in formats:
        try:
            return dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def created_range(rows: Sequence[Dict[str, str]]) -> Dict[str, Optional[str]]:
    dates = []
    for row in rows:
        parsed = parse_date(first_present(row, ["created_at", "created", "date"]))
        if parsed:
            dates.append(parsed)
    if not dates:
        return {"start": None, "end": None}
    return {
        "start": min(dates).date().isoformat(),
        "end": max(dates).date().isoformat(),
    }


def parse_case_date(value: str) -> Optional[dt.date]:
    """Parse a case ``created_at`` value into a date, returning None if unparseable."""
    parsed = parse_date(value)
    if parsed is None:
        return None
    if isinstance(parsed, dt.datetime):
        return parsed.date()
    if isinstance(parsed, dt.date):
        return parsed
    return None


def case_created_date(case: Dict[str, Any]) -> Optional[dt.date]:
    return parse_case_date(case.get("created_at", "") or "")


def determine_report_window(
    enriched_cases: Sequence[Dict[str, Any]],
    days: int,
    end_date_arg: Optional[str],
) -> Tuple[dt.date, dt.date, List[str], bool]:
    """Determine the report window. Returns (start_date, end_date, warnings, has_valid_dates)."""
    warnings: List[str] = []
    valid_dates: List[dt.date] = []
    for case in enriched_cases:
        d = case_created_date(case)
        if d is not None:
            valid_dates.append(d)

    has_valid = bool(valid_dates)

    if end_date_arg:
        try:
            end_date = dt.datetime.strptime(end_date_arg.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid --end-date format: '{end_date_arg}'. Expected YYYY-MM-DD."
            ) from exc
    elif valid_dates:
        end_date = max(valid_dates)
    else:
        end_date = dt.date.today()

    start_date = end_date - dt.timedelta(days=days - 1)

    if not has_valid:
        warnings.append("No valid created_at dates found; report uses all rows.")

    return start_date, end_date, warnings, has_valid


def split_cases_by_window(
    enriched_cases: Sequence[Dict[str, Any]],
    start_date: dt.date,
    end_date: dt.date,
    has_valid_dates: bool,
) -> Dict[str, List[Dict[str, Any]]]:
    """Split cases into report/historical/future/undated buckets by ``created_at`` date."""
    if not has_valid_dates:
        return {
            "report_cases": list(enriched_cases),
            "historical_cases": [],
            "future_cases": [],
            "undated_cases": list(enriched_cases),
        }

    report_cases: List[Dict[str, Any]] = []
    historical_cases: List[Dict[str, Any]] = []
    future_cases: List[Dict[str, Any]] = []
    undated_cases: List[Dict[str, Any]] = []

    for case in enriched_cases:
        d = case_created_date(case)
        if d is None:
            undated_cases.append(case)
        elif d < start_date:
            historical_cases.append(case)
        elif d > end_date:
            future_cases.append(case)
        else:
            report_cases.append(case)

    return {
        "report_cases": report_cases,
        "historical_cases": historical_cases,
        "future_cases": future_cases,
        "undated_cases": undated_cases,
    }


def detect_entities_in_text(text: str) -> List[str]:
    """Return the list of historical entities mentioned in ``text``."""
    if not text:
        return []
    lowered = text.lower()
    found: List[str] = []
    for entity, patterns in ENTITY_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lowered):
                found.append(entity)
                break
    return found


def detect_entities_in_case(case: Dict[str, Any]) -> List[str]:
    """Detect historical entities in the masked text of an enriched case."""
    parts: List[str] = []
    for key in ("excerpt", "category", "case_type", "module"):
        value = case.get(key)
        if value:
            parts.append(str(value))
    return detect_entities_in_text(" ".join(parts))


def analyze_historical_entities(
    report_cases: Sequence[Dict[str, Any]],
    historical_cases: Sequence[Dict[str, Any]],
    all_cases: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compute historical entity counts and trends across the three buckets."""

    entity_current_count: Counter[str] = Counter()
    entity_historical_count: Counter[str] = Counter()
    entity_all_count: Counter[str] = Counter()
    entity_current_refs: Dict[str, List[str]] = defaultdict(list)
    entity_historical_refs: Dict[str, List[str]] = defaultdict(list)

    def _accumulate(cases: Sequence[Dict[str, Any]], counter: Counter, refs_map: Optional[Dict[str, List[str]]]):
        for case in cases:
            for entity in detect_entities_in_case(case):
                counter[entity] += 1
                if refs_map is not None:
                    refs = refs_map[entity]
                    if len(refs) < 12 and case.get("reference"):
                        refs.append(case["reference"])

    _accumulate(report_cases, entity_current_count, entity_current_refs)
    _accumulate(historical_cases, entity_historical_count, entity_historical_refs)
    _accumulate(all_cases, entity_all_count, None)

    results: List[Dict[str, Any]] = []
    for entity, _ in ENTITY_PATTERNS:
        current = entity_current_count.get(entity, 0)
        historical = entity_historical_count.get(entity, 0)
        all_time = entity_all_count.get(entity, 0)

        include = (current > 0) or (all_time >= 3)
        if entity in SENSITIVE_ENTITIES and current > 0:
            include = True
        if not include:
            continue

        if current == 0:
            trend = "Historical only"
        elif historical == 0:
            trend = "New"
        elif historical >= 10:
            trend = "Long-running"
        elif current >= 5 or (current >= 3 and current >= historical / 2):
            trend = "Increasing"
        else:
            trend = "Repeated"

        results.append(
            {
                "entity": entity,
                "current_window_count": current,
                "historical_count_before_window": historical,
                "all_time_count": all_time,
                "current_refs": entity_current_refs.get(entity, [])[:8],
                "historical_refs": entity_historical_refs.get(entity, [])[:8],
                "trend_status": trend,
            }
        )
    return results


def _why_recurrence_matters(theme: str) -> str:
    mapping = {
        "Family / Dependent Visa Restrictions": (
            "Repeated reports of family/dependent visa difficulty for Pakistani nationals "
            "may indicate a pattern in MOI/Residency Affairs practice that warrants verification."
        ),
        "Visit Visa Restrictions": (
            "Repeated visit visa refusal or extension issues may indicate a wider host-government "
            "pattern needing verification before external representation."
        ),
        "KOC Gate Pass / GP Validity": (
            "Repeated KOC gate-pass concerns raise the possibility of differential site-access "
            "treatment for Pakistani workers and require employer/company verification."
        ),
        "Differential Treatment by Nationality": (
            "Allegations of differential treatment must be reviewed carefully; only verified "
            "evidence can support any external representation."
        ),
        "Legal / Detention / Police Matter": (
            "Detention, deportation, CID, or court-related cases involve liberty risk and require "
            "legal desk follow-up with senior visibility."
        ),
        "Death / Mortal Remains": (
            "Death and mortal-remains cases require urgent welfare handling, family communication, "
            "and documentation follow-up."
        ),
        "Domestic Worker / Shelter / Abuse": (
            "Protection cases require immediate welfare attention and safeguarding coordination."
        ),
        "OPF / Insurance / Compensation": (
            "Sustained OPF-related queries indicate that public guidance is unclear or insufficient "
            "and routine desk-level handling can absorb load."
        ),
        "Passport / NADRA / Consular Services": (
            "Recurrent consular documentation questions suggest public guidance can be improved."
        ),
        "Nurses / Health Worker Welfare": (
            "Recurrent welfare complaints from healthcare workers may indicate facility- or "
            "accommodation-level issues worth tracking."
        ),
        "Labour / Salary / Employer Dispute": (
            "Recurrent labour and salary disputes may indicate employers worth monitoring through "
            "the labour desk."
        ),
        "General Welfare / Guidance": (
            "Recurrent welfare guidance queries suggest a need for clearer public information."
        ),
        "Other / Unclassified": (
            "Unclassified items should be reviewed manually if repeated or linked to a sensitive authority."
        ),
    }
    return mapping.get(
        theme,
        "The theme is recurring or watch-worthy and should be reviewed by the appropriate desk.",
    )


def _theme_watch_signal(theme: str) -> bool:
    """Return True if a theme automatically qualifies as a watch item when present in window."""
    if theme in HIGH_SENSITIVITY_THEMES:
        return True
    if theme in {
        "KOC Gate Pass / GP Validity",
        "Legal / Detention / Police Matter",
        "Death / Mortal Remains",
    }:
        return True
    return False


def analyze_historical_recurrence(
    report_cases: Sequence[Dict[str, Any]],
    historical_cases: Sequence[Dict[str, Any]],
    all_cases: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build historical recurrence analysis objects for themes seen in the report window."""

    report_by_theme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    historical_by_theme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    all_by_theme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for case in report_cases:
        report_by_theme[case.get("theme", "Other / Unclassified")].append(case)
    for case in historical_cases:
        historical_by_theme[case.get("theme", "Other / Unclassified")].append(case)
    for case in all_cases:
        all_by_theme[case.get("theme", "Other / Unclassified")].append(case)

    results: List[Dict[str, Any]] = []
    for theme in THEMES:
        current = report_by_theme.get(theme, [])
        if not current:
            continue
        historical = historical_by_theme.get(theme, [])
        all_time = all_by_theme.get(theme, [])

        current_count = len(current)
        historical_count = len(historical)
        all_time_count = len(all_time)

        is_new = current_count > 0 and historical_count == 0
        is_repeated = current_count > 0 and historical_count > 0
        is_increasing = (
            current_count >= 5
            or (current_count >= 3 and current_count >= historical_count / 2 and historical_count > 0)
        )
        is_long_running = historical_count >= 10 and current_count > 0
        is_watch = _theme_watch_signal(theme)

        if is_increasing and is_long_running:
            trend_status = "Increasing / Long-running"
        elif is_long_running:
            trend_status = "Long-running"
        elif is_increasing:
            trend_status = "Increasing"
        elif is_repeated:
            trend_status = "Repeated"
        elif is_new:
            trend_status = "New"
        elif is_watch:
            trend_status = "Watch Item"
        else:
            trend_status = "New"

        why = _why_recurrence_matters(theme)
        if is_watch and trend_status not in ("Watch Item",):
            why = f"{why} Watch-item context: this theme is high-sensitivity and warrants attention even on a single report."

        current_refs = [c.get("reference", "") for c in current if c.get("reference")][:8]
        historical_refs = [c.get("reference", "") for c in historical if c.get("reference")][:8]
        current_excerpt = current[0].get("excerpt", "") if current else ""
        historical_excerpt = historical[0].get("excerpt", "") if historical else ""

        results.append(
            {
                "theme": theme,
                "issue_title": theme,
                "issue_type": THEME_ISSUE_TYPES.get(theme, "Watch Item"),
                "current_window_count": current_count,
                "historical_count_before_window": historical_count,
                "all_time_count": all_time_count,
                "trend_status": trend_status,
                "why_it_matters": why,
                "authority_or_institution": THEME_RECURRENCE_AUTHORITIES.get(
                    theme, "Embassy case officer"
                ),
                "evidence_current_refs": current_refs,
                "evidence_historical_refs": historical_refs,
                "representative_current_excerpt": shorten_text(current_excerpt, 220),
                "representative_historical_excerpt": shorten_text(historical_excerpt, 220),
                "recommended_action": THEME_RECURRENCE_ACTIONS.get(
                    theme,
                    THEME_ACTIONS.get(theme, "Review manually if repeated or linked to a sensitive authority."),
                ),
                "verification_needed": THEME_VERIFICATION_NEEDED.get(theme, False),
            }
        )

    # Sort: highest current count first, then by historical count
    results.sort(
        key=lambda item: (
            -item["current_window_count"],
            -item["historical_count_before_window"],
        )
    )
    return results


def suggested_authorities(theme: str, row: Dict[str, str]) -> List[str]:
    text = combined_case_text(row).lower()
    authorities = list(THEME_AUTHORITIES.get(theme, ["Embassy case officer"]))

    keyword_authorities = (
        ("moi", "Ministry of Interior"),
        ("residency", "Residency Affairs / Ministry of Interior"),
        ("pamm", "Public Authority for Manpower"),
        ("manpower", "Public Authority for Manpower"),
        ("koc", "Kuwait Oil Company"),
        ("police", "Police authority"),
        ("court", "Court / legal authority"),
        ("moh", "Ministry of Health"),
        ("hospital", "Hospital administration"),
        ("opf", "OPF"),
        ("insurance", "Insurance provider"),
    )
    for keyword, authority in keyword_authorities:
        if keyword in text and authority not in authorities:
            authorities.append(authority)
    return authorities[:4]


def build_enriched_cases(rows: Sequence[Dict[str, str]]) -> List[Dict[str, Any]]:
    enriched = []
    for index, row in enumerate(rows, start=1):
        redacted = redact_row(row)
        theme = classify_theme(redacted)
        sensitivity = assign_sensitivity(theme, redacted)
        enriched.append(
            {
                "reference": case_reference(redacted, index),
                "module": first_present(redacted, ["module"]),
                "created_at": first_present(redacted, ["created_at", "created", "date"]),
                "status": first_present(redacted, ["status"]),
                "assigned_to": first_present(redacted, ["assigned_to"]),
                "assigned_department": first_present(redacted, ["assigned_department", "department"]),
                "category": first_present(redacted, ["category"]),
                "case_type": first_present(redacted, ["case_type", "type"]),
                "theme": theme,
                "sensitivity": sensitivity,
                "excerpt": short_excerpt(redacted),
                "authorities": suggested_authorities(theme, redacted),
                "suggested_action": THEME_ACTIONS.get(theme, THEME_ACTIONS["Other / Unclassified"]),
            }
        )
    return enriched


def build_summary(enriched_cases: Sequence[Dict[str, Any]], days: int) -> Dict[str, Any]:
    theme_counts = Counter(case["theme"] for case in enriched_cases)
    sensitivity_counts = Counter(case["sensitivity"] for case in enriched_cases)
    module_counts = Counter(case["module"] or "Unspecified" for case in enriched_cases)
    status_counts = Counter(case["status"] or "Unspecified" for case in enriched_cases)
    assigned_to_counts = Counter(case["assigned_to"] or "Unassigned" for case in enriched_cases)
    assigned_department_counts = Counter(case["assigned_department"] or "Unspecified" for case in enriched_cases)
    samples_by_theme: Dict[str, List[str]] = defaultdict(list)
    status_by_theme: Dict[str, Counter[str]] = defaultdict(Counter)
    assigned_by_theme: Dict[str, Counter[str]] = defaultdict(Counter)
    high_sensitivity_issues = []

    for case in enriched_cases:
        theme = case["theme"]
        status_by_theme[theme][case["status"] or "Unspecified"] += 1
        assigned_by_theme[theme][case["assigned_to"] or "Unassigned"] += 1
        if len(samples_by_theme[theme]) < 5:
            samples_by_theme[theme].append(case["reference"])
        if case["sensitivity"] == "High":
            high_sensitivity_issues.append(
                {
                    "reference": case["reference"],
                    "theme": theme,
                    "module": case["module"],
                    "status": case["status"],
                    "assigned_to": case["assigned_to"],
                    "assigned_department": case["assigned_department"],
                    "excerpt": case["excerpt"],
                    "suggested_action": case["suggested_action"],
                }
            )

    workload_priority = [
        "OPF / Insurance / Compensation",
        "Passport / NADRA / Consular Services",
        "Labour / Salary / Employer Dispute",
        "General Welfare / Guidance",
        "Nurses / Health Worker Welfare",
        "Other / Unclassified",
    ]
    diplomatic_priority = [
        "Differential Treatment by Nationality",
        "Family / Dependent Visa Restrictions",
        "Visit Visa Restrictions",
        "KOC Gate Pass / GP Validity",
        "Legal / Detention / Police Matter",
        "Death / Mortal Remains",
        "Domestic Worker / Shelter / Abuse",
    ]

    operational_candidates = {theme: theme_counts[theme] for theme in workload_priority if theme_counts[theme]}
    if operational_candidates:
        top_operational = max(operational_candidates.items(), key=lambda item: (item[1], -workload_priority.index(item[0])))
    elif theme_counts:
        top_operational = theme_counts.most_common(1)[0]
    else:
        top_operational = None

    diplomatic_candidates = {theme: theme_counts[theme] for theme in diplomatic_priority if theme_counts[theme]}
    top_diplomatic_theme = None
    if diplomatic_candidates:
        top_diplomatic_theme = max(
            diplomatic_candidates.items(),
            key=lambda item: (item[1], -diplomatic_priority.index(item[0])),
        )[0]
    top_diplomatic = (
        {"theme": top_diplomatic_theme, "count": theme_counts[top_diplomatic_theme]}
        if top_diplomatic_theme
        else None
    )

    return {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "reporting_window_days": days,
        "total_cases": len(enriched_cases),
        "created_range": created_range([case for case in enriched_cases]),
        "counts_by_theme": {theme: theme_counts.get(theme, 0) for theme in THEMES},
        "counts_by_sensitivity": {
            "High": sensitivity_counts.get("High", 0),
            "Medium": sensitivity_counts.get("Medium", 0),
            "Low": sensitivity_counts.get("Low", 0),
        },
        "counts_by_module": dict(module_counts.most_common()),
        "counts_by_status": dict(status_counts.most_common()),
        "counts_by_assigned_to": dict(assigned_to_counts.most_common()),
        "counts_by_assigned_department": dict(assigned_department_counts.most_common()),
        "status_by_theme": {
            theme: dict(counter.most_common()) for theme, counter in sorted(status_by_theme.items())
        },
        "assigned_to_by_theme": {
            theme: dict(counter.most_common(5)) for theme, counter in sorted(assigned_by_theme.items())
        },
        "high_sensitivity_issues": high_sensitivity_issues,
        "top_operational_workload": (
            {"theme": top_operational[0], "count": top_operational[1]} if top_operational else None
        ),
        "top_diplomatic_issue": top_diplomatic,
        "sample_case_references_by_theme": {theme: samples_by_theme.get(theme, []) for theme in THEMES},
    }


def shorten_text(text: str, max_chars: int = 250) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def case_sample_for_ai(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "reference": case["reference"],
        "module": case["module"],
        "theme": case["theme"],
        "sensitivity": case["sensitivity"],
        "status": case["status"],
        "assigned_to": case["assigned_to"],
        "assigned_department": case["assigned_department"],
        "short_excerpt": shorten_text(case["excerpt"], 250),
        "authorities": case["authorities"],
        "suggested_action": case["suggested_action"],
    }


def build_ai_payload(summary: Dict[str, Any], enriched_cases: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Build the AI payload from the *report-window* enriched cases and current summary.

    ``enriched_cases`` here must be limited to the report window (current ``report_cases``);
    historical context is conveyed via ``summary['historical_recurrence']`` and
    ``summary['historical_entities']`` only.
    """
    summary_keys = (
        "generated_at",
        "reporting_window_days",
        "report_window",
        "input_dataset",
        "total_cases",
        "created_range",
        "counts_by_theme",
        "counts_by_sensitivity",
        "counts_by_module",
        "counts_by_status",
        "counts_by_assigned_to",
        "counts_by_assigned_department",
        "status_by_theme",
        "assigned_to_by_theme",
        "top_operational_workload",
        "top_diplomatic_issue",
        "sample_case_references_by_theme",
    )
    deterministic_summary = {key: summary.get(key) for key in summary_keys}

    high_samples = [
        case_sample_for_ai(case) for case in enriched_cases if case["sensitivity"] == "High"
    ][:12]
    operational_samples = [
        case_sample_for_ai(case) for case in enriched_cases if case["theme"] in OPERATIONAL_THEMES
    ][:10]

    return {
        "deterministic_summary": deterministic_summary,
        "theme_counts": summary.get("counts_by_theme", {}),
        "high_sensitivity_case_samples": high_samples,
        "operational_workload_samples": operational_samples,
        "sample_references_by_theme": summary.get("sample_case_references_by_theme", {}),
        "historical_recurrence": summary.get("historical_recurrence", []),
        "historical_entities": summary.get("historical_entities", []),
        "case_payload_note": (
            "Personal identifiers have been masked. Only current-window summary data, "
            "current-window high-sensitivity samples, current-window operational workload samples, "
            "and historical recurrence/entity context are included. Historical counts come "
            "exclusively from records before the report window. Current-window counts and "
            "references must never be conflated with historical counts."
        ),
    }


def format_counts_for_prompt(counts: Dict[str, Any]) -> str:
    populated = [(key, value) for key, value in counts.items() if value]
    if not populated:
        return "- None"
    return "\n".join(f"- {key}: {value}" for key, value in populated)


def format_case_samples_for_prompt(samples: Sequence[Dict[str, Any]]) -> str:
    if not samples:
        return "- None"
    lines = []
    for case in samples:
        assigned = case.get("assigned_to") or case.get("assigned_department")
        fields = [
            case.get("reference") or "-",
            case.get("theme") or "-",
            case.get("sensitivity") or "-",
            case.get("status") or "-",
        ]
        if assigned:
            fields.append(f"assigned: {assigned}")
        fields.append(case.get("short_excerpt") or "No excerpt available.")
        lines.append("- " + " | ".join(fields))
    return "\n".join(lines)


def _format_historical_recurrence_for_prompt(items: Sequence[Dict[str, Any]]) -> str:
    if not items:
        return "- None"
    lines = []
    for item in items:
        current_refs = ", ".join(item.get("evidence_current_refs", [])) or "None"
        historical_refs = ", ".join(item.get("evidence_historical_refs", [])) or "None"
        lines.append(
            "- "
            + " | ".join(
                [
                    item.get("issue_title", item.get("theme", "Issue")),
                    f"type: {item.get('issue_type', 'Watch Item')}",
                    f"current: {item.get('current_window_count', 0)}",
                    f"historical: {item.get('historical_count_before_window', 0)}",
                    f"all-time: {item.get('all_time_count', 0)}",
                    f"trend: {item.get('trend_status', '')}",
                    f"current_refs: {current_refs}",
                    f"historical_refs: {historical_refs}",
                    f"authority: {item.get('authority_or_institution', '')}",
                ]
            )
        )
    return "\n".join(lines)


def _format_historical_entities_for_prompt(items: Sequence[Dict[str, Any]]) -> str:
    if not items:
        return "- None"
    lines = []
    for entity in items:
        current_refs = ", ".join(entity.get("current_refs", [])) or "None"
        historical_refs = ", ".join(entity.get("historical_refs", [])) or "None"
        lines.append(
            "- "
            + " | ".join(
                [
                    entity.get("entity", ""),
                    f"current: {entity.get('current_window_count', 0)}",
                    f"historical: {entity.get('historical_count_before_window', 0)}",
                    f"all-time: {entity.get('all_time_count', 0)}",
                    f"trend: {entity.get('trend_status', '')}",
                    f"current_refs: {current_refs}",
                    f"historical_refs: {historical_refs}",
                ]
            )
        )
    return "\n".join(lines)


def build_source_summary_for_prompt(payload: Dict[str, Any]) -> str:
    summary = payload["deterministic_summary"]
    sensitivity = summary.get("counts_by_sensitivity", {})
    top_workload = summary.get("top_operational_workload") or {}
    top_diplomatic = summary.get("top_diplomatic_issue") or {}
    high_samples = payload.get("high_sensitivity_case_samples", [])
    operational_samples = payload.get("operational_workload_samples", [])
    report_window = summary.get("report_window") or {}
    input_dataset = summary.get("input_dataset") or {}
    historical_recurrence = payload.get("historical_recurrence") or []
    historical_entities = payload.get("historical_entities") or []

    window_label = "Not specified"
    if report_window.get("start_date") and report_window.get("end_date"):
        window_label = (
            f"{report_window['start_date']} to {report_window['end_date']} "
            f"({report_window.get('days', 0)} days)"
        )

    lines = [
        "SOURCE OF TRUTH (current report window only):",
        f"- Report window: {window_label}",
        (
            "- Input dataset: "
            f"total {input_dataset.get('total_rows', 0)}, "
            f"dated {input_dataset.get('dated_rows', 0)}, "
            f"undated {input_dataset.get('undated_rows', 0)}, "
            f"historical-before-window {input_dataset.get('historical_rows_before_window', 0)}, "
            f"in-window {input_dataset.get('report_window_rows', 0)}, "
            f"future-after-window {input_dataset.get('future_rows_after_window', 0)}"
        ),
        f"- Current-window total cases: {summary.get('total_cases', 0)}",
        (
            "- Current-window sensitivity counts: "
            f"High {sensitivity.get('High', 0)}, "
            f"Medium {sensitivity.get('Medium', 0)}, "
            f"Low {sensitivity.get('Low', 0)}"
        ),
        (
            "- Top current-window operational workload: "
            f"{top_workload.get('theme', 'None')} ({top_workload.get('count', 0)} cases)"
        ),
        (
            "- Top current-window diplomatic issue: "
            f"{top_diplomatic.get('theme', 'None')} ({top_diplomatic.get('count', 0)} cases)"
        ),
        "",
        "Current-window counts by theme:",
        format_counts_for_prompt(summary.get("counts_by_theme", {})),
        "",
        "Current-window sample references by theme:",
        format_counts_for_prompt(
            {
                theme: ", ".join(refs)
                for theme, refs in (summary.get("sample_case_references_by_theme") or {}).items()
                if refs
            }
        ),
        "",
        "Current-window high-sensitivity case samples, max 12:",
        format_case_samples_for_prompt(high_samples),
        "",
        "Current-window operational workload samples, max 10:",
        format_case_samples_for_prompt(operational_samples),
        "",
        "HISTORICAL CONTEXT (records BEFORE the report window — do NOT treat as current workload):",
        "Historical recurrence (theme | type | current | historical | all-time | trend | current_refs | historical_refs | authority):",
        _format_historical_recurrence_for_prompt(historical_recurrence),
        "",
        "Historical entity / authority mentions:",
        _format_historical_entities_for_prompt(historical_entities),
    ]
    return "\n".join(lines)


def build_prompt(payload: Dict[str, Any]) -> str:
    source_summary = build_source_summary_for_prompt(payload)
    summary = payload.get("deterministic_summary", {})
    report_window = summary.get("report_window") or {}
    window_label = "the current report window"
    if report_window.get("start_date") and report_window.get("end_date"):
        window_label = (
            f"the report window {report_window['start_date']} to {report_window['end_date']} "
            f"({report_window.get('days', 0)} days)"
        )
    return "\n".join(
        [
            "SYSTEM/TASK:",
            "You are drafting an internal Ambassador Pulse Brief for the Embassy of Pakistan, Kuwait.",
            "You must produce the final briefing now.",
            f"The MAIN REPORT covers ONLY {window_label}.",
            "HISTORICAL records (records before the report window) are provided ONLY to identify repeated, increasing, or long-running issues.",
            "Do not treat historical counts as current-week workload.",
            "Do not mix current and historical references in the same evidence list.",
            "Use current evidence references for current issues; use historical references only inside historical context or recurrence sections.",
            "Do not invent references or counts. Use only references and counts that appear in the SOURCE OF TRUTH section below.",
            "Always include a 'Repeated / Emerging Issues for Attention' section if the historical recurrence list is non-empty, near the top of the briefing.",
            "Always state the report window clearly near the top of the briefing.",
            "Do not ask questions.",
            "Do not say you need more instructions.",
            "Do not say 'what would you like me to do?'",
            "Do not describe the JSON.",
            "Do not invent facts.",
            "Use only the provided deterministic data.",
            "Use the deterministic audit summary as source of truth.",
            "Keep the tone official, concise, and embassy-style.",
            "Write as an internal Embassy policy brief, not as a generic AI summary.",
            "Separate operational workload from diplomatic or senior-attention issues.",
            "Use phrases such as 'reported by applicants', 'requires verification', 'may warrant clarification', and 'if confirmed'.",
            "Distinguish applicant reports from confirmed official policy or confirmed discrimination.",
            "Do not state that Kuwaiti authorities are definitely discriminating unless the data confirms only that fact; if the data is an allegation, call it a report or allegation.",
            "Do not blame Embassy consular services for host-government visa, MOI, residency, KOC, or gate-pass restrictions.",
            "Do not use the phrase 'performance of consular services' for MOI/residency issues.",
            "Do not say 'escalate' unless a deterministic suggested action uses that exact word.",
            "Prefer 'seek official clarification from relevant Kuwaiti authorities' for verified host-government policy issues.",
            "Avoid 'urgent' unless sensitivity is High and the case indicates detention, death, abuse, or immediate risk.",
            "Avoid vague staff comments about 'Unspecified' or 'Unassigned' cases unless a clear table field supports the statement.",
            "Use each evidence reference only under its own deterministic theme; do not move Legal/Detention references into visa sections.",
            "Do not remove OPF from the operational workload section if OPF is the top current-window workload.",
            "Do not include personal identifiers, internal reasoning, analysis tags, or <think> content.",
            "",
            source_summary,
            "",
            "APPROVED PHRASING GUIDANCE:",
            "Family / Dependent Visa Restrictions: Applicants reported difficulty obtaining or processing family/dependent visas for Pakistani nationals. The matter appears to involve MOI/Residency Affairs policy or practice and may warrant official clarification through appropriate channels.",
            "Visit Visa Restrictions: Applicants reported difficulty with visit visa validity, extension, or reopening. These reports should be compiled and verified before any external representation.",
            "KOC Gate Pass / GP Validity: A report indicates shorter gate-pass validity for Pakistani workers compared with other nationalities. This should be verified with the employer/company and, if substantiated, considered for clarification with the concerned authority.",
            "Legal / Detention / Police Matter: Cases involving detention, CID, deportation centre, court, or police require close legal desk follow-up and senior visibility where liberty or deportation risk is involved.",
            "OPF / Insurance / Compensation: OPF-related queries form the largest operational workload. These appear to be service-guidance matters and should be addressed through clearer public instructions and desk-level handling.",
            "",
            "OUTPUT FORMAT:",
            "# Ambassador Pulse Brief",
            "",
            "Report window: {start_date} to {end_date} ({days} days).",
            "",
            "## 1. Key Points for Ambassador",
            "5 concise bullets covering ONLY current-window data.",
            "",
            "## Repeated / Emerging Issues for Attention",
            "Include this section when historical recurrence data is non-empty.",
            "For each item, write the issue title and report:",
            "- Type, current-window count, historical count before window, all-time count",
            "- Trend status (New / Repeated / Increasing / Long-running / Watch Item / Increasing / Long-running)",
            "- Why it matters",
            "- Authority / institution",
            "- Current evidence references (current_refs only)",
            "- Historical evidence examples (historical_refs only)",
            "- Recommended action and verification needed (Yes/No)",
            "If the historical recurrence list is empty, write 'None identified in the reporting window.'",
            "",
            "## 2. Issues Requiring Diplomatic / Senior Attention",
            "For each high-sensitivity theme:",
            "- Issue",
            "- What is being reported",
            "- Why it matters",
            "- Evidence references",
            "- Suggested action",
            "",
            "## 3. Community Service Workload",
            "Summarize operational/service themes:",
            "- OPF",
            "- Passport/NADRA/Consular",
            "- General welfare",
            "- Nurses",
            "- Labour/employer",
            "",
            "## 4. Staff / Operational Follow-up",
            "Mention assigned desks only when named in the deterministic data.",
            "Highlight pending/assigned cases by theme where useful.",
            "",
            "## 5. Suggested Action Points",
            "Use practical diplomatic action points:",
            "- Prepare a short list of family/visit visa references for internal review.",
            "- Verify the KOC gate-pass report with the complainant/company before external engagement.",
            "- Ensure legal/detention cases are tracked by the legal desk until action is recorded.",
            "- Publish or prepare clearer OPF card guidance to reduce repeated queries.",
            "- Continue weekly export and offline pulse review.",
        ]
    ).strip()


def call_ollama(prompt: str, model: str) -> str:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2},
    }
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise RuntimeError(
            "Ollama is not running or is unreachable at http://localhost:11434.\n"
            "Start Ollama locally, confirm the model is installed, or rerun with --no-ai.\n"
            f"Details: {reason}"
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError(
            "Ollama did not respond before the timeout. Try again, use a smaller CSV, or rerun with --no-ai."
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            "Ollama timed out or failed while reading the local response. "
            "Try again, use --no-ai, or use a smaller prompt/model."
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama returned a non-JSON response: {raw[:300]}") from exc

    if "error" in payload:
        error = str(payload["error"])
        if "not found" in error.lower() or "pull" in error.lower():
            raise RuntimeError(
                f"Ollama model not found or unavailable: {model}\n"
                f"Install it locally with: ollama pull {model}\n"
                f"Details: {error}"
            )
        raise RuntimeError(f"Ollama API call failed: {error}")

    response_text = payload.get("response")
    if not isinstance(response_text, str) or not response_text.strip():
        raise RuntimeError(f"Ollama API call returned no usable response. Raw response: {raw[:300]}")
    return clean_ai_response(response_text)


def clean_ai_response(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL).strip()
    return cleaned or text.strip()


def markdown_table(rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return ""
    header = rows[0]
    separator = ["---"] * len(header)
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in rows[1:]:
        escaped = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")
    return "\n".join(lines)


def deterministic_markdown(summary: Dict[str, Any]) -> str:
    total = summary["total_cases"]
    generated_at = summary["generated_at"]
    days = summary["reporting_window_days"]
    date_range = summary.get("created_range") or {}
    theme_rows = [["Theme", "Count", "Sample references"]]
    for theme, count in summary["counts_by_theme"].items():
        if count:
            samples = ", ".join(summary["sample_case_references_by_theme"].get(theme, [])) or "-"
            theme_rows.append([theme, str(count), samples])

    sensitivity = summary["counts_by_sensitivity"]
    high_issues = summary["high_sensitivity_issues"]
    top_workload = summary.get("top_operational_workload")
    top_diplomatic = summary.get("top_diplomatic_issue")

    high_lines = []
    if high_issues:
        for issue in high_issues[:20]:
            high_lines.append(
                f"- {issue['reference']}: {issue['theme']} - {issue['excerpt'] or 'No excerpt available.'}"
            )
        if len(high_issues) > 20:
            high_lines.append(f"- Additional high-sensitivity cases not listed here: {len(high_issues) - 20}")
    else:
        high_lines.append("- No high-sensitivity cases were identified by keyword rules.")

    workload_line = (
        f"{top_workload['theme']} ({top_workload['count']} cases)"
        if top_workload
        else "No operational workload identified."
    )
    diplomatic_line = (
        f"{top_diplomatic['theme']} ({top_diplomatic['count']} cases)"
        if top_diplomatic
        else "No diplomatic issue identified."
    )

    report_window = summary.get("report_window") or {}
    input_dataset = summary.get("input_dataset") or {}

    lines = [
        "# Ambassador Pulse Brief",
        "",
        f"Generated: {generated_at}",
        "",
        f"Reporting window label: last {days} days.",
    ]
    if report_window.get("start_date") and report_window.get("end_date"):
        lines.extend(
            [
                "",
                f"Report window: {report_window['start_date']} to {report_window['end_date']} "
                f"({report_window.get('days', days)} days).",
            ]
        )
    if date_range.get("start") and date_range.get("end"):
        lines.extend(["", f"In-window case date range: {date_range['start']} to {date_range['end']}."])
    if input_dataset:
        lines.extend(
            [
                "",
                "## Input Dataset",
                "",
                f"- Total rows in CSV: {input_dataset.get('total_rows', 0)}",
                f"- Dated rows: {input_dataset.get('dated_rows', 0)}",
                f"- Undated rows: {input_dataset.get('undated_rows', 0)}",
                f"- Historical rows before window: {input_dataset.get('historical_rows_before_window', 0)}",
                f"- Report window rows: {input_dataset.get('report_window_rows', 0)}",
                f"- Future rows after window: {input_dataset.get('future_rows_after_window', 0)}",
            ]
        )
        warnings = input_dataset.get("warnings") or []
        if warnings:
            lines.append("- Warnings:")
            for warning in warnings:
                lines.append(f"  - {warning}")
    lines.extend(
        [
            "",
            "## Deterministic Summary",
            "",
            f"Total cases (current window): {total}",
            "",
            f"Sensitivity counts: High {sensitivity['High']}, Medium {sensitivity['Medium']}, Low {sensitivity['Low']}.",
            "",
            f"Top operational workload: {workload_line}",
            "",
            f"Top diplomatic issue: {diplomatic_line}",
            "",
            "## Counts by Theme",
            "",
            markdown_table(theme_rows) if len(theme_rows) > 1 else "No cases found.",
            "",
            "## High-Sensitivity Issues",
            "",
            os.linesep.join(high_lines),
            "",
            "## Notes",
            "",
            "This section was generated deterministically from local keyword rules. Personal identifiers were masked before any AI drafting step. Counts here apply to the report window only; historical data is used for recurrence context.",
        ]
    )
    return "\n".join(lines).strip()


def case_count_phrase(count: int) -> str:
    return f"{count} case" if count == 1 else f"{count} cases"


def format_top_counts(counts: Dict[str, Any], limit: int = 5, skip_unknown: bool = False) -> str:
    unknown = {"Unspecified", "Unassigned", ""}
    populated = [
        (key, value)
        for key, value in counts.items()
        if value and (not skip_unknown or key not in unknown)
    ]
    if not populated:
        return "None available"
    return ", ".join(f"{key} ({value})" for key, value in populated[:limit])


def format_theme_refs(summary: Dict[str, Any], theme: str, limit: int = 6) -> str:
    refs = summary.get("sample_case_references_by_theme", {}).get(theme, [])[:limit]
    return ", ".join(refs) if refs else "No sample references"


def active_theme_list(summary: Dict[str, Any], limit: int = 3) -> str:
    counts = summary.get("counts_by_theme", {})
    populated = [(theme, count) for theme, count in counts.items() if count]
    populated.sort(key=lambda item: item[1], reverse=True)
    if not populated:
        return "No active themes"
    return ", ".join(f"{theme} ({count})" for theme, count in populated[:limit])


def why_theme_matters(theme: str) -> str:
    mapping = {
        "Family / Dependent Visa Restrictions": "Applicants reported difficulty obtaining or processing family/dependent visas for Pakistani nationals. The matter appears to involve MOI/Residency Affairs policy or practice and may warrant official clarification through appropriate channels.",
        "Visit Visa Restrictions": "Applicants reported difficulty with visit visa validity, extension, or reopening. These reports should be compiled and verified before any external representation.",
        "KOC Gate Pass / GP Validity": "A report indicates shorter gate-pass validity for Pakistani workers compared with other nationalities. This should be verified with the employer/company and, if substantiated, considered for clarification with the concerned authority.",
        "Differential Treatment by Nationality": "Any differential-treatment report should be treated as an allegation requiring careful verification before external representation.",
        "Legal / Detention / Police Matter": "Cases involving detention, CID, deportation centre, court, or police require close legal desk follow-up and senior visibility where liberty or deportation risk is involved.",
        "Death / Mortal Remains": "Death and mortal-remains cases require immediate family support and close procedural coordination.",
        "Domestic Worker / Shelter / Abuse": "Protection cases require immediate welfare attention and safeguarding coordination.",
    }
    return mapping.get(theme, "The issue is marked high sensitivity and should be reviewed by the appropriate senior desk.")


def suggested_policy_action(theme: str, fallback: str) -> str:
    mapping = {
        "Family / Dependent Visa Restrictions": "Compile the listed family/dependent visa references for internal review, verify the reported restriction pattern, and seek official clarification through appropriate channels if confirmed.",
        "Visit Visa Restrictions": "Compile visit visa references, verify validity or extension issues, and consider official clarification only after the reports are confirmed.",
        "KOC Gate Pass / GP Validity": "Verify the gate-pass validity report with the complainant and company before any external engagement; if substantiated, seek clarification from the concerned authority.",
        "Legal / Detention / Police Matter": "Ensure each legal/detention case is tracked by the legal desk until action is recorded, with senior visibility where liberty or deportation risk is involved.",
        "Death / Mortal Remains": "Maintain close family coordination and track required documentation until the death or mortal-remains process is resolved.",
        "Domestic Worker / Shelter / Abuse": "Maintain protection follow-up with the relevant welfare or shelter channel and record each action taken.",
        "OPF / Insurance / Compensation": "Publish or prepare clearer OPF card guidance and route repeated OPF queries through desk-level handling.",
    }
    return mapping.get(theme, fallback)


def status_line_for_theme(summary: Dict[str, Any], theme: str) -> str:
    status_counts = summary.get("status_by_theme", {}).get(theme, {})
    if not status_counts:
        return "No status data"
    return ", ".join(f"{status} {count}" for status, count in status_counts.items())


def assigned_line_for_theme(summary: Dict[str, Any], theme: str) -> str:
    assigned_counts = summary.get("assigned_to_by_theme", {}).get(theme, {})
    if not assigned_counts:
        return "No assigned desk data"
    known_counts = {owner: count for owner, count in assigned_counts.items() if owner not in {"Unassigned", ""}}
    if not known_counts:
        return "No named desk data"
    return ", ".join(f"{owner} {count}" for owner, count in known_counts.items())


def _format_recurrence_section(historical_recurrence: Sequence[Dict[str, Any]]) -> List[str]:
    lines = ["## Repeated / Emerging Issues for Attention", ""]
    if not historical_recurrence:
        lines.append("None identified in the reporting window.")
        lines.append("")
        return lines
    for issue in historical_recurrence:
        title = issue.get("issue_title") or issue.get("theme") or "Issue"
        current_refs = ", ".join(issue.get("evidence_current_refs", [])) or "None"
        historical_refs = ", ".join(issue.get("evidence_historical_refs", [])) or "None"
        verification = "Yes" if issue.get("verification_needed") else "No"
        lines.extend(
            [
                f"### {title}",
                f"- Type: {issue.get('issue_type', 'Watch Item')}",
                f"- Current window: {case_count_phrase(issue.get('current_window_count', 0))}",
                f"- Historical before this window: {case_count_phrase(issue.get('historical_count_before_window', 0))}",
                f"- All-time in export: {case_count_phrase(issue.get('all_time_count', 0))}",
                f"- Trend: {issue.get('trend_status', 'Watch Item')}",
                f"- Why flagged: {issue.get('why_it_matters', '')}",
                f"- Authority / institution: {issue.get('authority_or_institution', '')}",
                f"- Current evidence references: {current_refs}",
                f"- Historical evidence examples: {historical_refs}",
                f"- Recommended action: {issue.get('recommended_action', '')}",
                f"- Verification needed: {verification}",
                "",
            ]
        )
    return lines


def _format_entities_section(historical_entities: Sequence[Dict[str, Any]]) -> List[str]:
    if not historical_entities:
        return []
    lines = ["## Historical Authority / Entity Mentions", ""]
    for entity in historical_entities:
        current_refs = ", ".join(entity.get("current_refs", [])) or "None"
        historical_refs = ", ".join(entity.get("historical_refs", [])) or "None"
        lines.append(
            f"- {entity.get('entity', '')}: current window {entity.get('current_window_count', 0)}, "
            f"historical before window {entity.get('historical_count_before_window', 0)}, "
            f"all-time {entity.get('all_time_count', 0)}; trend {entity.get('trend_status', '')}. "
            f"Current refs: {current_refs}. Historical refs: {historical_refs}."
        )
    lines.append("")
    return lines


def build_deterministic_brief(summary: Dict[str, Any]) -> str:
    counts = summary.get("counts_by_theme", {})
    sensitivity = summary.get("counts_by_sensitivity", {})
    total = summary.get("total_cases", 0)
    high_count = sensitivity.get("High", 0)
    medium_count = sensitivity.get("Medium", 0)
    low_count = sensitivity.get("Low", 0)
    top_workload = summary.get("top_operational_workload") or {}
    top_diplomatic = summary.get("top_diplomatic_issue") or {}
    report_window = summary.get("report_window") or {}
    historical_recurrence = summary.get("historical_recurrence") or []
    historical_entities = summary.get("historical_entities") or []

    workload_text = (
        f"{top_workload.get('theme')} ({case_count_phrase(top_workload.get('count', 0))})"
        if top_workload
        else "No operational workload identified"
    )
    diplomatic_text = (
        f"{top_diplomatic.get('theme')} ({case_count_phrase(top_diplomatic.get('count', 0))})"
        if top_diplomatic
        else "No high-sensitivity diplomatic issue identified"
    )

    window_line = ""
    if report_window.get("start_date") and report_window.get("end_date"):
        window_line = (
            f"Report window: {report_window.get('start_date')} to {report_window.get('end_date')} "
            f"({report_window.get('days', 0)} days)."
        )

    lines = [
        "# Ambassador Pulse Brief",
        "",
    ]
    if window_line:
        lines.extend([window_line, ""])
    lines.extend(
        [
            "## 1. Key Points for Ambassador",
            "",
            f"- {case_count_phrase(total)} reviewed for the report window.",
            f"- Sensitivity profile: High {high_count}, Medium {medium_count}, Low {low_count}.",
            f"- Primary operational workload: {workload_text}.",
            f"- Primary diplomatic or senior-attention issue: {diplomatic_text}.",
            f"- Most active themes: {active_theme_list(summary)}.",
            "",
        ]
    )
    lines.extend(_format_recurrence_section(historical_recurrence))
    lines.extend(_format_entities_section(historical_entities))
    lines.extend(
        [
            "## 2. Issues Requiring Diplomatic / Senior Attention",
            "",
        ]
    )

    high_by_theme: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for issue in summary.get("high_sensitivity_issues", []):
        high_by_theme[issue.get("theme", "Other / Unclassified")].append(issue)

    if not high_by_theme:
        lines.append("- No high-sensitivity themes were identified by the deterministic classifier.")
    else:
        ordered_high_themes = sorted(
            high_by_theme,
            key=lambda theme: counts.get(theme, len(high_by_theme[theme])),
            reverse=True,
        )
        for theme in ordered_high_themes:
            issues = high_by_theme[theme]
            refs = ", ".join(issue.get("reference", "-") for issue in issues[:8])
            excerpts = "; ".join(
                shorten_text(issue.get("excerpt", "No excerpt available."), 180) for issue in issues[:2]
            )
            suggested_action = issues[0].get("suggested_action") or THEME_ACTIONS.get(theme, THEME_ACTIONS["Other / Unclassified"])
            suggested_action = suggested_policy_action(theme, suggested_action)
            lines.extend(
                [
                    f"### {theme}",
                    f"- Issue: {theme}.",
                    f"- What is being reported: Applicant excerpts include: {excerpts or 'No excerpt available.'}",
                    f"- Why it matters: {why_theme_matters(theme)}",
                    f"- Evidence references: {refs or format_theme_refs(summary, theme)}.",
                    f"- Suggested action: {suggested_action}",
                    "",
                ]
            )

    lines.extend(
        [
            "## 3. Community Service Workload",
            "",
        ]
    )
    operational_order = [
        "OPF / Insurance / Compensation",
        "Passport / NADRA / Consular Services",
        "General Welfare / Guidance",
        "Nurses / Health Worker Welfare",
        "Labour / Salary / Employer Dispute",
    ]
    for theme in operational_order:
        count = counts.get(theme, 0)
        refs = format_theme_refs(summary, theme)
        status = status_line_for_theme(summary, theme)
        lines.append(f"- {theme}: {case_count_phrase(count)}. Sample references: {refs}. Status: {status}.")

    lines.extend(
        [
            "",
            "## 4. Staff / Operational Follow-up",
            "",
            f"- Named departments/desks in the export: {format_top_counts(summary.get('counts_by_assigned_department', {}), skip_unknown=True)}.",
            f"- Named officers/desks in the export: {format_top_counts(summary.get('counts_by_assigned_to', {}), skip_unknown=True)}.",
        ]
    )
    for theme, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
        if not count:
            continue
        status = status_line_for_theme(summary, theme)
        assigned = assigned_line_for_theme(summary, theme)
        lines.append(f"- {theme}: {status}; assigned to {assigned}.")

    lines.extend(
        [
            "",
            "## 5. Suggested Action Points",
            "",
            "- Prepare a short list of family/visit visa references for internal review.",
            "- Verify the KOC gate-pass report with the complainant/company before external engagement.",
            "- Ensure legal/detention cases are tracked by the legal desk until action is recorded.",
            "- Publish or prepare clearer OPF card guidance to reduce repeated queries.",
            "- Continue weekly export and offline pulse review.",
        ]
    )
    if top_diplomatic:
        lines.append(f"- For {top_diplomatic.get('theme')}, compile evidence references and seek official clarification only if the reported pattern is verified.")
    if counts.get("OPF / Insurance / Compensation", 0):
        lines.append("- Route OPF card and membership requests through the OPF or welfare focal point and track completion separately from legal matters.")
    if high_count:
        lines.append("- Review high-sensitivity cases first for evidence completeness and welfare risk; reserve urgent handling for detention, death, abuse, or immediate-risk cases.")
    lines.append("- Maintain separation between diplomatic issues and routine community service workload in staff reporting.")

    return "\n".join(lines).strip()


def add_note_after_title(markdown: str, note: str) -> str:
    if not note:
        return markdown
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "# Ambassador Pulse Brief":
        return "\n".join([lines[0], "", f"Note: {note}", *lines[1:]]).strip()
    return f"Note: {note}\n\n{markdown}".strip()


def known_references_by_theme(summary: Dict[str, Any]) -> Tuple[Dict[str, set], set]:
    refs_by_theme = {
        theme: set(refs)
        for theme, refs in (summary.get("sample_case_references_by_theme") or {}).items()
        if refs
    }
    all_refs = set()
    for refs in refs_by_theme.values():
        all_refs.update(refs)
    return refs_by_theme, all_refs


def has_cross_theme_evidence(text: str, summary: Dict[str, Any]) -> bool:
    refs_by_theme, all_refs = known_references_by_theme(summary)
    if not all_refs:
        return False

    lowered = text.lower()
    theme_positions: List[Tuple[int, str]] = []
    for theme in refs_by_theme:
        start = 0
        theme_lower = theme.lower()
        while True:
            pos = lowered.find(theme_lower, start)
            if pos == -1:
                break
            theme_positions.append((pos, theme))
            start = pos + len(theme_lower)

    if not theme_positions:
        return False

    theme_positions.sort()
    for index, (position, theme) in enumerate(theme_positions):
        next_theme_pos = theme_positions[index + 1][0] if index + 1 < len(theme_positions) else len(text)
        next_major_section = lowered.find("\n## 3.", position)
        if next_major_section == -1:
            next_major_section = lowered.find("\n## 3 ", position)
        end = min(value for value in (next_theme_pos, next_major_section, position + 2200, len(text)) if value != -1)
        section = text[position:end]
        cited_refs = {ref for ref in all_refs if ref in section}
        allowed_refs = refs_by_theme.get(theme, set())
        if any(ref not in allowed_refs for ref in cited_refs):
            return True
    return False


def _all_known_references(summary: Dict[str, Any]) -> set:
    refs: set = set()
    samples = summary.get("sample_case_references_by_theme") or {}
    for theme_refs in samples.values():
        refs.update(theme_refs or [])
    for issue in summary.get("historical_recurrence") or []:
        refs.update(issue.get("evidence_current_refs") or [])
        refs.update(issue.get("evidence_historical_refs") or [])
    for entity in summary.get("historical_entities") or []:
        refs.update(entity.get("current_refs") or [])
        refs.update(entity.get("historical_refs") or [])
    for issue in summary.get("high_sensitivity_issues") or []:
        ref = issue.get("reference")
        if ref:
            refs.add(ref)
    return refs


def _current_known_references(summary: Dict[str, Any]) -> set:
    refs: set = set()
    samples = summary.get("sample_case_references_by_theme") or {}
    for theme_refs in samples.values():
        refs.update(theme_refs or [])
    for issue in summary.get("historical_recurrence") or []:
        refs.update(issue.get("evidence_current_refs") or [])
    for entity in summary.get("historical_entities") or []:
        refs.update(entity.get("current_refs") or [])
    for issue in summary.get("high_sensitivity_issues") or []:
        ref = issue.get("reference")
        if ref:
            refs.add(ref)
    return refs


def _historical_only_references(summary: Dict[str, Any]) -> set:
    historical: set = set()
    for issue in summary.get("historical_recurrence") or []:
        historical.update(issue.get("evidence_historical_refs") or [])
    for entity in summary.get("historical_entities") or []:
        historical.update(entity.get("historical_refs") or [])
    return historical - _current_known_references(summary)


def _extract_referenced_codes(text: str) -> set:
    """Extract candidate reference codes from text (e.g. ABC-12345 or ROW-0001)."""
    return set(re.findall(r"\b[A-Z]{2,5}-\d{2,5}\b", text or ""))


def is_bad_ai_output(text: str, summary: Optional[Dict[str, Any]] = None) -> bool:
    normalized = (text or "").lower().replace("’", "'").strip()
    if not normalized:
        return True
    if normalized.startswith("okay"):
        return True
    if "# ambassador pulse brief" not in normalized[:800]:
        return True
    if any(phrase in normalized for phrase in BAD_AI_PHRASES):
        return True
    if summary and has_cross_theme_evidence(text, summary):
        return True
    if not summary:
        return False

    # Quality gate: report window must be mentioned when present.
    report_window = summary.get("report_window") or {}
    if report_window.get("start_date") and report_window.get("end_date"):
        if (
            report_window["start_date"] not in text
            and report_window["end_date"] not in text
        ):
            return True

    # Quality gate: historical recurrence section is required when non-empty.
    historical_recurrence = summary.get("historical_recurrence") or []
    if historical_recurrence and "repeated / emerging issues" not in normalized:
        return True

    # Quality gate: do not invent references not present anywhere in the summary.
    known_refs = _all_known_references(summary)
    referenced = _extract_referenced_codes(text)
    invented = {ref for ref in referenced if ref and ref not in known_refs and not ref.startswith("ROW-")}
    # Only fail when there's at least some known data and we see invented refs.
    if known_refs and invented:
        return True

    # Quality gate: historical-only references must not be cited as current evidence.
    historical_only_refs = _historical_only_references(summary)
    if historical_only_refs:
        # Look for current-evidence cues immediately preceding any historical-only ref.
        lowered = text.lower()
        for ref in historical_only_refs:
            for match in re.finditer(re.escape(ref), text):
                window_start = max(0, match.start() - 200)
                preceding = lowered[window_start: match.start()]
                if (
                    "current evidence" in preceding
                    or "current refs" in preceding
                    or "current-window" in preceding
                    or "current window" in preceding
                ):
                    return True

    # Quality gate: do not state an all-time count as current-window workload.
    total_current = summary.get("total_cases", 0)
    all_time_total = sum(
        (item.get("all_time_count", 0) for item in historical_recurrence), 0
    )
    if all_time_total and total_current and all_time_total != total_current:
        # Look for explicit phrasing tying all-time number to current week
        patterns = [
            rf"{all_time_total}\s+cases\s+(this|in the)\s+(current|report|reporting|week|window)",
            rf"current[- ]week[^.]{{0,80}}{all_time_total}\s+case",
            rf"this\s+(week|window)[^.]{{0,80}}{all_time_total}\s+case",
        ]
        for pattern in patterns:
            if re.search(pattern, normalized):
                return True

    # Quality gate: OPF must remain in operational workload when it is the top current workload.
    top_workload = summary.get("top_operational_workload") or {}
    if top_workload.get("theme") == "OPF / Insurance / Compensation":
        # Find the operational/community service workload section
        section_match = re.search(
            r"(community service workload|operational workload)(.+?)(?=\n##\s|$)",
            normalized,
            re.DOTALL,
        )
        if section_match and "opf" not in section_match.group(2):
            return True

    return False


def merge_ai_and_deterministic(
    brief_text: str,
    deterministic_text: str,
    source_note: str,
) -> str:
    lines = [
        brief_text.strip(),
        "",
        "---",
        "",
        "## Deterministic Audit Summary",
        "",
        "The following section is generated by local deterministic rules and should be treated as the source of truth for counts and theme samples.",
        "",
        deterministic_text.strip(),
    ]
    if source_note:
        lines.extend(["", "---", "", source_note])
    return "\n".join(lines).strip() + "\n"


def write_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def export_docx_with_pandoc(markdown_path: str, docx_path: str) -> Tuple[bool, str]:
    """Convert ``markdown_path`` to ``docx_path`` using Pandoc.

    Returns ``(success, message)``. If Pandoc is unavailable or fails,
    ``success`` is False and ``message`` describes what happened.
    """
    pandoc_bin = shutil.which("pandoc")
    if not pandoc_bin:
        return False, "DOCX export skipped because Pandoc is not available on this system."

    try:
        completed = subprocess.run(
            [pandoc_bin, markdown_path, "-o", docx_path],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return False, f"DOCX export skipped because Pandoc failed to launch: {exc}"

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        return (
            False,
            f"DOCX export skipped because Pandoc exited with code "
            f"{completed.returncode}: {stderr or 'no error output'}",
        )

    if not os.path.exists(docx_path):
        return False, "DOCX export skipped because Pandoc reported success but no file was produced."

    return True, f"Word report saved to: {docx_path}"


def main() -> int:
    args = parse_args()
    if args.days <= 0:
        print("Error: --days must be a positive integer.", file=sys.stderr)
        return 2

    input_path = resolve_path(args.input)
    report_path = os.path.join(script_dir(), REPORT_FILE)
    summary_path = os.path.join(script_dir(), SUMMARY_FILE)
    docx_path = os.path.join(script_dir(), DOCX_FILE)

    try:
        rows, headers = read_cases(input_path)
        all_cases = build_enriched_cases(rows)

        start_date, end_date, warnings, has_valid_dates = determine_report_window(
            all_cases, args.days, args.end_date
        )
        buckets = split_cases_by_window(all_cases, start_date, end_date, has_valid_dates)
        report_cases = buckets["report_cases"]
        historical_cases = buckets["historical_cases"]
        future_cases = buckets["future_cases"]
        undated_cases = buckets["undated_cases"]

        dated_rows = sum(1 for case in all_cases if case_created_date(case) is not None)
        undated_rows = len(all_cases) - dated_rows

        summary = build_summary(report_cases, args.days)

        summary["report_window"] = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "days": args.days,
        }
        summary["input_dataset"] = {
            "total_rows": len(all_cases),
            "dated_rows": dated_rows,
            "undated_rows": undated_rows,
            "historical_rows_before_window": len(historical_cases),
            "report_window_rows": len(report_cases),
            "future_rows_after_window": len(future_cases),
            "warnings": list(warnings),
        }
        summary["historical_recurrence"] = analyze_historical_recurrence(
            report_cases, historical_cases, all_cases
        )
        summary["historical_entities"] = analyze_historical_entities(
            report_cases, historical_cases, all_cases
        )

        output_summary = dict(summary)
        output_summary["input_file"] = input_path
        output_summary["csv_headers"] = headers
        output_summary["cases"] = report_cases
        output_summary["all_cases_count"] = len(all_cases)
        output_summary["historical_cases_count"] = len(historical_cases)
        output_summary["future_cases_count"] = len(future_cases)
        output_summary["undated_cases_count"] = len(undated_cases)

        write_json(summary_path, output_summary)

        deterministic_text = deterministic_markdown(summary)
        source_note = "Briefing source: deterministic fallback used because --no-ai was selected."
        brief_text = build_deterministic_brief(summary)

        if not args.no_ai:
            try:
                prompt = build_prompt(build_ai_payload(summary, report_cases))
                ai_text = call_ollama(prompt, args.model)
                if is_bad_ai_output(ai_text, summary):
                    rejection_note = (
                        "AI output was rejected by the quality gate; deterministic fallback briefing used."
                    )
                    brief_text = add_note_after_title(build_deterministic_brief(summary), rejection_note)
                    source_note = rejection_note
                else:
                    brief_text = ai_text
                    source_note = f"AI drafting source: local Ollama model `{args.model}` at `{OLLAMA_URL}`."
            except RuntimeError as exc:
                fallback_note = f"AI drafting failed: {exc}\n\nDeterministic fallback briefing used."
                print(f"Warning: {fallback_note}", file=sys.stderr)
                brief_text = add_note_after_title(build_deterministic_brief(summary), fallback_note)
                source_note = "Briefing source: deterministic fallback used because local AI drafting failed."

        report_text = merge_ai_and_deterministic(brief_text, deterministic_text, source_note)
        write_text(report_path, report_text)

        docx_message: Optional[str] = None
        docx_success = False
        if args.docx:
            docx_success, docx_message = export_docx_with_pandoc(report_path, docx_path)
            if not docx_success:
                print(f"Warning: {docx_message}", file=sys.stderr)

    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except (csv.Error, UnicodeDecodeError, ValueError) as exc:
        print(f"Error reading CSV: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Error writing output files: {exc}", file=sys.stderr)
        return 1

    ai_status = "AI drafting skipped (--no-ai)." if args.no_ai else source_note
    print("Ambassador Pulse Offline report generated.")
    print(ai_status)
    print(f"Markdown report saved to: {report_path}")
    print(f"Summary JSON saved to: {summary_path}")
    if args.docx:
        if docx_success and docx_message:
            print(docx_message)
        elif docx_message:
            print(docx_message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
