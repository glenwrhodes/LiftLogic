"""Tests for the simulation itself: movement, doors, boarding and stats.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

import unittest

from liftlogic.schedulers import ALL_SCHEDULERS, Scheduler
from liftlogic.sim import Config, Simulation


class GoTo(Scheduler):
    """A scripted scheduler: every lift heads for one fixed floor."""

    def __init__(self, floor=None):
        self.floor = floor

    def next_stop(self, lift, sim):
        return self.floor


def quiet(**overrides) -> Config:
    """A config with no random arrivals and round numbers, for exact checks."""
    settings = dict(floors=6, lifts=1, capacity=2, speed=1.0, door_time=1.0,
                    arrival_rate=0.0, dt=0.1)
    settings.update(overrides)
    return Config(**settings)


class MovementTests(unittest.TestCase):
    def test_idle_lift_stays_put(self):
        sim = Simulation(GoTo(None), quiet())
        sim.run(5)
        self.assertEqual(sim.lifts[0].position, 0)
        self.assertFalse(sim.lifts[0].doors_open)

    def test_lift_travels_at_its_speed_and_opens_at_the_target(self):
        sim = Simulation(GoTo(3), quiet())
        lift = sim.lifts[0]
        sim.run(1.5)
        self.assertGreater(lift.position, 1.0)
        self.assertLess(lift.position, 2.0)
        sim.run(2.0)    # 3 floors at 1 floor per second, plus a little slack
        self.assertEqual(lift.position, 3)
        self.assertTrue(lift.doors_open)

    def test_lift_never_leaves_the_building(self):
        for cls in ALL_SCHEDULERS:
            sim = Simulation(cls(), Config(), seed=3)
            for _ in range(60 * 120):
                sim.step()
                for lift in sim.lifts:
                    self.assertGreaterEqual(lift.position, 0)
                    self.assertLessEqual(lift.position, sim.config.floors - 1)

    def test_scheduler_choosing_a_missing_floor_is_an_error(self):
        sim = Simulation(GoTo(99), quiet())
        with self.assertRaises(ValueError):
            sim.step()

    def test_lift_does_not_move_while_doors_are_open(self):
        scheduler = GoTo(0)
        sim = Simulation(scheduler, quiet())
        sim.step()                      # doors open at the ground floor
        scheduler.floor = 4
        sim.run(0.5)
        self.assertTrue(sim.lifts[0].doors_open)
        self.assertEqual(sim.lifts[0].position, 0)
        sim.run(1.0)
        self.assertFalse(sim.lifts[0].doors_open)
        self.assertGreater(sim.lifts[0].position, 0)


class BoardingTests(unittest.TestCase):
    def test_passenger_boards_rides_and_gets_out(self):
        scheduler = GoTo(0)
        sim = Simulation(scheduler, quiet())
        p = sim.add_passenger(0, 2)
        sim.step()
        self.assertEqual(sim.lifts[0].riders, [p])
        self.assertEqual(sim.waiting[0], [])
        scheduler.floor = 2
        sim.run(4)
        self.assertEqual(sim.lifts[0].riders, [])
        self.assertEqual(sim.delivered, [p])
        self.assertIsNotNone(p.done_time)

    def test_capacity_is_respected_in_queue_order(self):
        sim = Simulation(GoTo(0), quiet(capacity=2))
        a, b, c = (sim.add_passenger(0, 3) for _ in range(3))
        sim.step()
        self.assertEqual(sim.lifts[0].riders, [a, b])
        self.assertEqual(sim.waiting[0], [c])
        self.assertTrue(sim.lifts[0].full)

    def test_latecomer_boards_while_doors_are_still_open(self):
        sim = Simulation(GoTo(0), quiet())
        sim.step()
        sim.run(0.3)
        late = sim.add_passenger(0, 1)
        sim.step()
        self.assertEqual(sim.lifts[0].riders, [late])

    def test_bad_trips_are_rejected(self):
        sim = Simulation(GoTo(None), quiet())
        with self.assertRaises(ValueError):
            sim.add_passenger(2, 2)
        with self.assertRaises(ValueError):
            sim.add_passenger(0, 6)
        with self.assertRaises(ValueError):
            sim.add_passenger(-1, 2)


class StatsTests(unittest.TestCase):
    def test_empty_building_has_zero_stats(self):
        st = Simulation(GoTo(None), quiet()).stats()
        self.assertEqual((st.spawned, st.delivered, st.waiting, st.riding), (0, 0, 0, 0))
        self.assertEqual((st.avg_wait, st.max_wait), (0.0, 0.0))

    def test_wait_stops_counting_when_the_passenger_boards(self):
        scheduler = GoTo(None)
        sim = Simulation(scheduler, quiet())
        p = sim.add_passenger(0, 1)
        sim.run(2)
        self.assertAlmostEqual(p.wait(sim.time), 2.0)
        scheduler.floor = 0
        sim.step()                      # boards at 2.1 seconds
        sim.run(3)
        self.assertAlmostEqual(p.wait(sim.time), 2.1)

    def test_average_and_longest_include_people_still_waiting(self):
        scheduler = GoTo(0)
        sim = Simulation(scheduler, quiet())
        sim.add_passenger(0, 1)         # boards on the first step: waits 0.1s
        sim.step()
        scheduler.floor = None
        sim.add_passenger(3, 0)         # nobody ever comes for this one
        sim.run(9.9)
        st = sim.stats()
        self.assertEqual((st.spawned, st.waiting, st.riding), (2, 1, 1))
        self.assertAlmostEqual(st.max_wait, 9.9)
        self.assertAlmostEqual(st.avg_wait, (0.1 + 9.9) / 2)


class ArrivalTests(unittest.TestCase):
    def test_same_seed_gives_every_algorithm_the_same_passengers(self):
        streams = []
        for cls in ALL_SCHEDULERS:
            sim = Simulation(cls(), Config(), seed=11)
            sim.run(120)
            streams.append([(p.origin, p.dest, p.spawn_time) for p in sim.passengers])
        self.assertGreater(len(streams[0]), 20)
        self.assertEqual(streams[0], streams[1])
        self.assertEqual(streams[0], streams[2])

    def test_different_seeds_give_different_passengers(self):
        trips = []
        for seed in (1, 2):
            sim = Simulation(GoTo(None), Config(), seed=seed)
            sim.run(60)
            trips.append([(p.origin, p.dest) for p in sim.passengers])
        self.assertNotEqual(trips[0], trips[1])

    def test_arrival_rate_is_about_right_and_trips_are_valid(self):
        sim = Simulation(GoTo(None), Config(arrival_rate=1.0), seed=5)
        sim.run(600)
        self.assertGreater(len(sim.passengers), 500)
        self.assertLess(len(sim.passengers), 700)
        for p in sim.passengers:
            self.assertNotEqual(p.origin, p.dest)
            self.assertIn(p.origin, range(sim.config.floors))
            self.assertIn(p.dest, range(sim.config.floors))

    def test_tiny_buildings_are_rejected(self):
        with self.assertRaises(ValueError):
            Simulation(GoTo(None), Config(floors=1))
        with self.assertRaises(ValueError):
            Simulation(GoTo(None), Config(lifts=0))

    def test_two_floor_building_works(self):
        for cls in ALL_SCHEDULERS:
            sim = Simulation(cls(), Config(floors=2), seed=1)
            sim.run(120)
            self.assertGreater(len(sim.delivered), 0)


if __name__ == "__main__":
    unittest.main()
