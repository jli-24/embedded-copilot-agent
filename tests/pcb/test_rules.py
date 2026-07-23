from embedded_copilot.pcb.models import PCBRequirement
from embedded_copilot.pcb.rules import PCBRuleEngine


def test_rule_engine_is_deterministic_side_effect_free_and_has_stable_ids() -> None:
    requirement = PCBRequirement(
        project_name="demo",
        platform="ESP32",
        components=[
            "MCU",
            "Communication",
            "High-speed signal",
            "Analog",
        ],
        interfaces=["SPI", "UART", "I2C", "ADC"],
    )
    original = requirement.model_dump(mode="json")
    engine = PCBRuleEngine()

    first = engine.evaluate(requirement)
    second = engine.evaluate(requirement)

    assert first == second
    assert [issue.id for issue in first.issues] == [
        "pcb-power-declaration",
        "pcb-power-decoupling",
        "pcb-clock-high-speed",
        "pcb-analog-isolation",
        "pcb-communication-spi",
        "pcb-communication-uart",
        "pcb-communication-i2c",
        "pcb-ground-integrity",
    ]
    assert len({issue.id for issue in first.issues}) == len(first.issues)
    assert requirement.model_dump(mode="json") == original


def test_power_and_ground_rules_pass_only_with_declared_evidence() -> None:
    requirement = PCBRequirement(
        project_name="power_board",
        components=["Power", "MCU"],
        constraints=[
            "Decoupling strategy is declared for the power stage.",
            "Continuous GND plane integrity is declared.",
        ],
    )

    evaluation = PCBRuleEngine().evaluate(requirement)

    assert evaluation.issues == []
    assert evaluation.passed_rules == [
        "pcb-power-declaration",
        "pcb-power-decoupling",
        "pcb-ground-integrity",
    ]


def test_clock_analog_and_communication_rules_pass_with_explicit_evidence() -> None:
    requirement = PCBRequirement(
        project_name="reviewed_board",
        components=["Power", "High-speed signal", "Analog", "Communication"],
        interfaces=["SPI", "UART", "I2C", "ADC"],
        constraints=[
            "Decoupling is declared.",
            "Clock routing and return path are reviewed.",
            "ADC noise isolation and filter placement are reviewed.",
            "SPI layout is reviewed.",
            "UART routing is reviewed.",
            "I2C pull-ups and routing are reviewed.",
            "GND plane integrity is reviewed.",
        ],
    )

    evaluation = PCBRuleEngine().evaluate(requirement)

    assert evaluation.issues == []
    assert evaluation.passed_rules == [
        "pcb-power-declaration",
        "pcb-power-decoupling",
        "pcb-clock-high-speed",
        "pcb-analog-isolation",
        "pcb-communication-spi",
        "pcb-communication-uart",
        "pcb-communication-i2c",
        "pcb-ground-integrity",
    ]


def test_non_applicable_rules_are_not_reported_as_passed() -> None:
    evaluation = PCBRuleEngine().evaluate(
        PCBRequirement(
            project_name="minimal",
            components=["Power"],
            constraints=["Decoupling and GND plane integrity are declared."],
        )
    )

    assert "pcb-clock-high-speed" not in evaluation.passed_rules
    assert "pcb-analog-isolation" not in evaluation.passed_rules
    assert not any("communication" in rule for rule in evaluation.passed_rules)
