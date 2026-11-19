"""The three ways to run Lift Logic: in a window, recording frames, or a check.

Only `run_window` opens a window. The other two draw onto an ordinary surface
in memory and never touch the display.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

from __future__ import annotations

from pathlib import Path

from .schedulers import ALL_SCHEDULERS
from .sim import Config, Simulation

STEPS_PER_SECOND = 60
SPEEDS = (1, 2, 4, 8)
FRAME_PATTERN = "frame_{:05d}.png"


def make_sims(seed: int, config: Config | None = None) -> list[Simulation]:
    """One building per algorithm, all fed the same passengers."""
    config = config or Config(dt=1.0 / STEPS_PER_SECOND)
    return [Simulation(cls(), config, seed) for cls in ALL_SCHEDULERS]


def summary(sims) -> str:
    parts = []
    for sim in sims:
        st = sim.stats()
        parts.append(f"{sim.scheduler.name}: avg {st.avg_wait:.1f}s, "
                     f"longest {st.max_wait:.0f}s, delivered {st.delivered}")
    return "\n".join(parts)


def run_check(seed: int) -> int:
    """Start everything without a window, run briefly, draw once, and exit."""
    import pygame
    from .render import CANVAS_SIZE, Renderer

    sims = make_sims(seed)
    for sim in sims:
        sim.run(60)
    canvas = pygame.Surface(CANVAS_SIZE)
    Renderer().draw(canvas, sims)
    for sim in sims:
        if not sim.delivered:
            print(f"Lift Logic check FAILED: {sim.scheduler.name} delivered nobody")
            return 1
    print(summary(sims))
    print("Lift Logic check OK")
    return 0


def run_record(out_dir: str, seconds: float, fps: int, speed: int, seed: int,
               overwrite: bool) -> int:
    """Save the run as numbered PNG frames, drawn in memory at a fixed step."""
    import pygame
    from .png import save_png
    from .render import CANVAS_SIZE, Renderer

    if seconds <= 0:
        print("--seconds must be more than 0")
        return 2
    if fps <= 0 or STEPS_PER_SECOND % fps:
        print(f"--fps must divide {STEPS_PER_SECOND} evenly (60, 30, 20, 15, ...)")
        return 2
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    old = sorted(out.glob("frame_*.png"))
    if old and not overwrite:
        print(f"{out} already holds {len(old)} frames. "
              "Choose another folder or add --overwrite to replace them.")
        return 2
    for path in old:
        path.unlink()

    sims = make_sims(seed)
    renderer = Renderer()
    canvas = pygame.Surface(CANVAS_SIZE)
    steps_per_frame = speed * STEPS_PER_SECOND // fps
    total = round(seconds * fps)
    for frame in range(total):
        renderer.draw(canvas, sims, speed=speed)
        save_png(canvas, out / FRAME_PATTERN.format(frame))
        for _ in range(steps_per_frame):
            for sim in sims:
                sim.step()
        if (frame + 1) % fps == 0 or frame + 1 == total:
            print(f"\r{frame + 1}/{total} frames", end="", flush=True)
    print()
    print(f"Saved {total} frames ({CANVAS_SIZE[0]}x{CANVAS_SIZE[1]}, {fps} fps) to {out.resolve()}")
    return 0


def run_window(seed: int, speed: int) -> int:
    import pygame
    from .render import CANVAS_SIZE, Renderer

    pygame.display.init()
    pygame.display.set_caption("Lift Logic")
    window = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
    renderer = Renderer()
    canvas = pygame.Surface(CANVAS_SIZE)
    clock = pygame.time.Clock()
    sims = make_sims(seed)
    paused = False
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    sims = make_sims(seed)
                elif event.key in (pygame.K_UP, pygame.K_DOWN):
                    step = 1 if event.key == pygame.K_UP else -1
                    index = SPEEDS.index(speed) + step
                    speed = SPEEDS[max(0, min(len(SPEEDS) - 1, index))]
        if not paused:
            for _ in range(speed):
                for sim in sims:
                    sim.step()
        renderer.draw(canvas, sims, speed=speed, paused=paused, hints=True)

        # Fit the canvas into the window, keeping its shape.
        win_w, win_h = window.get_size()
        scale = min(win_w / CANVAS_SIZE[0], win_h / CANVAS_SIZE[1])
        size = (max(1, round(CANVAS_SIZE[0] * scale)), max(1, round(CANVAS_SIZE[1] * scale)))
        window.fill((0, 0, 0))
        window.blit(pygame.transform.smoothscale(canvas, size),
                    ((win_w - size[0]) // 2, (win_h - size[1]) // 2))
        pygame.display.flip()
        clock.tick(STEPS_PER_SECOND)
    pygame.quit()
    return 0
