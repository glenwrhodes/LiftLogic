"""The three scheduling algorithms being compared.

A scheduler is asked one question, `next_stop`, each time a lift is standing
at a floor with its doors closed. It answers with the floor to head for, the
lift's own floor to open the doors there, or None to stay put. The lift asks
again at every floor it reaches, so an answer is never binding for long.

Each building has several lifts and no scheduler sends two of them to the
same call: a call at a floor another lift (with room) is already heading for
is left to that lift.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

from __future__ import annotations


class Scheduler:
    name = "Scheduler"
    blurb = ""

    def next_stop(self, lift, sim) -> int | None:
        raise NotImplementedError

    def on_doors_open(self, lift, sim) -> None:
        """Called after riders get out and before anyone gets in."""

    def may_board(self, lift, passenger, sim) -> bool:
        """Asked for each waiting passenger while the lift has room."""
        return True

    # ------------------------------------------------------------ helpers

    @staticmethod
    def open_calls(lift, sim) -> list[int]:
        """Floors with waiting passengers that this lift is free to answer."""
        if lift.full:
            return []
        taken = {
            other.target
            for other in sim.lifts
            if other is not lift and other.target is not None and not other.full
        }
        return [f for f, queue in enumerate(sim.waiting) if queue and f not in taken]


class FirstComeFirstServed(Scheduler):
    """Serve requests strictly in the order they were made."""

    name = "First Come, First Served"
    blurb = "Oldest request first. No stops on the way."

    def next_stop(self, lift, sim):
        if lift.riders:
            return lift.riders[0].dest      # riders are kept in boarding order
        calls = self.open_calls(lift, sim)
        if not calls:
            return None
        return min(calls, key=lambda f: sim.waiting[f][0].id)


class NearestFirst(Scheduler):
    """Always go to the closest stop, whether a drop-off or a pick-up."""

    name = "Nearest First"
    blurb = "Closest stop next, whichever way it is."

    def next_stop(self, lift, sim):
        stops = {p.dest for p in lift.riders}
        stops.update(self.open_calls(lift, sim))
        if not stops:
            return None
        return min(stops, key=lambda f: (abs(f - lift.floor), f))


class Look(Scheduler):
    """Sweep one way, collecting passengers going that way, then reverse."""

    name = "LOOK (Collective Sweep)"
    blurb = "Keep going one way, then turn around."

    def next_stop(self, lift, sim):
        first = lift.direction or 1
        for d in (first, -first):
            stop = self._stop_towards(lift, sim, d)
            if stop is not None:
                lift.direction = d
                return stop
        lift.direction = 0
        return None

    def on_doors_open(self, lift, sim):
        # Turn around now if this was the end of the sweep, so that people
        # waiting here to go the other way can get straight in.
        d = lift.direction
        if d and self._stop_towards(lift, sim, d) is None:
            lift.direction = -d if self._stop_towards(lift, sim, -d) is not None else 0

    def may_board(self, lift, passenger, sim):
        if lift.direction == 0:
            lift.direction = passenger.direction    # first one in sets the way
        return passenger.direction == lift.direction

    def _stop_towards(self, lift, sim, d) -> int | None:
        """The next stop for a lift sweeping in direction d, if there is one."""
        here = lift.floor
        calls = self.open_calls(lift, sim)
        # "Ahead" includes this floor: a rider for here still has to get out.
        ahead = {p.dest for p in lift.riders if (p.dest - here) * d >= 0}
        for f in calls:
            if (f - here) * d >= 0 and any(p.direction == d for p in sim.waiting[f]):
                ahead.add(f)
        if ahead:
            return min(ahead, key=lambda f: abs(f - here))
        # Nobody ahead is going our way. Go as far as the farthest caller who
        # wants to come back, so the return sweep collects everyone.
        beyond = [f for f in calls if (f - here) * d > 0]
        if beyond:
            return max(beyond, key=lambda f: abs(f - here))
        return None


ALL_SCHEDULERS = (FirstComeFirstServed, NearestFirst, Look)
