import re
import logging
from typing import Dict, List, Pattern, Tuple

logger = logging.getLogger(__name__)


class CredentialMapper:
    def __init__(self):
        self.mappings: Dict[str, List[str]] = {}
        self.reverse_mappings: Dict[str, str] = {}

    def add_mapping(self, category: str, value: str) -> str:
        if value in self.reverse_mappings:
            return self.reverse_mappings[value]

        if category not in self.mappings:
            self.mappings[category] = []

        self.mappings[category].append(value)
        index = len(self.mappings[category])
        placeholder = f"[{category.upper()}_{index}]"

        self.reverse_mappings[value] = placeholder
        return placeholder

    def rehydrate_text(self, text: str) -> str:
        sorted_placeholders = sorted(
            self.reverse_mappings.items(),
            key=lambda item: len(item[1]),
            reverse=True
        )

        for original_value, placeholder in sorted_placeholders:
            text = text.replace(placeholder, original_value)
        return text


class ContentSanitizer:
    def __init__(self):
        self.removal_patterns: List[Pattern] = [
            re.compile(r'^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\]\s?', re.MULTILINE),
        ]

        self.mapping_patterns: List[Tuple[str, Pattern]] = [
            # Private Keys
            ("RSA_PRIVATE_KEY", re.compile(r'-----BEGIN RSA PRIVATE KEY-----(?:.|\n)+?-----END RSA PRIVATE KEY-----')),
            ("SSH_PRIVATE_KEY",
             re.compile(r'-----BEGIN OPENSSH PRIVATE KEY-----(?:.|\n)+?-----END OPENSSH PRIVATE KEY-----')),

            # Jenkins & Log Formatting
            ("JENKINS_ANNOTATION", re.compile(r'\x1B\[8mha:////[a-zA-Z0-9+/=]+?\x1B\[0m')),
            ("ANSI_ESCAPE_CODE", re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')),

            # JWT Tokens
            ("JWT_TOKEN", re.compile(r'ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.[A-Za-z0-9-_.+/=]*')),

            # Common Service Tokens
            ("GITHUB_TOKEN", re.compile(r'\bghp_[0-9a-zA-Z]{36}\b')),
            ("SLACK_TOKEN", re.compile(r'\bxox[baprs]-[0-9a-zA-Z-]+\b')),
            ("STRIPE_API_KEY", re.compile(r'\bsk_live_[0-9a-zA-Z]{24}\b')),
            ("TWILIO_API_KEY", re.compile(r'\bSK[0-9a-fA-F]{32}\b')),

            # Cloud Provider Credentials
            ("GOOGLE_API_KEY", re.compile(r'\bAIza[0-9A-Za-z-_]{35}\b')),
            ("GOOGLE_OAUTH_TOKEN", re.compile(r'\bya29\.[0-9A-Za-z-_]+\b')),
            ("AWS_ACCESS_KEY_ID", re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
            ("AWS_SECRET_ACCESS_KEY", re.compile(r'\b[0-9a-zA-Z/+]{40}\b')),

            # Generic High-Entropy Strings & Secrets
            ("HEX_KEY_64", re.compile(r'\b[0-9a-fA-F]{64}\b')),
            ("HEX_KEY_40", re.compile(r'\b[0-9a-fA-F]{40}\b')),
            ("BASE64_KEY_32_PLUS", re.compile(r'\b[A-Za-z0-9+/=]{32,}\b')),
        ]

    def sanitize(self, text: str, mapper: CredentialMapper) -> str:
        sanitized_text = text

        for pattern in self.removal_patterns:
            sanitized_text = pattern.sub("", sanitized_text)

        for category, pattern in self.mapping_patterns:
            def replacement_function(match):
                matched_value = match.group(0)
                return mapper.add_mapping(category, matched_value)

            sanitized_text = pattern.sub(replacement_function, sanitized_text)

        return sanitized_text
