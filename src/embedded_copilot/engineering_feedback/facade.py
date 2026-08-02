"""Minimal Engineering Feedback facade."""

from __future__ import annotations

from embedded_copilot.engineering_feedback.contracts import EngineeringFeedbackPort


class EngineeringFeedbackRuntime:
    __slots__ = ("__port",)

    def __init__(self, port: EngineeringFeedbackPort) -> None:
        self.__port = port

    def engineering_feedback_port(self) -> EngineeringFeedbackPort:
        return self.__port
