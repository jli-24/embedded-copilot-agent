from __future__ import annotations


class FirmwareLexError(ValueError):
    """Raised when bounded lexical masking cannot safely continue."""


def mask_non_code(text: str) -> str:
    """Mask comments and literals while preserving offsets and line numbers."""
    output = list(text)
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if char == "/" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "line_comment"
                continue
            if char == "/" and next_char == "*":
                output[index] = output[index + 1] = " "
                index += 2
                state = "block_comment"
                continue
            if char == '"':
                output[index] = " "
                state = "string"
            elif char == "'":
                output[index] = " "
                state = "character"
        elif state == "line_comment":
            if char == "\n":
                state = "code"
            else:
                output[index] = " "
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                output[index] = output[index + 1] = " "
                index += 2
                state = "code"
                continue
            if char != "\n":
                output[index] = " "
        elif state in {"string", "character"}:
            terminator = '"' if state == "string" else "'"
            if char == "\\":
                output[index] = " "
                if index + 1 < len(text):
                    if text[index + 1] != "\n":
                        output[index + 1] = " "
                    index += 2
                    continue
            elif char == terminator:
                output[index] = " "
                state = "code"
            elif char == "\n":
                raise FirmwareLexError("Firmware literal is unterminated")
            else:
                output[index] = " "
        index += 1
    if state in {"block_comment", "string", "character"}:
        raise FirmwareLexError("Firmware lexical structure is incomplete")
    masked = "".join(output)
    _validate_braces(masked)
    return masked


def _validate_braces(text: str) -> None:
    depth = 0
    for char in text:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth < 0:
                raise FirmwareLexError("Firmware braces are unbalanced")
    if depth:
        raise FirmwareLexError("Firmware braces are unbalanced")
