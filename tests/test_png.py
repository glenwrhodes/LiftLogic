"""Tests for the PNG writer and the frame recorder.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from liftlogic import app  # noqa: E402
from liftlogic.png import SIGNATURE, encode_png, save_png  # noqa: E402


def quietly(fn, *args):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


class PngTests(unittest.TestCase):
    def test_saved_file_reads_back_pixel_for_pixel(self):
        surface = pygame.Surface((37, 23))
        for x in range(37):
            for y in range(23):
                surface.set_at((x, y), (x * 6, y * 11, (x * y) % 256))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "picture.png"
            save_png(surface, path)
            self.assertTrue(path.read_bytes().startswith(SIGNATURE))
            loaded = pygame.image.load(str(path))
        self.assertEqual(loaded.get_size(), (37, 23))
        self.assertEqual(pygame.image.tobytes(loaded, "RGB"),
                         pygame.image.tobytes(surface, "RGB"))

    def test_wrong_amount_of_pixel_data_is_rejected(self):
        with self.assertRaises(ValueError):
            encode_png(2, 2, b"\x00" * 11)


class RecorderTests(unittest.TestCase):
    def record(self, folder, seconds=0.2, fps=20, overwrite=False):
        return quietly(app.run_record, folder, seconds, fps, 2, 7, overwrite)

    def test_writes_numbered_full_size_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.record(folder), 0)
            names = sorted(p.name for p in Path(folder).iterdir())
            self.assertEqual(names, [f"frame_{i:05d}.png" for i in range(4)])
            frame = pygame.image.load(str(Path(folder) / names[0]))
            self.assertEqual(frame.get_size(), (1920, 1080))

    def test_same_seed_records_identical_frames(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self.record(a, seconds=0.5)
            self.record(b, seconds=0.5)
            for path in Path(a).iterdir():
                self.assertEqual(path.read_bytes(), (Path(b) / path.name).read_bytes())

    def test_refuses_to_mix_with_old_frames_unless_told_to_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            self.record(folder, seconds=0.5)
            self.assertEqual(self.record(folder), 2)
            self.assertEqual(len(list(Path(folder).iterdir())), 10)
            self.assertEqual(self.record(folder, overwrite=True), 0)
            self.assertEqual(len(list(Path(folder).iterdir())), 4)

    def test_rejects_a_frame_rate_that_does_not_fit_the_time_step(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.record(folder, fps=25), 2)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_check_mode_passes_at_every_traffic_level(self):
        for name in app.TRAFFIC_NAMES:
            self.assertEqual(quietly(app.run_check, 7, name), 0)

    def test_traffic_level_changes_what_is_recorded(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            quietly(app.run_record, a, 0.5, 20, 8, 7, False, "quiet")
            quietly(app.run_record, b, 0.5, 20, 8, 7, False, "rush")
            last = "frame_00009.png"
            self.assertNotEqual((Path(a) / last).read_bytes(), (Path(b) / last).read_bytes())


class TrafficLevelTests(unittest.TestCase):
    def test_levels_get_busier_and_normal_is_the_default(self):
        rates = [app.traffic_level(name)[1] for name in app.TRAFFIC_NAMES]
        self.assertEqual(rates, sorted(rates))
        self.assertEqual(len(set(rates)), 3)
        self.assertEqual(app.DEFAULT_TRAFFIC, "normal")
        self.assertEqual(app.make_sims(1)[0].arrival_rate, app.traffic_level("normal")[1])
        self.assertEqual(app.make_sims(1, traffic="rush")[0].arrival_rate,
                         app.traffic_level("rush")[1])

    def test_the_key_cycles_through_all_levels_and_back(self):
        seen = ["quiet"]
        for _ in range(3):
            seen.append(app.next_traffic(seen[-1]))
        self.assertEqual(seen, ["quiet", "normal", "rush", "quiet"])

    def test_unknown_level_is_an_error(self):
        with self.assertRaises(ValueError):
            app.traffic_level("gridlock")


if __name__ == "__main__":
    unittest.main()
