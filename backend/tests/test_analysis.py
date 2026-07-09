import unittest
from datetime import date, timedelta

from analysis import DailySnapshot, build_phase_summary, detect_changepoints


def make_snapshots(counts: list[int]) -> list[DailySnapshot]:
    start = date(2026, 1, 1)
    return [
        DailySnapshot(
            day=start + timedelta(days=index),
            message_count=count,
            active_members=1 if count else 0,
            top_author="alguien" if count else None,
            top_author_messages=count,
        )
        for index, count in enumerate(counts)
    ]


class DetectChangepointsTests(unittest.TestCase):
    def test_finds_real_level_shift(self) -> None:
        counts = [15] * 20 + [2] * 20 + [0] * 10
        breakpoints = detect_changepoints(counts)

        self.assertEqual(breakpoints, [20, 50])

    def test_flat_series_has_no_internal_breakpoint(self) -> None:
        breakpoints = detect_changepoints([5] * 30)

        self.assertEqual(breakpoints, [30])

    def test_too_short_series_is_a_single_segment(self) -> None:
        breakpoints = detect_changepoints([5, 3, 0])

        self.assertEqual(breakpoints, [3])


class BuildPhaseSummaryTests(unittest.TestCase):
    def test_labels_high_pulse_then_wear_out_phases(self) -> None:
        # PELT no justifica separar "2/dia" de "0/dia" al final (la varianza del
        # salto grande domina la penalizacion) y los deja como una sola fase.
        snapshots = make_snapshots([15] * 20 + [2] * 20 + [0] * 10)

        phases = build_phase_summary(snapshots)

        labels = [phase.label for phase in phases]
        self.assertEqual(labels, ["Pulso alto", "Desgaste"])
        self.assertEqual(phases[0].start_day, snapshots[0].day)
        self.assertEqual(phases[-1].end_day, snapshots[-1].day)

    def test_empty_snapshots_returns_no_phases(self) -> None:
        self.assertEqual(build_phase_summary([]), [])


if __name__ == "__main__":
    unittest.main()
