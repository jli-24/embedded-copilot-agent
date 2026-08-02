"""Narrow facade for Engineering Artifacts."""

from __future__ import annotations

from embedded_copilot.engineering_artifacts.contracts import EngineeringArtifactPort


class EngineeringArtifactRuntime:
    __slots__ = ("__port",)

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise TypeError("use create_engineering_artifact_runtime")

    @classmethod
    def _compose(cls, port: EngineeringArtifactPort) -> EngineeringArtifactRuntime:
        runtime = object.__new__(cls)
        runtime.__port = port
        return runtime

    def engineering_artifact_port(self) -> EngineeringArtifactPort:
        return self.__port
