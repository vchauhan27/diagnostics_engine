import json
import re
from dataclasses import dataclass, field
from enum import Enum

# ============================================================
# REGEX PATTERNS — one per FailureInput field
# ============================================================

TESTCASE_PATTERN    = re.compile(r"Test Case ID\s*:\s*(.*)")
PRODUCT_PATTERN     = re.compile(r"Product Name\s*:\s*(.*)")
BUILD_VERSION_PATTERN = re.compile(r"Build Version\s*:\s*(.*)")
ENVIRONMENT_PATTERN = re.compile(r"^Environment\s*:\s*(.*)")
FAILED_STEP_PATTERN = re.compile(r"FAILED at step '(.*?)'")
COMPONENT_PATTERN   = re.compile(r"\bat\s+([\w\.]+)\.")
EXCEPTION_PATTERN   = re.compile(r"(\w+(?:Exception|Error))(?::\s*(.*))?")


# ============================================================
# PARSER STATES
# ============================================================

class ParserState(Enum):
    NORMAL      = "normal"
    EXCEPTION   = "exception"
    STACK_TRACE = "stack_trace"


# ============================================================
# OUTPUT DATA MODEL — matches FailureInput in agents.py exactly
# ============================================================

@dataclass
class ParsedFailure:
    """
    Fields map 1-to-1 with agents.FailureInput.
    All values are extracted directly from the log — nothing is hardcoded.
    """
    test_case_id:  str | None = None
    product_name:  str | None = None
    build_version: str | None = None
    environment:   str | None = None
    error_type:    str | None = None
    error_message: str | None = None
    component:     str | None = None   # first package prefix from stack trace
    stack_trace:   str | None = None   # full stack trace as a single string
    total_log_lines: int = 0

    # Internal accumulator — not part of the final output
    _stack_lines: list = field(default_factory=list, repr=False)

    def to_failure_input_dict(self) -> dict:
        """Return only the fields required by FailureInput."""
        return {
            "test_case_id":  self.test_case_id  or "UNKNOWN",
            "product_name":  self.product_name  or "Unknown Product",
            "build_version": self.build_version or "Unknown Build",
            "environment":   self.environment   or "Unknown",
            "error_type":    self.error_type    or "UnknownError",
            "error_message": self.error_message or "No error message captured",
            "component":     self.component     or "Unknown Component",
            "stack_trace":   self.stack_trace   or "No stack trace captured",
        }

    def to_json(self) -> str:
        return json.dumps(self.to_failure_input_dict(), indent=4)


# ============================================================
# FAILURE PARSER
# ============================================================

class FailureParser:
    def __init__(self):
        self.state = ParserState.NORMAL

    def parse(self, path: str) -> ParsedFailure:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        return self._parse_lines(lines)
        
    def parse_text(self, text: str) -> ParsedFailure:
        lines = text.splitlines()
        return self._parse_lines(lines)

    def _parse_lines(self, lines: list[str]) -> ParsedFailure:
        result = ParsedFailure()
        result.total_log_lines = len(lines)

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # -- Extract header metadata (runs on every line cheaply) --
            self._extract_metadata(line, result)
            self._extract_failed_step(line, result)

            # -- State machine for exception + stack trace --
            if self.state == ParserState.NORMAL:
                self.state = self._handle_normal(line, result)
            elif self.state == ParserState.EXCEPTION:
                self.state = self._handle_exception(line, result)
            elif self.state == ParserState.STACK_TRACE:
                self.state = self._handle_stack_trace(line, result)

        # Finalise stack_trace as a single string
        if result._stack_lines:
            result.stack_trace = "\n".join(result._stack_lines)

        return result

    # ========================================================
    # STATE HANDLERS
    # ========================================================

    def _handle_normal(self, line: str, result: ParsedFailure) -> ParserState:
        match = EXCEPTION_PATTERN.search(line)
        if not match:
            return ParserState.NORMAL

        result.error_type = match.group(1)

        if match.group(2):
            result.error_message = match.group(2).strip()
            if " at " in line:
                frame = line[line.index(" at "):].strip()
                result._stack_lines.append(frame)
            return ParserState.STACK_TRACE

        return ParserState.EXCEPTION

    def _handle_exception(self, line: str, result: ParsedFailure) -> ParserState:
        if " at " in line:
            frame = line[line.index(" at "):].strip()
            result._stack_lines.append(frame)
            return ParserState.STACK_TRACE

        result.error_message = line
        return ParserState.STACK_TRACE

    def _handle_stack_trace(self, line: str, result: ParsedFailure) -> ParserState:
        if " at " in line:
            frame = line[line.index(" at "):].strip()
            result._stack_lines.append(frame)

            # Capture the first meaningful package prefix as the component
            if result.component is None:
                pkg_match = COMPONENT_PATTERN.search(frame)
                if pkg_match:
                    result.component = pkg_match.group(1)

            return ParserState.STACK_TRACE

        return ParserState.NORMAL

    # ========================================================
    # METADATA EXTRACTORS
    # ========================================================

    def _extract_metadata(self, line: str, result: ParsedFailure):
        if result.test_case_id is None:
            m = TESTCASE_PATTERN.search(line)
            if m:
                result.test_case_id = m.group(1).strip()

        if result.product_name is None:
            m = PRODUCT_PATTERN.search(line)
            if m:
                result.product_name = m.group(1).strip()

        if result.build_version is None:
            m = BUILD_VERSION_PATTERN.search(line)
            if m:
                result.build_version = m.group(1).strip()

        if result.environment is None:
            m = ENVIRONMENT_PATTERN.search(line)
            if m:
                result.environment = m.group(1).strip()

    def _extract_failed_step(self, line: str, result: ParsedFailure):
        """Use the failing step as a fallback component when stack trace is absent."""
        m = FAILED_STEP_PATTERN.search(line)
        if m and result.component is None:
            result.component = m.group(1)


# ============================================================
# MAIN — quick sanity check
# ============================================================

if __name__ == "__main__":
    import os
    log_path = os.path.join(os.path.dirname(__file__), "sample.log")
    parsed = FailureParser().parse(log_path)
    print(parsed.to_json())