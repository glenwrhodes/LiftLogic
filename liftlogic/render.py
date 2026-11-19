"""Draws the buildings in cross-section, with a stats panel under each.

Everything is drawn onto a fixed 1920x1080 canvas that the caller owns, so the
same code serves the window (which scales the canvas down) and the frame
recorder (which saves it as is). Nothing here needs a display.

Copyright (c) 2026 Tiny Moosh Games Inc.
"""

from __future__ import annotations

import pygame

from . import COPYRIGHT

CANVAS_SIZE = (1920, 1080)

WHITE = (240, 243, 250)
DIM = (150, 160, 185)
SKY_TOP = (18, 22, 40)
SKY_BOTTOM = (52, 68, 108)
GROUND = (34, 40, 52)
SHELL = (126, 134, 158)
ROOM_A = (62, 70, 94)
ROOM_B = (56, 63, 86)
SLAB = (126, 134, 158)
SHAFT = (24, 26, 38)
CABLE = (96, 100, 116)
CAR = (236, 180, 72)
CAR_INSIDE = (250, 240, 214)
GLASS = (120, 170, 220, 120)
RIDER = (70, 120, 220)
PANEL = (26, 30, 46)
BAR_BACK = (44, 50, 72)
GOOD = (84, 208, 128)
OKAY = (240, 200, 70)
BAD = (232, 78, 66)

MARGIN = 30
PANEL_W = 600
GROUND_Y = 804
BUILDING_H = 608
QUEUE_SHOWN = 9
EXIT_TIME = 1.5         # seconds a delivered passenger is shown walking away
DOOR_SLIDE = 0.3        # seconds the doors take to slide open or shut
PATIENCE = 10.0       # seconds of waiting at which a passenger turns yellow


def _mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def wait_colour(seconds: float):
    """Green for a fresh arrival, through yellow, to red for a long wait."""
    if seconds <= PATIENCE:
        return _mix(GOOD, OKAY, seconds / PATIENCE)
    return _mix(OKAY, BAD, (seconds - PATIENCE) / PATIENCE)


def door_opening(lift, door_time: float) -> float:
    """How far open the doors are, from 0 (shut) to 1 (fully open)."""
    if not lift.doors_open:
        return 0.0
    since_open = door_time - lift.door_timer
    return max(0.0, min(1.0, since_open / DOOR_SLIDE, lift.door_timer / DOOR_SLIDE))


