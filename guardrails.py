"""
Guardrails for the HR/IT helpdesk agent.

1. detect_prompt_injection(text)  -> blocks attempts to override the bot's rules
2. redact_pii(text)               -> masks phone, PAN, Aadhaar, card numbers and personal emails
3. keyword_scope_check(text)      -> fast check whether a question is about HR or IT

The agent also uses an LLM classifier for scope (see agent.py); the keyword check
here is the cheap first pass, so most HR/IT questions never need that extra call.
"""

import re

# ---------------------------------------------------------------------------
# 1. Prompt-injection detection
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override|bypass|skip)\b.{0,40}\b(previous|prior|above|earlier|all|your|the|system|these)\b.{0,30}\b(instructions?|rules?|prompts?|guidelines?|polic(y|ies)|restrictions?)",
    r"\b(reveal|show|print|repeat|display|leak|tell me)\b.{0,40}\b(system prompt|hidden prompt|initial prompt|your (instructions|prompt|rules))",
    r"\byou are (now|no longer)\b",
    r"\b(act|behave|pretend|roleplay)\b.{0,20}\b(as|like|to be)\b.{0,40}\b(admin|administrator|developer|root|unrestricted|dan|jailbroken|different (ai|assistant|bot))",
    r"\b(developer|god|admin|debug|sudo|jailbreak|dan)\s+mode\b",
    r"\bnew (instructions|rules|system prompt)\s*:",
    r"</?\s*(system|assistant|instructions?)\s*>",
    r"\[\s*(system|inst)\s*\]",
    r"\bdo anything now\b",
    r"\bi am (the|an?) (admin|administrator|hr manager|ceo|developer)\b.{0,60}\b(give|show|access|all employees|every employee)",
    r"\b(all|every|other) employees?'?s?\b.{0,40}\b(phone|pan|aadhaar|salary|personal|data|details|records?)",
    r"\bselect\s+\*\s+from\b|\bdrop\s+table\b|\bunion\s+select\b|;\s*--",
]
_INJECTION_REGEX = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION_PATTERNS]


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Return (True, matched_text) if the message looks like a prompt-injection attempt."""
    for regex in _INJECTION_REGEX:
        match = regex.search(text or "")
        if match:
            return True, match.group(0)
    return False, None


# ---------------------------------------------------------------------------
# 2. PII redaction
# ---------------------------------------------------------------------------

# Shared helpdesk inboxes from the policies are not personal data, so keep them.
_ALLOWED_EMAILS = {
    "hr-helpdesk@goaified-demo.in",
    "it-helpdesk@goaified-demo.in",
    "finance-helpdesk@goaified-demo.in",
}

_PII_PATTERNS = [
    # (label, regex) - order matters: longer number patterns before shorter ones
    ("CARD", re.compile(r"\b(?:\d[ -]?){15}\d\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PHONE", re.compile(r"(?<!\w)(?:\+91[ -]?|0)?[6-9]\d{4}[ -]?\d{5}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
]
_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Mask PII in text. Returns (redacted_text, list_of_pii_types_found)."""
    if not text:
        return text, []
    found = []

    def _email_sub(m: re.Match) -> str:
        if m.group(0).lower() in _ALLOWED_EMAILS:
            return m.group(0)
        found.append("EMAIL")
        return "[REDACTED_EMAIL]"

    text = _EMAIL_REGEX.sub(_email_sub, text)

    for label, regex in _PII_PATTERNS:
        text, n = regex.subn(f"[REDACTED_{label}]", text)
        if n:
            found.append(label)

    return text, sorted(set(found))


# ---------------------------------------------------------------------------
# 3. Topic / scope check
# ---------------------------------------------------------------------------

_HR_IT_KEYWORDS = [
    # HR
    "leave", "leaves", "holiday", "vacation", "sick", "casual", "earned", "maternity",
    "paternity", "bereavement", "lwp", "wfh", "work from home", "remote", "hr",
    "manager", "reimburse", "reimbursement", "expense", "claim", "travel", "allowance",
    "policy", "policies", "joining", "designation", "department", "profile", "payroll",
    "attendance", "carry forward", "medical certificate",
    # IT
    "password", "login", "log in", "locked", "lockout", "mfa", "2fa", "authenticator",
    "vpn", "wifi", "wi-fi", "network", "laptop", "computer", "monitor", "mouse",
    "headset", "hardware", "software", "install", "ticket", "tickets", "it helpdesk",
    "email", "outlook", "portal", "access", "printer", "device", "battery",
]
_KEYWORD_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _HR_IT_KEYWORDS) + r")\b", re.IGNORECASE
)


def keyword_scope_check(text: str) -> bool:
    """True if the message clearly mentions an HR or IT topic.
    False means "not sure" - the agent then asks the LLM to classify it."""
    return bool(_KEYWORD_REGEX.search(text or ""))


REFUSAL_OUT_OF_SCOPE = (
    "I can only help with HR and IT questions, such as leave, work from home, "
    "expenses, passwords, VPN, laptops and IT tickets. Please ask me something in those areas."
)
REFUSAL_INJECTION = (
    "I can't follow that request. I'm the HR/IT helpdesk assistant and I only answer "
    "HR and IT questions using company policies and your own employee records."
)
