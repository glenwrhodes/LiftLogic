# Lift Logic

An elevator simulator that compares three scheduling algorithms side by side.

Three identical buildings are shown in cross-section. Each has 8 floors and 2 lifts, and each receives exactly the same passengers at the same moments. The only difference is the algorithm running the lifts. Under each building are its wait-time stats.

| Algorithm | How it decides |
| --- | --- |
| First Come, First Served | Fetches the passenger who has waited longest and delivers riders in the order they boarded, with no stops on the way. |
| Nearest First | Always goes to the closest stop, whether that is a rider's floor or someone calling. |
| LOOK (Collective Sweep) | Keeps travelling one way, collecting people going that way, and turns around only when nothing is left ahead. |

Passengers are drawn green when they arrive and turn yellow, then red, the longer they wait. Riders are blue.

## Running it

It needs Python 3.10 or later and pygame (`pip install -r requirements.txt`).

```
python -m liftlogic
```

| Key | Action |
| --- | --- |
| Space | Pause |
| T | Traffic: Quiet, Normal, Rush hour |
| Up / Down | Faster / slower (1x, 2x, 4x, 8x) |
| R | Restart with the same seed, keeping the traffic level |
| Esc | Quit |

Options: `--seed N` picks a different stream of passengers, `--speed N` sets the starting speed, and `--traffic quiet|normal|rush` sets the starting traffic level.

## Traffic levels

Which algorithm does best depends on how busy the building is, so the traffic can be changed while it runs. The current level is shown at the top right.

| Level | Passengers per second |
| --- | --- |
| Quiet | 0.4 |
| Normal (default) | 0.8 |
| Rush hour | 1.2 |

Changing the level keeps the three buildings on identical passengers. The stats count everything since the start, so after changing level press R for a clean run at that level.

### What LOOK does when the lifts are full

A full lift does not stop for callers. LOOK's sweep down starts at the top, so the upper floors fill the lift first and it passes the people lower down. When more people want to go down than the lifts can carry, the whole shortfall lands on floors 1 and 2, and those callers can wait a very long time while the upper floors are served promptly. This is how the algorithm behaves, not a fault, and `tests/test_schedulers.py` (`LookFullLiftTests`) pins it down.

## Recording frames for video

```
python -m liftlogic --record frames --seconds 30
```

This writes `frames/frame_00000.png`, `frame_00001.png` and so on, at 1920x1080. No window opens and the screen is not captured: every frame is drawn in memory and advances the simulation by a fixed amount, so the result does not depend on how fast the computer is, and the same seed always produces the same frames.

| Option | Meaning | Default |
| --- | --- | --- |
| `--seconds` | Length of the video | 30 |
| `--fps` | Frames per second (must divide 60) | 60 |
| `--speed` | Simulated seconds per video second | 2 |
| `--seed` | Stream of passengers | 7 |
| `--traffic` | `quiet`, `normal` or `rush` | normal |
| `--overwrite` | Replace frames already in the folder | off |

To turn the frames into a video with ffmpeg:

```
ffmpeg -framerate 60 -i frames/frame_%05d.png -c:v libx264 -pix_fmt yuv420p liftlogic.mp4
```

## Check mode

```
python -m liftlogic --check
```

Starts everything without opening a window, runs one simulated minute, draws a frame, prints the results and exits with code 0. It exits with a non-zero code if anything fails. Add `--traffic quiet|normal|rush` to check another traffic level.

## Tests

```
python -m unittest discover -s tests -t .
```

## What the stats mean

- **Average wait**: the mean time from a passenger arriving to getting into a lift. People still waiting are counted with the time they have waited so far, so an algorithm cannot look good by leaving someone behind.
- **Longest wait**: the worst single wait, counted the same way.
- **Delivered**: passengers who have reached their floor.
- **Waiting now**: passengers standing on a floor at this moment.

## Layout

| File | Contents |
| --- | --- |
| `liftlogic/sim.py` | The building, lifts, passengers and stats. No pygame. |
| `liftlogic/schedulers.py` | The three algorithms. |
| `liftlogic/render.py` | Drawing. |
| `liftlogic/png.py` | PNG writer used by the recorder. |
| `liftlogic/app.py` | Window, recording and check modes. |
| `tests/` | Tests for all of the above except drawing. |

© 2026 Tiny Moosh Games Inc.
