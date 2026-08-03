from __future__ import annotations

from pathlib import Path

from web.demo import load_demo_manifest


def test_esp32_camera_demo_is_loaded_from_manifest_metadata_only(
    monkeypatch,
) -> None:
    original_read_bytes = Path.read_bytes

    def reject_fixture_reads(path: Path) -> bytes:
        if path.name != "manifest.json":
            raise AssertionError("demo fixture content must not be read")
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", reject_fixture_reads)
    manifest = load_demo_manifest(Path("demo/esp32_camera/manifest.json"))

    assert manifest.id == "synthetic-esp32-camera-product-demo"
    assert manifest.name == "ESP32 Camera 综合工程审查"
    assert "分析 ESP32-S3 Camera 设计" in manifest.request
    assert {item.filename for item in manifest.attachments} == {
        "esp32_camera_datasheet.pdf",
        "esp32_camera.kicad_pcb",
        "camera_firmware.c",
        "camera_build.log",
    }
    assert manifest.required_agents == ("hardware", "firmware", "pcb", "debug")
    assert all(
        item.size_bytes == (Path("demo/esp32_camera") / item.filename).stat().st_size
        for item in manifest.attachments
    )
