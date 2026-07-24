from __future__ import annotations

import os
import re
import stat
from collections.abc import Iterable
from pathlib import Path

from pydantic import ValidationError

from embedded_copilot.input.models import AttachmentType, UserAttachment
from embedded_copilot.pcb.exceptions import PCBParseError
from embedded_copilot.pcb.models import (
    PCBComponent,
    PCBLayer,
    PCBNet,
    PCBNetNode,
    PCBNetType,
    PCBPin,
    PCBPosition,
    PCBTrack,
    PCBVia,
    PCBZone,
    UnifiedPCBModel,
)
from embedded_copilot.pcb.parser.base import PCBSourceResolver
from embedded_copilot.pcb.parser.models import PCBParserLimits, SExpression


DEFAULT_MAX_PCB_SIZE_BYTES = 25 * 1024 * 1024
_POWER_NET = re.compile(
    r"^(?:\+?\d+(?:V\d+)?|VCC|VDD|VBAT|VBUS|VIN|VOUT|PWR)(?:[_-].*)?$",
    re.IGNORECASE,
)
_GROUND_NET = re.compile(r"^(?:GND|AGND|DGND|PGND|VSS)(?:[_-].*)?$", re.IGNORECASE)
_CLOCK_NET = re.compile(r"(?:CLK|CLOCK|XTAL|OSC)", re.IGNORECASE)


