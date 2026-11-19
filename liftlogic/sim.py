"""The simulation: a building, its lifts and its passengers.

Nothing in here imports pygame. Time advances in fixed steps, and all
randomness comes from one seeded generator that never looks at the state of
the lifts, so two simulations with the same seed receive exactly the same
passengers whatever their scheduler does.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field


EPSILON = 1e-9     # absorbs rounding error when adding up time steps


@dataclass(frozen=True)
class Config:
    floors: int = 8
    lifts: int = 2
    capacity: int = 6
    speed: float = 1.5          # floors per second
    door_time: float = 1.2      # seconds the doors stay open at a stop
    arrival_rate: float = 0.8  # passengers per second, on average
    lobby_share: float = 0.4    # share of trips that start at the ground floor
    exit_share: float = 0.4     # share of trips that end at the ground floor
    dt: float = 1.0 / 60.0      # length of one simulation step in seconds


@dataclass
class Passenger:
    id: int
    origin: int
    dest: int
    spawn_time: float
    board_time: float | None = None
    done_time: float | None = None
    lift: int | None = None

    @property
    def direction(self) -> int:
        return 1 if self.dest > self.origin else -1

    def wait(self, now: float) -> float:
        """Seconds spent waiting for a lift, still counting if not aboard."""
        end = self.board_time if self.board_time is not None else now
        return end - self.spawn_time


@dataclass
class Lift:
    id: int
    capacity: int
    floor: int = 0              # the floor it is at, or the one it last left
    offset: float = 0.0         # progress towards the next floor, 0 to 1
    moving: int = 0             # -1, 0 or +1: actual movement right now
    direction: int = 0          # -1, 0 or +1: which way it is serving (LOOK)
    door_timer: float = 0.0     # above zero while the doors are open
    target: int | None = None
    riders: list[Passenger] = field(default_factory=list)

    @property
    def position(self) -> float:
        return self.floor + self.moving * self.offset

    @property
    def doors_open(self) -> bool:
        return self.door_timer > 0.0

    @property
    def full(self) -> bool:
        return len(self.riders) >= self.capacity

    @property
    def at_floor(self) -> bool:
        return self.moving == 0


@dataclass(frozen=True)
class Stats:
    spawned: int
    delivered: int
    waiting: int
    riding: int
    avg_wait: float
    max_wait: float


class Simulation:
    def __init__(self, scheduler, config: Config | None = None, seed: int = 1):
        self.config = config or Config()
        if self.config.floors < 2:
            raise ValueError("a building needs at least 2 floors")
        if self.config.lifts < 1:
            raise ValueError("a building needs at least 1 lift")
        self.scheduler = scheduler
        self.seed = seed
        self.rng = random.Random(seed)
        self.time = 0.0
        self.ticks = 0
        self.lifts = [Lift(i, self.config.capacity) for i in range(self.config.lifts)]
        self.waiting: list[list[Passenger]] = [[] for _ in range(self.config.floors)]
        self.passengers: list[Passenger] = []
        self.delivered: list[Passenger] = []
        self._next_arrival = self._arrival_gap()

    # ----------------------------------------------------------- arrivals

    def _arrival_gap(self) -> float:
        rate = self.config.arrival_rate
        return self.rng.expovariate(rate) if rate > 0 else float("inf")

    def _random_trip(self) -> tuple[int, int]:
        top = self.config.floors - 1
        roll = self.rng.random()
        if roll < self.config.lobby_share:
            return 0, self.rng.randint(1, top)
        if roll < self.config.lobby_share + self.config.exit_share:
            return self.rng.randint(1, top), 0
        origin = self.rng.randint(0, top)
        dest = self.rng.randint(0, top - 1)
        if dest >= origin:
            dest += 1
        return origin, dest

    def add_passenger(self, origin: int, dest: int) -> Passenger:
        floors = self.config.floors
        if not (0 <= origin < floors and 0 <= dest < floors):
            raise ValueError("floor out of range")
        if origin == dest:
            raise ValueError("origin and destination must differ")
        p = Passenger(len(self.passengers), origin, dest, self.time)
        self.passengers.append(p)
        self.waiting[origin].append(p)
        return p

    # --------------------------------------------------------------- step

    def step(self) -> None:
        """Advance the simulation by one fixed time step."""
        dt = self.config.dt
        self.ticks += 1
        self.time = self.ticks * dt
        while self._next_arrival <= self.time:
            self.add_passenger(*self._random_trip())
            self._next_arrival += self._arrival_gap()
        for lift in self.lifts:
            self._step_lift(lift, dt)

    def run(self, seconds: float) -> None:
        for _ in range(round(seconds / self.config.dt)):
            self.step()

    def _step_lift(self, lift: Lift, dt: float) -> None:
        if lift.doors_open:
            self._board(lift)       # latecomers can still get in
            lift.door_timer -= dt
            if lift.door_timer < EPSILON:
                lift.door_timer = 0.0
            return

        if lift.moving:
            lift.offset += self.config.speed * dt
            if lift.offset < 1.0 - EPSILON:
                return
            lift.floor += lift.moving
            lift.offset = 0.0
            lift.moving = 0
            # Arrived at a floor: fall through and decide what to do next.

        target = self.scheduler.next_stop(lift, self)
        if target is not None and not 0 <= target < self.config.floors:
            raise ValueError(f"scheduler chose floor {target}, which does not exist")
        lift.target = target
        if target is None:
            return
        if target == lift.floor:
            self._open_doors(lift)
        else:
            lift.moving = 1 if target > lift.floor else -1

    def _open_doors(self, lift: Lift) -> None:
        lift.door_timer = self.config.door_time
        staying = []
        for p in lift.riders:
            if p.dest == lift.floor:
                p.done_time = self.time
                self.delivered.append(p)
            else:
                staying.append(p)
        lift.riders = staying
        self.scheduler.on_doors_open(lift, self)
        self._board(lift)

    def _board(self, lift: Lift) -> None:
        queue = self.waiting[lift.floor]
        if not queue:
            return
        left_behind = []
        for p in queue:
            if not lift.full and self.scheduler.may_board(lift, p, self):
                p.board_time = self.time
                p.lift = lift.id
                lift.riders.append(p)
            else:
                left_behind.append(p)
        self.waiting[lift.floor] = left_behind

    # -------------------------------------------------------------- stats

    def stats(self) -> Stats:
        waits = [p.wait(self.time) for p in self.passengers]
        return Stats(
            spawned=len(self.passengers),
            delivered=len(self.delivered),
            waiting=sum(len(q) for q in self.waiting),
            riding=sum(len(lift.riders) for lift in self.lifts),
            avg_wait=sum(waits) / len(waits) if waits else 0.0,
            max_wait=max(waits) if waits else 0.0,
        )