class Renderer:
    def __init__(self):
        pygame.font.init()
        self._fonts: dict[int, pygame.font.Font] = {}
        self._background = self._make_background()

    # ------------------------------------------------------------ helpers

    def _text(self, surface, text, size, colour, pos, anchor="topleft"):
        font = self._fonts.get(size)
        if font is None:
            font = self._fonts[size] = pygame.font.Font(None, size)
        image = font.render(text, True, colour)
        rect = image.get_rect(**{anchor: pos})
        surface.blit(image, rect)
        return rect

    @staticmethod
    def _make_background():
        width, height = CANVAS_SIZE
        background = pygame.Surface(CANVAS_SIZE)
        for y in range(height):
            colour = _mix(SKY_TOP, SKY_BOTTOM, y / GROUND_Y)
            pygame.draw.line(background, colour, (0, y), (width, y))
        background.fill(GROUND, (0, GROUND_Y, width, height - GROUND_Y))
        return background

    @staticmethod
    def _figure(surface, x, feet_y, colour, scale=1.0):
        body_w, body_h, head = round(14 * scale), round(24 * scale), round(7 * scale)
        body = pygame.Rect(0, 0, body_w, body_h)
        body.midbottom = (x, feet_y)
        pygame.draw.rect(surface, colour, body, border_radius=round(5 * scale))
        pygame.draw.circle(surface, colour, (x, body.top - head), head)

    # --------------------------------------------------------------- draw

    def draw(self, surface, sims, speed=1, paused=False, hints=False):
        surface.blit(self._background, (0, 0))
        width, height = CANVAS_SIZE

        title = self._text(surface, "LIFT LOGIC", 64, WHITE, (MARGIN, 22))
        self._text(surface, "The same passengers, three ways to run the lifts",
                   30, DIM, (title.right + 24, title.bottom - 6), "bottomleft")
        now = sims[0].time
        status = f"Time {int(now) // 60:02d}:{int(now) % 60:02d}    Speed {speed}x"
        if paused:
            status += "    PAUSED"
        self._text(surface, status, 34, WHITE, (width - MARGIN, 34), "topright")

        all_stats = [sim.stats() for sim in sims]
        worst = max(st.avg_wait for st in all_stats)
        lowest = min(st.avg_wait for st in all_stats)
        for i, (sim, st) in enumerate(zip(sims, all_stats)):
            px = MARGIN + i * (PANEL_W + MARGIN)
            self._text(surface, sim.scheduler.name, 42, WHITE, (px + 4, 98))
            self._text(surface, sim.scheduler.blurb, 26, DIM, (px + 4, 134))
            self._draw_building(surface, sim, px)
            best = worst > lowest and st.avg_wait == lowest
            self._draw_stats(surface, st, px, best, worst)

        footer_y = height - 24
        if hints:
            self._text(surface, "Space pause   Up/Down speed   R restart   Esc quit",
                       24, DIM, (MARGIN, footer_y), "midleft")
        self._draw_legend(surface, width // 2, footer_y)
        self._text(surface, COPYRIGHT, 24, DIM, (width - MARGIN, footer_y), "midright")

    def _draw_legend(self, surface, centre_x, y):
        bar_w = 160
        left = self._text(surface, "Waiting: just arrived", 24, DIM,
                          (centre_x - bar_w // 2 - 12, y), "midright")
        for x in range(bar_w):
            colour = wait_colour(2 * PATIENCE * x / bar_w)
            pygame.draw.line(surface, colour,
                             (left.right + 12 + x, y - 6), (left.right + 12 + x, y + 5))
        self._text(surface, "long wait", 24, DIM, (centre_x + bar_w // 2 + 12, y), "midleft")

    def _draw_building(self, surface, sim, px):
        cfg = sim.config
        now = sim.time
        fh = BUILDING_H // cfg.floors
        top_y = GROUND_Y - cfg.floors * fh
        bx, bw = px + 10, PANEL_W - 20
        shaft_w, gap = 86, 10
        block = cfg.lifts * shaft_w + (cfg.lifts - 1) * gap
        shaft_left = bx + bw - 108 - block
        shaft_right = shaft_left + block

        def floor_y(f):
            return GROUND_Y - f * fh

        # Shell, roof and the machine room above the shafts.
        pygame.draw.rect(surface, SHELL, (bx - 6, top_y - 14, bw + 12, GROUND_Y - top_y + 14))
        pygame.draw.rect(surface, SHELL, (shaft_left - 6, top_y - 40, block + 12, 30),
                         border_radius=4)

        for f in range(cfg.floors):
            y = floor_y(f)
            room = ROOM_A if f % 2 == 0 else ROOM_B
            pygame.draw.rect(surface, room, (bx, y - fh, bw, fh))
            if f:
                pygame.draw.rect(surface, SLAB, (bx, y, bw, 6))
            self._text(surface, "G" if f == 0 else str(f), 28, DIM,
                       (bx + 20, y - fh // 2 + 3), "center")

        for i in range(cfg.lifts):
            sx = shaft_left + i * (shaft_w + gap)
            pygame.draw.rect(surface, SHAFT, (sx, top_y, shaft_w, GROUND_Y - top_y))

        # People waiting, the head of the queue nearest the lifts.
        for f, queue in enumerate(sim.waiting):
            y = floor_y(f)
            for k, p in enumerate(queue[:QUEUE_SHOWN]):
                self._figure(surface, shaft_left - 20 - k * 22, y, wait_colour(p.wait(now)))
            if len(queue) > QUEUE_SHOWN:
                self._text(surface, f"+{len(queue) - QUEUE_SHOWN}", 24, WHITE,
                           (shaft_left - 20 - QUEUE_SHOWN * 22 + 8, y - 14), "midright")

        # People who have just arrived, walking away from the lifts.
        for p in reversed(sim.delivered):
            t = (now - p.done_time) / EXIT_TIME
            if t > 1.0:
                break
            room = ROOM_A if p.dest % 2 == 0 else ROOM_B
            self._figure(surface, round(shaft_right + 18 + t * 72), floor_y(p.dest),
                         _mix(RIDER, room, t))

        car_h = min(62, fh - 14)
        for i, lift in enumerate(sim.lifts):
            sx = shaft_left + i * (shaft_w + gap)
            bottom = round(GROUND_Y - lift.position * fh)
            car = pygame.Rect(sx + 6, bottom - car_h, shaft_w - 12, car_h)
            pygame.draw.line(surface, CABLE, (car.centerx, top_y), (car.centerx, car.top), 2)
            pygame.draw.rect(surface, CAR, car, border_radius=5)
            inside = car.inflate(-8, -8)
            pygame.draw.rect(surface, CAR_INSIDE, inside)
            for k in range(len(lift.riders)):
                self._figure(surface, inside.left + 6 + k * 11, inside.bottom, RIDER, 0.7)

            # Glass doors that slide apart from the middle.
            shut = 1.0 - door_opening(lift, cfg.door_time)
            leaf_w = round(inside.width / 2 * shut)
            if leaf_w > 0:
                leaf = pygame.Surface((leaf_w, inside.height), pygame.SRCALPHA)
                leaf.fill(GLASS)
                surface.blit(leaf, inside.topleft)
                surface.blit(leaf, (inside.right - leaf_w, inside.top))
                pygame.draw.line(surface, CAR, (inside.left + leaf_w, inside.top),
                                 (inside.left + leaf_w, inside.bottom - 1))
                pygame.draw.line(surface, CAR, (inside.right - leaf_w, inside.top),
                                 (inside.right - leaf_w, inside.bottom - 1))

    def _draw_stats(self, surface, st, px, best, worst):
        box = pygame.Rect(px, 830, PANEL_W, 196)
        pygame.draw.rect(surface, PANEL, box, border_radius=14)
        self._text(surface, "AVERAGE WAIT", 26, DIM, (box.left + 24, box.top + 18))
        big = self._text(surface, f"{st.avg_wait:.1f}s", 92, GOOD if best else WHITE,
                         (box.left + 24, box.top + 46))
        if best:
            badge = pygame.Rect(big.right + 18, 0, 84, 34)
            badge.centery = big.centery - 4
            pygame.draw.rect(surface, GOOD, badge, border_radius=8)
            self._text(surface, "BEST", 26, PANEL, badge.center, "center")

        rows = (
            ("Longest wait", f"{st.max_wait:.0f}s"),
            ("Delivered", str(st.delivered)),
            ("Waiting now", str(st.waiting)),
        )
        for k, (label, value) in enumerate(rows):
            y = box.top + 20 + k * 38
            self._text(surface, label, 30, DIM, (box.left + 340, y))
            self._text(surface, value, 30, WHITE, (box.right - 24, y), "topright")

        # Average wait as a bar, measured against the worst of the three.
        bar = pygame.Rect(box.left + 24, box.bottom - 38, PANEL_W - 48, 16)
        pygame.draw.rect(surface, BAR_BACK, bar, border_radius=8)
        if worst > 0 and st.avg_wait > 0:
            fill = bar.copy()
            fill.width = max(16, round(bar.width * st.avg_wait / worst))
            pygame.draw.rect(surface, wait_colour(st.avg_wait), fill, border_radius=8)
