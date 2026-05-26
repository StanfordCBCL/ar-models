import json
import shutil
import struct
import unittest
from pathlib import Path

from ar_models.core import (
    build_manifest_entry,
    default_part_colors,
    discover_input_files,
    lookup_surface_indices,
    parse_rotation,
    pressure_to_mmhg,
    prompt_scene_config,
    sample_sequence_indices,
    slugify,
    sort_time_series_files,
)
from ar_models.glb_postprocess import embed_animated_pressure_colors
from ar_models.site import write_index_page, write_model_page


class CoreTests(unittest.TestCase):
    def test_slugify_normalizes_text(self):
        self.assertEqual(slugify("CHiPS 10 Series 5"), "chips-10-series-5")

    def test_discover_input_files_collects_directory_contents(self):
        root = Path(self._testMethodName)
        tmp_path = Path.cwd() / ".tmp-tests" / root
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        tmp_path.mkdir(parents=True, exist_ok=True)
        sample_dir = tmp_path / "inputs"
        sample_dir.mkdir()
        keep = sample_dir / "aorta.vtp"
        skip = sample_dir / "notes.txt"
        keep.write_text("x")
        skip.write_text("y")

        discovered = discover_input_files([str(sample_dir)])

        self.assertEqual(discovered, [keep.resolve()])

    def test_prompt_scene_config_uses_defaults_and_parses_rotation(self):
        responses = iter(["", "", "", "", "90,0,180", "", ""])
        config = prompt_scene_config(lambda _: next(responses))

        self.assertEqual(config.fit_meters, 0.18)
        self.assertEqual(config.decimate_ratio, 0.30)
        self.assertEqual(config.rotation_deg, (90.0, 0.0, 180.0))
        self.assertTrue(config.centered)
        self.assertTrue(config.shade_smooth)

    def test_default_part_colors_cycles_palette(self):
        colors = default_part_colors(["lv", "rv", "la"])
        self.assertEqual(list(colors), ["lv", "rv", "la"])
        self.assertTrue(colors["lv"].startswith("#"))

    def test_build_manifest_entry_serializes_scene_config(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))

        entry = build_manifest_entry(slug="chips", title="CHiPS", parts=["lv", "rv"], config=config)

        self.assertEqual(entry["page"], "models/chips/")
        self.assertEqual(entry["blenderParameters"]["rotation_deg"], [0.0, 0.0, 0.0])

    def test_build_manifest_entry_serializes_animation_metadata(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))

        entry = build_manifest_entry(
            slug="animated",
            title="Animated",
            parts=["pressure-surface"],
            config=config,
            animation={"enabled": True, "frameCount": 28, "fps": 12},
            pressure_presentation={"unit": "mmHg", "rangeMmHg": [-1.6, 46.1]},
            download_glb_path="assets/models/animated/animated-static.glb",
        )

        self.assertEqual(entry["downloadGlb"], "assets/models/animated/animated-static.glb")
        self.assertEqual(entry["animation"]["frameCount"], 28)
        self.assertEqual(entry["pressurePresentation"]["unit"], "mmHg")

    def test_parse_rotation_rejects_wrong_shape(self):
        with self.assertRaises(ValueError):
            parse_rotation("0,1")

    def test_write_model_page_embeds_download_button(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))
        entry = build_manifest_entry(slug="chips", title="CHiPS", parts=["lv", "rv"], config=config)
        output_dir = Path.cwd() / ".tmp-tests" / self._testMethodName
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"

        write_model_page(output_path, entry)

        page = output_path.read_text()
        self.assertIn("Download QR code", page)
        self.assertIn("../../assets/models/chips/chips.glb", page)
        self.assertNotIn('id="cycle-slider"', page)

    def test_write_model_page_embeds_animation_controls(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))
        entry = build_manifest_entry(
            slug="animated",
            title="Animated",
            parts=["pressure-surface"],
            config=config,
            animation={
                "enabled": True,
                "frameCount": 28,
                "fps": 12,
                "durationSeconds": 2.25,
                "labelMode": "normalized-cycle",
                "representativeFrame": {"sourceName": "result_2400.vtu"},
            },
            pressure_presentation={
                "arrayName": "Pressure",
                "divisor": 1333.2,
                "unit": "mmHg",
                "rangeMmHg": [-1.6, 46.1],
                "colorRangeMmHg": [-1.6, 46.1],
                "sampledFrames": [{"label": "0% of cycle", "sourceName": "result_2000.vtu", "minPressureMmHg": 0.0, "maxPressureMmHg": 1.0}],
            },
            download_glb_path="assets/models/animated/animated-static.glb",
        )
        output_dir = Path.cwd() / ".tmp-tests" / self._testMethodName
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"

        write_model_page(output_path, entry)

        page = output_path.read_text()
        self.assertIn("Pause animation", page)
        self.assertIn("Static GLB and USDZ downloads use the systolic pressure result", page)
        self.assertNotIn("Static GLB and USDZ downloads use the systolic pressure result (result_2400.vtu).", page)
        self.assertNotIn("Full-cycle range", page)
        self.assertNotIn("Pressure scale is fixed across the full cardiac period", page)
        self.assertNotIn("Current timestep range", page)
        self.assertNotIn("Array:", page)
        self.assertIn("../../assets/models/animated/animated-static.glb", page)
        self.assertIn('id="cycle-slider"', page)
        self.assertIn('role="slider"', page)
        self.assertIn('aria-valuemax="100"', page)
        self.assertIn('class="cycle-slider-label" id="cycle-label"', page)
        self.assertIn('viewer.currentTime', page)
        self.assertIn('setPointerCapture', page)
        self.assertIn('toggleButton.textContent = "Play animation"', page)
        self.assertIn('ArrowLeft', page)
        self.assertIn('ArrowRight', page)
        self.assertIn('Home', page)
        self.assertIn('End', page)

    def test_write_index_page_embeds_preview_model(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))
        entry = build_manifest_entry(slug="chips", title="CHiPS", parts=["lv", "rv"], config=config)
        output_dir = Path.cwd() / ".tmp-tests" / self._testMethodName
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"

        write_index_page(output_path, [entry])

        page = output_path.read_text()
        self.assertIn('<script type="module"', page)
        self.assertIn('model-viewer src="assets/models/chips/chips.glb"', page)
        self.assertIn('auto-rotate', page)
        self.assertIn('aspect-ratio: 1 / 1;', page)
        self.assertIn("Animated entries also expose cycle-aware pressure metadata", page)

    def test_write_index_page_sets_animation_loop_for_animated_entries(self):
        responses = iter(["", "", "", "", "", "", ""])
        config = prompt_scene_config(lambda _: next(responses))
        entry = build_manifest_entry(
            slug="animated",
            title="Animated",
            parts=["pressure-surface"],
            config=config,
            animation={"enabled": True, "frameCount": 28, "fps": 12},
            pressure_presentation={"unit": "mmHg", "rangeMmHg": [-1.6, 46.1]},
        )
        output_dir = Path.cwd() / ".tmp-tests" / self._testMethodName
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "index.html"

        write_index_page(output_path, [entry])

        page = output_path.read_text()
        self.assertIn("animation-loop", page)

    def test_sort_time_series_files_orders_numeric_suffixes(self):
        files = [Path("result_20.vtu"), Path("result_100.vtu"), Path("result_3.vtu")]

        ordered = sort_time_series_files(files)

        self.assertEqual([path.name for path in ordered], ["result_3.vtu", "result_20.vtu", "result_100.vtu"])

    def test_sample_sequence_indices_preserves_required_frames(self):
        sampled = sample_sequence_indices(101, 28, required_indices=[0, 20, 100])

        self.assertEqual(len(sampled), 28)
        self.assertIn(0, sampled)
        self.assertIn(20, sampled)
        self.assertIn(100, sampled)

    def test_pressure_to_mmhg_uses_divisor(self):
        self.assertAlmostEqual(pressure_to_mmhg(2666.4, 1333.2), 2.0)

    def test_lookup_surface_indices_resolves_original_ids(self):
        surface_original_ids = [0, 619, 60696, 609, 613, 623]
        requested_ids = [619, 613, 0]

        resolved = lookup_surface_indices(surface_original_ids, requested_ids)

        self.assertEqual(resolved, [1, 4, 0])

    def test_embed_animated_pressure_colors_adds_color_morph_targets(self):
        output_dir = Path.cwd() / ".tmp-tests" / self._testMethodName
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        glb_path = output_dir / "animated.glb"
        color_path = output_dir / "pressure-colors.bin"

        color_path.write_bytes(bytes([0, 255, 0, 255, 0, 0]))
        self._write_test_glb(glb_path)

        embed_animated_pressure_colors(
            glb_path,
            {
                "colorDataPath": str(color_path),
                "sampledFrames": [{"sampledIndex": 0}, {"sampledIndex": 1}],
                "representativeFrame": {"sampledIndex": 1},
                "surface": {"vertexCount": 1},
            },
        )

        payload, binary_chunk = self._read_test_glb(glb_path)
        target = payload["meshes"][0]["primitives"][0]["targets"][0]
        self.assertIn("COLOR_0", target)

        color_accessor = payload["accessors"][target["COLOR_0"]]
        color_view = payload["bufferViews"][color_accessor["bufferView"]]
        delta = struct.unpack_from("<3f", binary_chunk, color_view["byteOffset"])
        self.assertAlmostEqual(delta[0], -1.0, places=6)
        self.assertAlmostEqual(delta[1], 1.0, places=6)
        self.assertAlmostEqual(delta[2], 0.0, places=6)

    def _write_test_glb(self, path: Path) -> None:
        arrays = [
            (1.0, 2.0, 3.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (0.1, 0.2, 0.3),
            (0.0, 0.0, 0.0),
        ]
        binary_chunk = b"".join(struct.pack("<3f", *values) for values in arrays)
        payload = {
            "asset": {"version": "2.0"},
            "buffers": [{"byteLength": len(binary_chunk)}],
            "bufferViews": [
                {"buffer": 0, "byteOffset": 0, "byteLength": 12, "target": 34962},
                {"buffer": 0, "byteOffset": 12, "byteLength": 12, "target": 34962},
                {"buffer": 0, "byteOffset": 24, "byteLength": 12, "target": 34962},
                {"buffer": 0, "byteOffset": 36, "byteLength": 12, "target": 34962},
                {"buffer": 0, "byteOffset": 48, "byteLength": 12, "target": 34962},
            ],
            "accessors": [
                {"bufferView": 0, "componentType": 5126, "count": 1, "type": "VEC3"},
                {"bufferView": 1, "componentType": 5126, "count": 1, "type": "VEC3"},
                {"bufferView": 2, "componentType": 5126, "count": 1, "type": "VEC3"},
                {"bufferView": 3, "componentType": 5126, "count": 1, "type": "VEC3"},
                {"bufferView": 4, "componentType": 5126, "count": 1, "type": "VEC3"},
            ],
            "meshes": [
                {
                    "primitives": [
                        {
                            "attributes": {"POSITION": 0, "NORMAL": 1, "COLOR_0": 2},
                            "targets": [{"POSITION": 3, "NORMAL": 4}],
                        }
                    ],
                    "weights": [0.0],
                    "extras": {"targetNames": ["Frame_000"]},
                }
            ],
            "nodes": [{"mesh": 0}],
            "scenes": [{"nodes": [0]}],
            "scene": 0,
            "animations": [
                {
                    "channels": [{"sampler": 0, "target": {"node": 0, "path": "weights"}}],
                    "samplers": [{"input": 0, "output": 0, "interpolation": "STEP"}],
                }
            ],
        }

        json_chunk = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
        binary_chunk += b"\x00" * ((4 - len(binary_chunk) % 4) % 4)
        total_length = 12 + 8 + len(json_chunk) + 8 + len(binary_chunk)

        with path.open("wb") as handle:
            handle.write(struct.pack("<4sII", b"glTF", 2, total_length))
            handle.write(struct.pack("<I4s", len(json_chunk), b"JSON"))
            handle.write(json_chunk)
            handle.write(struct.pack("<I4s", len(binary_chunk), b"BIN\x00"))
            handle.write(binary_chunk)

    def _read_test_glb(self, path: Path) -> tuple[dict[str, object], bytes]:
        payload = path.read_bytes()
        json_length = struct.unpack_from("<I", payload, 12)[0]
        json_start = 20
        json_end = json_start + json_length
        document = json.loads(payload[json_start:json_end].decode("utf-8"))
        binary_length = struct.unpack_from("<I", payload, json_end)[0]
        binary_start = json_end + 8
        return document, payload[binary_start : binary_start + binary_length]


if __name__ == "__main__":
    unittest.main()
