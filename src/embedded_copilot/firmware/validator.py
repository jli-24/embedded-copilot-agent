from __future__ import annotations

from embedded_copilot.firmware.models import GeneratedCode, ValidationResult


class FirmwareValidator:
    """Static structural validation for mock generated projects."""

    def validate(self, generated: GeneratedCode) -> ValidationResult:
        errors: list[str] = []
        if not generated.files:
            errors.append("generated project has no files")

        filenames: set[str] = set()
        has_main = False
        for generated_file in generated.files:
            filename_key = generated_file.filename.casefold()
            if filename_key in filenames:
                errors.append(f"duplicate filename: {generated_file.filename}")
            filenames.add(filename_key)
            if not generated_file.content:
                errors.append(f"empty file content: {generated_file.filename}")
            normalized_path = generated_file.filename.replace("\\", "/")
            stem = normalized_path.rsplit("/", maxsplit=1)[-1].rsplit(".", maxsplit=1)[0]
            if stem.casefold() == "main":
                has_main = True

        if generated.files and not has_main:
            errors.append("generated project has no main file")

        return ValidationResult(
            success=not errors,
            errors=errors,
            metadata={"file_count": len(generated.files)},
        )
