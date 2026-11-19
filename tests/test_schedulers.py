"""Tests for the three scheduling algorithms.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

import random
import unittest

from liftlogic.schedulers import (ALL_SCHEDULERS, FirstComeFirstServed, Look,
                                  NearestFirst, Scheduler)
from liftlogic.sim import Config, Simulation


def quiet(**overrides) -> Config:
    """A config with no random arrivals, so tests place every passenger."""
    settings = dict(floors=8, lifts=1, capacity=6, speed=1.0, door_time=1.0,
                    arrival_rate=0.0, dt=0.1)
    settings.update(overrides)
    return Config(**settings)


def drain(sim, limit=600.0):
    """Run until nobody is waiting or riding. Fails the test if that never happens."""
    for _ in range(round(limit / sim.config.dt)):
        st = sim.stats()
        if st.waiting == 0 and st.riding == 0:
            return
        sim.step()
    raise AssertionError(f"{sim.scheduler.name} left passengers stranded: {sim.stats()}")


class FirstComeFirstServedTests(unittest.TestCase):
    def test_answers_the_oldest_call_even_when_another_is_nearer(self):
        sim = Simulation(FirstComeFirstServed(), quiet())
        far = sim.add_passenger(5, 4)
        near = sim.add_passenger(1, 2)
        drain(sim)
        self.assertLess(far.board_time, near.board_time)

    def test_delivers_riders_in_boarding_order(self):
        sim = Simulation(FirstComeFirstServed(), quiet())
        first = sim.add_passenger(0, 4)
        second = sim.add_passenger(0, 2)
        drain(sim)
        self.assertLess(first.done_time, second.done_time)


class NearestFirstTests(unittest.TestCase):
    def test_answers_the_nearest_call_first(self):
        sim = Simulation(NearestFirst(), quiet())
        far = sim.add_passenger(5, 4)
        near = sim.add_passenger(1, 2)
        drain(sim)
        self.assertLess(near.board_time, far.board_time)

    def test_drops_off_the_nearest_rider_first(self):
        sim = Simulation(NearestFirst(), quiet())
        first = sim.add_passenger(0, 4)
        second = sim.add_passenger(0, 2)
        drain(sim)
        self.assertLess(second.done_time, first.done_time)

    def test_picks_up_on_the_way_whichever_direction_the_caller_wants(self):
        sim = Simulation(NearestFirst(), quiet())
        rider = sim.add_passenger(0, 5)
        down = sim.add_passenger(2, 0)
        drain(sim)
        self.assertLess(down.board_time, rider.done_time)


class LookTests(unittest.TestCase):
    def test_stops_on_the_way_for_riders(self):
        sim = Simulation(Look(), quiet())
        first = sim.add_passenger(0, 4)
        second = sim.add_passenger(0, 2)
        drain(sim)
        self.assertLess(second.done_time, first.done_time)

    def test_collects_callers_going_its_way_and_leaves_the_others_for_later(self):
        sim = Simulation(Look(), quiet())
        rider = sim.add_passenger(0, 5)
        same_way = sim.add_passenger(3, 4)
        other_way = sim.add_passenger(2, 0)
        drain(sim)
        self.assertLess(same_way.board_time, rider.done_time)
        self.assertGreater(other_way.board_time, rider.done_time)

    def test_goes_to_the_farthest_caller_then_sweeps_back(self):
        sim = Simulation(Look(), quiet())
        low = sim.add_passenger(3, 0)
        high = sim.add_passenger(6, 0)
        drain(sim)
        # Both want to go down, so the lift passes floor 3 on the way up and
        # collects it on the way back.
        self.assertLess(high.board_time, low.board_time)
        self.assertAlmostEqual(high.done_time, low.done_time)

    def test_turns_around_without_a_second_door_cycle(self):
        sim = Simulation(Look(), quiet())
        up = sim.add_passenger(0, 3)
        down = sim.add_passenger(3, 0)      # waiting where the rider gets out
        drain(sim)
        self.assertAlmostEqual(down.board_time, up.done_time)

    def test_riders_are_never_carried_away_from_their_floor(self):
        sim = Simulation(Look(), Config(), seed=4)
        distance = {}
        for _ in range(60 * 240):
            sim.step()
            for lift in sim.lifts:
                for p in lift.riders:
                    now = abs(lift.position - p.dest)
                    self.assertLessEqual(now, distance.get(p.id, now) + 1e-9)
                    distance[p.id] = now


class LookFullLiftTests(unittest.TestCase):
    """What LOOK does when its lifts arrive full.

    A sweep down starts at the top, so the upper floors fill the lift and it
    passes the callers lower down. In traffic heavier than the lifts can
    carry, the whole shortfall therefore lands on the lowest floors. That is
    how the algorithm works, not a fault: these tests pin it down.
    """

    def test_full_lift_passes_a_low_caller_who_called_first(self):
        sim = Simulation(Look(), quiet(capacity=2))
        low = sim.add_passenger(1, 0)           # the first to call
        high = [sim.add_passenger(5, 0), sim.add_passenger(5, 0)]
        drain(sim)
        # The lift went up to the farthest caller, filled there, and came
        # down past floor 1 without stopping. It had to come back for them.
        for p in high:
            self.assertLess(p.done_time, low.board_time)

    def test_lift_with_room_stops_for_the_same_caller(self):
        sim = Simulation(Look(), quiet(capacity=3))
        low = sim.add_passenger(1, 0)
        high = [sim.add_passenger(5, 0), sim.add_passenger(5, 0)]
        drain(sim)
        for p in high:
            self.assertLess(low.board_time, p.done_time)
            self.assertAlmostEqual(low.done_time, p.done_time)

    def test_in_heavy_traffic_only_full_lifts_pass_low_floor_down_callers(self):
        for seed in (1, 2, 3):
            with self.subTest(seed=seed):
                sim = Simulation(Look(), Config(arrival_rate=1.6), seed=seed)
                passed_full = passed_with_room = 0
                before = [(lift.floor, lift.moving) for lift in sim.lifts]
                for _ in range(60 * 600):
                    sim.step()
                    for i, lift in enumerate(sim.lifts):
                        floor, moving = before[i]
                        before[i] = (lift.floor, lift.moving)
                        came_down_to_a_low_floor = (
                            moving == -1 and lift.floor != floor and lift.floor in (1, 2))
                        if not came_down_to_a_low_floor or lift.doors_open:
                            continue
                        if not any(p.direction == -1 for p in sim.waiting[lift.floor]):
                            continue
                        if lift.full:
                            passed_full += 1
                        elif lift.floor in Scheduler.open_calls(lift, sim):
                            passed_with_room += 1
                self.assertEqual(passed_with_room, 0)
                self.assertGreater(passed_full, 30)

                def average_down_wait(floors):
                    waits = [p.wait(sim.time) for p in sim.passengers
                             if p.origin in floors and p.direction == -1]
                    return sum(waits) / len(waits)

                self.assertGreater(average_down_wait((1, 2)),
                                   5 * average_down_wait((5, 6, 7)))


class SharedBehaviourTests(unittest.TestCase):
    def test_everyone_is_delivered_once_arrivals_stop(self):
        for cls in ALL_SCHEDULERS:
            for lifts in (1, 2, 3):
                with self.subTest(scheduler=cls.name, lifts=lifts):
                    sim = Simulation(cls(), quiet(lifts=lifts, capacity=3))
                    rng = random.Random(lifts)
                    for _ in range(80):
                        origin, dest = rng.sample(range(8), 2)
                        sim.add_passenger(origin, dest)
                        sim.run(rng.uniform(0.0, 2.0))
                    drain(sim)
                    self.assertEqual(len(sim.delivered), 80)
                    self.assertEqual(len({p.id for p in sim.delivered}), 80)
                    for p in sim.passengers:
                        self.assertLessEqual(p.spawn_time, p.board_time)
                        self.assertLess(p.board_time, p.done_time)

    def test_capacity_is_never_exceeded_under_heavy_load(self):
        for cls in ALL_SCHEDULERS:
            with self.subTest(scheduler=cls.name):
                sim = Simulation(cls(), Config(arrival_rate=3.0, capacity=4), seed=9)
                for _ in range(60 * 60):
                    sim.step()
                    for lift in sim.lifts:
                        self.assertLessEqual(len(lift.riders), 4)
                self.assertGreater(len(sim.delivered), 0)

    def test_only_one_lift_answers_a_lone_call(self):
        for cls in ALL_SCHEDULERS:
            with self.subTest(scheduler=cls.name):
                sim = Simulation(cls(), quiet(lifts=2))
                sim.add_passenger(4, 0)
                sim.run(2)
                moved = [lift for lift in sim.lifts if lift.position > 0]
                self.assertEqual(len(moved), 1)

    def test_lifts_rest_when_there_is_nothing_to_do(self):
        for cls in ALL_SCHEDULERS:
            with self.subTest(scheduler=cls.name):
                sim = Simulation(cls(), quiet(lifts=2))
                sim.add_passenger(2, 5)
                drain(sim)
                sim.run(5)
                before = [lift.position for lift in sim.lifts]
                sim.run(5)
                self.assertEqual(before, [lift.position for lift in sim.lifts])
                self.assertFalse(any(lift.doors_open for lift in sim.lifts))

    def test_same_seed_gives_the_same_result(self):
        for cls in ALL_SCHEDULERS:
            with self.subTest(scheduler=cls.name):
                results = []
                for _ in range(2):
                    sim = Simulation(cls(), Config(), seed=21)
                    sim.run(180)
                    results.append(sim.stats())
                self.assertEqual(results[0], results[1])


class OpenCallsTests(unittest.TestCase):
    def test_lists_floors_with_people_waiting(self):
        sim = Simulation(FirstComeFirstServed(), quiet())
        sim.add_passenger(2, 0)
        sim.add_passenger(6, 1)
        self.assertEqual(Scheduler.open_calls(sim.lifts[0], sim), [2, 6])

    def test_full_lift_is_offered_no_calls(self):
        sim = Simulation(FirstComeFirstServed(), quiet(capacity=1))
        sim.add_passenger(0, 5)
        sim.step()
        sim.add_passenger(3, 0)
        self.assertTrue(sim.lifts[0].full)
        self.assertEqual(Scheduler.open_calls(sim.lifts[0], sim), [])

    def test_floor_another_lift_is_heading_for_is_left_to_it(self):
        sim = Simulation(FirstComeFirstServed(), quiet(lifts=2))
        sim.add_passenger(4, 0)
        sim.step()
        first, second = sim.lifts
        self.assertEqual(first.target, 4)
        self.assertEqual(Scheduler.open_calls(second, sim), [])
        self.assertEqual(Scheduler.open_calls(first, sim), [4])


if __name__ == "__main__":
    unittest.main()
