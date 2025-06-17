import re


class LogSanitizer:
    _timestamp_pattern = re.compile(
        r'^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\]\s?',
        re.MULTILINE
    )
    _jenkins_pipeline_annotation = re.compile(
        r'\x1B\[8mha:////[a-zA-Z0-9+/=]+?\x1B\[0m'
    )
    _ansi_escape_pattern = re.compile(
        r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])'
    )

    _keyword_mappings = {
        "[GitCheckoutListener]": "[GIT_LISTENER]",
        "[Pipeline]": "[PIPE]",
        "[Gitea]": "[GITEA]"
    }

    def run(self, raw_log: str) -> str:
        processed_log = raw_log

        for key, value in self._keyword_mappings.items():
            processed_log = processed_log.replace(key, value)

        processed_log = self._timestamp_pattern.sub("", processed_log)
        processed_log = self._jenkins_pipeline_annotation.sub("", processed_log)
        processed_log = self._ansi_escape_pattern.sub("", processed_log)

        return processed_log.strip()