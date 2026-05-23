import shutil
import unittest
from pathlib import Path

from ar_models.core import (
    build_manifest_entry,
    default_part_colors,
    discover_input_files,
    parse_rotation,
    prompt_scene_config,
    slugify,
)
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
        self.assertIn("The home page now includes a live preview", page)


if __name__ == "__main__":
    unittest.main()
