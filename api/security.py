import re


CONTROL_CHARACTER_PATTERN = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]"
)

PROMPT_CONTROL_PATTERNS = (
    re.compile(
        r"\b(?:ignore|disregard|override|bypass)\b"
        r".{0,40}"
        r"\b(?:instructions?|rules?|prompts?|messages?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:reveal|show|print|repeat|return)\b"
        r".{0,40}"
        r"\b(?:system|developer)\b"
        r".{0,20}"
        r"\b(?:prompts?|messages?|instructions?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:<|\[)\s*"
        r"(?:system|developer|assistant)"
        r"\s*(?:>|\])",
        re.IGNORECASE,
    ),
)


def validate_question_security(question: str) -> str:
    """Reject explicit prompt-control and unsafe input patterns."""

    if CONTROL_CHARACTER_PATTERN.search(question):
        raise ValueError(
            "Question contains unsupported control characters."
        )

    if any(
        pattern.search(question)
        for pattern in PROMPT_CONTROL_PATTERNS
    ):
        raise ValueError(
            "Question contains prohibited prompt-control "
            "instructions."
        )

    return question

COMPLIANCE_SCOPE_PATTERN = re.compile(
    r"\b(?:"
    r"access|accounts?|administrative|alerts?|"
    r"anti[- ]?malware|assets?|audit|authentication|"
    r"authorization|backups?|browsers?|cis|compliance|"
    r"configurations?|controls?|data|devices?|dhcp|dns|"
    r"domains?|email|encryption|firewalls?|identity|"
    r"incidents?|intrusion|inventory|logs?|malware|"
    r"network|passwords?|patch(?:es|ing)?|penetration|"
    r"phishing|polic(?:y|ies)|remediation|retention|"
    r"routers?|safeguards?|secure|security|segmentation|"
    r"sensitive|service\s+providers?|software|storage|"
    r"suppliers?|training|vulnerabilit(?:y|ies)|vpn|"
    r"websites?|workforce"
    r")\b",
    re.IGNORECASE,
)

OUT_OF_SCOPE_RESPONSE = (
    "Insufficient compliance data found."
)


def is_compliance_question(question: str) -> bool:
    """Return whether a question has a compliance-domain signal."""

    return COMPLIANCE_SCOPE_PATTERN.search(question) is not None