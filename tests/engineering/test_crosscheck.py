from __future__ import annotations

from embedded_copilot.datasheet.models import DatasheetPin
from embedded_copilot.engineering.crosscheck import cross_check

from tests.engineering.fixtures import datasheet_model, firmware_review


def test_crosscheck_reports_only_exact_datasheet_firmware_gpio_conflict() -> None:
    findings = cross_check(datasheet_model(), firmware_review())

    assert len(findings) == 1
    assert findings[0].rule_id == "datasheet-firmware-gpio-conflict"
    assert findings[0].severity == "high"
    assert "GPIO8" in findings[0].description
    assert findings[0].source_ids == (
        "attachment:datasheet-1",
        "attachment:source-1#line:7",
    )


def test_crosscheck_does_not_guess_unknown_aliases() -> None:
    review = firmware_review().model_copy(
        update={
            "gpio_assignments": (
                firmware_review().gpio_assignments[0].model_copy(
                    update={"pin": "GPIO404"}
                ),
            )
        }
    )

    assert cross_check(datasheet_model(), review) == ()


def test_crosscheck_does_not_treat_package_number_as_gpio_number() -> None:
    review = firmware_review().model_copy(
        update={
            "gpio_assignments": (
                firmware_review().gpio_assignments[0].model_copy(
                    update={"pin": "GPIO12"}
                ),
            )
        }
    )

    assert cross_check(datasheet_model(), review) == ()


def test_crosscheck_keeps_three_way_alias_collision_ambiguous() -> None:
    datasheet = datasheet_model().model_copy(
        update={
            "pins": tuple(
                DatasheetPin(
                    number=str(number),
                    name=name,
                    type="alternate",
                    description="Reserved fixed Flash function",
                )
                for number, name in ((1, "GPIO8"), (2, "IO8"), (3, "GPIO08"))
            ),
            "interfaces": (),
        }
    )

    assert cross_check(datasheet, firmware_review()) == ()


def test_crosscheck_requires_alias_to_be_unique_across_all_datasheet_pins() -> None:
    datasheet = datasheet_model().model_copy(
        update={
            "pins": (
                DatasheetPin(
                    number="12",
                    name="GPIO8",
                    type="power",
                    description="Reserved fixed Flash function",
                ),
                DatasheetPin(
                    number="13",
                    name="IO8",
                    type="alternate",
                    description="General-purpose alternate function",
                ),
            ),
            "interfaces": (),
        }
    )

    assert cross_check(datasheet, firmware_review()) == ()