class KiCadPCBParser:
    """Parse a bounded KiCad board subset into one immutable exchange model."""

    def __init__(
        self,
        resolver: PCBSourceResolver,
        *,
        max_size_bytes: int = DEFAULT_MAX_PCB_SIZE_BYTES,
    ) -> None:
        if not isinstance(resolver, PCBSourceResolver):
            raise PCBParseError("PCB source resolver is invalid")
        if (
            isinstance(max_size_bytes, bool)
            or not isinstance(max_size_bytes, int)
            or max_size_bytes <= 0
        ):
            raise PCBParseError("PCB parser size limit is invalid")
        self._resolver = resolver
        self._max_size_bytes = max_size_bytes
        self._limits = PCBParserLimits()

    def parse(self, attachment: UserAttachment) -> UnifiedPCBModel:
        try:
            raw = self._read_source(attachment)
            text = raw.decode("utf-8", errors="strict")
            if "\x00" in text:
                raise ValueError("NUL is forbidden")
            root = _parse_s_expression(text, self._limits)
            return _extract_board(root, attachment.filename)
        except PCBParseError:
            raise
        except (UnicodeError, ValueError, TypeError, ValidationError, OSError):
            raise PCBParseError("KiCad PCB parsing failed") from None

    def _read_source(self, attachment: UserAttachment) -> bytes:
        if (
            not isinstance(attachment, UserAttachment)
            or attachment.media_type is not AttachmentType.EDA
            or Path(attachment.filename).suffix.casefold() != ".kicad_pcb"
            or attachment.content_type != "application/x-kicad-pcb"
            or attachment.metadata.get("format") != "kicad_pcb"
        ):
            raise PCBParseError("PCB attachment is unsupported")
        try:
            root = Path(self._resolver.root)
            if root.is_symlink() or not root.is_dir():
                raise ValueError("invalid root")
            trusted_root = root.resolve(strict=True)
            candidate = Path(self._resolver.resolve(attachment))
            if not candidate.is_absolute() or candidate.name != attachment.filename:
                raise ValueError("invalid target")
            if not candidate.is_relative_to(trusted_root):
                raise ValueError("target escaped root")

            cursor = trusted_root
            relative = candidate.relative_to(trusted_root)
            for part in relative.parts:
                cursor = cursor / part
                if cursor.is_symlink():
                    raise ValueError("symlink is forbidden")
                cursor.lstat()

            resolved = candidate.resolve(strict=True)
            if not resolved.is_relative_to(trusted_root):
                raise ValueError("target escaped root")
            file_stat = resolved.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(file_stat.st_mode)
                or file_stat.st_size != attachment.size_bytes
                or file_stat.st_size <= 0
                or file_stat.st_size > self._max_size_bytes
            ):
                raise ValueError("invalid source size")

            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(resolved, flags)
            try:
                opened_stat = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(opened_stat.st_mode)
                    or opened_stat.st_size != file_stat.st_size
                ):
                    raise ValueError("source changed")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = os.read(descriptor, min(64 * 1024, self._max_size_bytes + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > self._max_size_bytes:
                        raise ValueError("source is too large")
                    chunks.append(chunk)
                if total != file_stat.st_size:
                    raise ValueError("source changed")
                return b"".join(chunks)
            finally:
                os.close(descriptor)
        except PCBParseError:
            raise
        except Exception:
            raise PCBParseError("PCB source validation failed") from None


def _tokenize(text: str, limits: PCBParserLimits) -> list[str]:
    tokens: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        character = text[index]
        if character.isspace():
            index += 1
            continue
        if character in "()":
            tokens.append(character)
            index += 1
        elif character == '"':
            index += 1
            value: list[str] = []
            while index < length:
                character = text[index]
                if character == '"':
                    index += 1
                    break
                if character == "\\":
                    index += 1
                    if index >= length:
                        raise ValueError("unterminated escape")
                    escaped = text[index]
                    value.append({"n": "\n", "r": "\r", "t": "\t"}.get(escaped, escaped))
                    index += 1
                    continue
                value.append(character)
                index += 1
            else:
                raise ValueError("unterminated string")
            tokens.append("".join(value))
        else:
            start = index
            while index < length and not text[index].isspace() and text[index] not in "()":
                index += 1
            tokens.append(text[start:index])
        if len(tokens) > limits.max_tokens:
            raise ValueError("token limit exceeded")
    return tokens


def _parse_s_expression(text: str, limits: PCBParserLimits) -> SExpression:
    stack: list[list[object]] = []
    roots: list[object] = []
    for token in _tokenize(text, limits):
        if token == "(":
            if len(stack) >= limits.max_depth:
                raise ValueError("nesting limit exceeded")
            stack.append([])
        elif token == ")":
            if not stack:
                raise ValueError("unexpected close")
            expression = tuple(stack.pop())
            if stack:
                stack[-1].append(expression)
            else:
                roots.append(expression)
        else:
            if not stack:
                raise ValueError("atom outside expression")
            stack[-1].append(token)
    if stack or len(roots) != 1 or not isinstance(roots[0], tuple):
        raise ValueError("invalid root expression")
    return roots[0]


def _head(expression: SExpression) -> str | None:
    return expression[0] if expression and isinstance(expression[0], str) else None


def _children(expression: SExpression, name: str) -> list[SExpression]:
    return [
        item
        for item in expression[1:]
        if isinstance(item, tuple) and _head(item) == name
    ]


def _child(expression: SExpression, name: str) -> SExpression | None:
    values = _children(expression, name)
    return values[0] if values else None


def _atom(expression: SExpression | None, index: int) -> str | None:
    if expression is None or len(expression) <= index:
        return None
    value = expression[index]
    return value if isinstance(value, str) else None


def _required_atom(expression: SExpression | None, index: int) -> str:
    value = _atom(expression, index)
    if value is None or not value.strip():
        raise ValueError("required atom is missing")
    return value.strip()


def _number(expression: SExpression | None, index: int) -> float:
    return float(_required_atom(expression, index))


def _integer(expression: SExpression | None, index: int) -> int:
    return int(_required_atom(expression, index))


def _property(expression: SExpression, name: str) -> str | None:
    for item in _children(expression, "property"):
        if (_atom(item, 1) or "").casefold() == name.casefold():
            return _atom(item, 2)
    legacy_name = name.casefold()
    for item in _children(expression, "fp_text"):
        if (_atom(item, 1) or "").casefold() == legacy_name:
            return _atom(item, 2)
    return None


def _net_name(expression: SExpression | None, nets: dict[int, str]) -> str | None:
    if expression is None:
        return None
    net_id = _integer(expression, 1)
    explicit = _atom(expression, 2)
    if net_id == 0:
        if explicit is not None and explicit.strip():
            raise ValueError("unconnected net has a name")
        return None
    declared = nets.get(net_id)
    if declared is None or not declared.strip():
        raise ValueError("net reference is missing")
    if explicit is not None and explicit.strip() != declared.strip():
        raise ValueError("net reference does not match")
    return declared.strip()


def _net_type(name: str) -> PCBNetType:
    if _GROUND_NET.search(name):
        return PCBNetType.GROUND
    if _POWER_NET.search(name):
        return PCBNetType.POWER
    if _CLOCK_NET.search(name):
        return PCBNetType.CLOCK
    return PCBNetType.SIGNAL if name.strip() else PCBNetType.UNKNOWN


def _extract_layers(root: SExpression) -> tuple[PCBLayer, ...]:
    container = _child(root, "layers")
    if container is None:
        raise ValueError("layers are missing")
    layers: list[PCBLayer] = []
    for item in container[1:]:
        if not isinstance(item, tuple):
            raise ValueError("layer is malformed")
        layers.append(
            PCBLayer(
                index=_integer(item, 0),
                name=_required_atom(item, 1),
                type=_required_atom(item, 2),
            )
        )
    if not layers:
        raise ValueError("layers are empty")
    return tuple(layers)


def _extract_net_map(root: SExpression) -> tuple[dict[int, str], list[int]]:
    result: dict[int, str] = {}
    order: list[int] = []
    for item in _children(root, "net"):
        net_id = _integer(item, 1)
        name = _atom(item, 2) or ""
        if net_id in result:
            raise ValueError("duplicate net id")
        result[net_id] = name
        if name.strip():
            order.append(net_id)
    return result, order


def _extract_components(
    root: SExpression,
    nets: dict[int, str],
) -> tuple[PCBComponent, ...]:
    components: list[PCBComponent] = []
    expressions = [*_children(root, "footprint"), *_children(root, "module")]
    for expression in expressions:
        identifier = _required_atom(expression, 1)
        library, separator, footprint = identifier.partition(":")
        if not separator:
            footprint = library
            library_value: str | None = None
        else:
            library_value = library
        at = _child(expression, "at")
        pins: list[PCBPin] = []
        for pad in _children(expression, "pad"):
            pins.append(
                PCBPin(
                    number=_required_atom(pad, 1),
                    pad_type=_required_atom(pad, 2),
                    net_name=_net_name(_child(pad, "net"), nets),
                )
            )
        components.append(
            PCBComponent(
                reference=_property(expression, "Reference") or "",
                value=_property(expression, "Value") or "",
                footprint=footprint,
                library=library_value,
                position=PCBPosition(x_mm=_number(at, 1), y_mm=_number(at, 2)),
                rotation=float(_atom(at, 3) or 0),
                layer=_required_atom(_child(expression, "layer"), 1),
                pins=tuple(pins),
            )
        )
    return tuple(components)


def _extract_tracks(root: SExpression, nets: dict[int, str]) -> tuple[PCBTrack, ...]:
    tracks: list[PCBTrack] = []
    for item in _children(root, "segment"):
        start = _child(item, "start")
        end = _child(item, "end")
        tracks.append(
            PCBTrack(
                start=PCBPosition(x_mm=_number(start, 1), y_mm=_number(start, 2)),
                end=PCBPosition(x_mm=_number(end, 1), y_mm=_number(end, 2)),
                width_mm=_number(_child(item, "width"), 1),
                layer=_required_atom(_child(item, "layer"), 1),
                net_name=_net_name(_child(item, "net"), nets),
            )
        )
    return tuple(tracks)


def _extract_vias(root: SExpression, nets: dict[int, str]) -> tuple[PCBVia, ...]:
    vias: list[PCBVia] = []
    for item in _children(root, "via"):
        at = _child(item, "at")
        layers = _child(item, "layers")
        if layers is None:
            raise ValueError("via layers are missing")
        vias.append(
            PCBVia(
                position=PCBPosition(x_mm=_number(at, 1), y_mm=_number(at, 2)),
                diameter_mm=_number(_child(item, "size"), 1),
                drill_mm=_number(_child(item, "drill"), 1),
                layers=tuple(
                    value for value in layers[1:] if isinstance(value, str) and value
                ),
                net_name=_net_name(_child(item, "net"), nets),
            )
        )
    return tuple(vias)


def _extract_zones(root: SExpression, nets: dict[int, str]) -> tuple[PCBZone, ...]:
    zones: list[PCBZone] = []
    for item in _children(root, "zone"):
        layer = _child(item, "layer")
        layers = _child(item, "layers")
        if layer is not None:
            layer_names: Iterable[str] = (_required_atom(layer, 1),)
        elif layers is not None:
            layer_names = (
                value for value in layers[1:] if isinstance(value, str) and value
            )
        else:
            raise ValueError("zone layers are missing")
        zones.append(
            PCBZone(
                name=_atom(_child(item, "name"), 1),
                net_name=(
                    _atom(_child(item, "net_name"), 1)
                    or _net_name(_child(item, "net"), nets)
                ),
                layers=tuple(layer_names),
            )
        )
    return tuple(zones)


def _metadata(root: SExpression) -> dict[str, str | int]:
    result: dict[str, str | int] = {}
    version = _atom(_child(root, "version"), 1)
    generator = _atom(_child(root, "generator"), 1)
    if version is not None:
        result["format_version"] = int(version)
    if generator is not None and generator.strip():
        result["generator"] = generator.strip()
    return result


def _extract_board(root: SExpression, filename: str) -> UnifiedPCBModel:
    if _head(root) != "kicad_pcb":
        raise ValueError("unsupported root")
    nets, net_order = _extract_net_map(root)
    components = _extract_components(root, nets)
    layers = _extract_layers(root)
    tracks = _extract_tracks(root, nets)
    vias = _extract_vias(root, nets)
    zones = _extract_zones(root, nets)
    _validate_layer_references(components, layers, tracks, vias, zones)
    nodes_by_net: dict[str, list[PCBNetNode]] = {}
    for component in components:
        for pin in component.pins:
            if pin.net_name is not None:
                nodes_by_net.setdefault(pin.net_name, []).append(
                    PCBNetNode(reference=component.reference, pin=pin.number)
                )
    net_models = tuple(
        PCBNet(
            name=nets[net_id],
            net_type=_net_type(nets[net_id]),
            nodes=tuple(nodes_by_net.get(nets[net_id], [])),
        )
        for net_id in net_order
    )
    if not any((components, net_models, tracks, vias, zones)):
        raise ValueError("board is empty")
    return UnifiedPCBModel(
        board_name=Path(filename).stem,
        source_format="kicad_pcb",
        components=components,
        nets=net_models,
        layers=layers,
        tracks=tracks,
        vias=vias,
        zones=zones,
        metadata=_metadata(root),
    )


def _validate_layer_references(
    components: tuple[PCBComponent, ...],
    layers: tuple[PCBLayer, ...],
    tracks: tuple[PCBTrack, ...],
    vias: tuple[PCBVia, ...],
    zones: tuple[PCBZone, ...],
) -> None:
    declared = {layer.name for layer in layers}
    referenced = [
        *(component.layer for component in components),
        *(track.layer for track in tracks),
        *(layer for via in vias for layer in via.layers),
        *(layer for zone in zones for layer in zone.layers),
    ]
    if any(layer not in declared for layer in referenced):
        raise ValueError("PCB layer reference is missing")
