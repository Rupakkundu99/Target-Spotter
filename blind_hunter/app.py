"""Pygame frontend — the Phase 2 playable loop.

Wires the pieces together at a fixed tick rate:

  1. Pump window events (quit; arrow keys turn; SPACE fires a debug clap so the
     game is playable without a mic).
  2. Drain ClapEvents from the mic InputSource (if one was supplied).
  3. For each clap: step the player (`apply_clap`) and spawn a reveal centered on
     the player's new position.
  4. Advance AI / end-conditions (`update_world`).
  5. Composite and present the frame (`RevealRenderer.draw`).

Turning is done with LEFT/RIGHT arrows here — the stand-in for Option A's voice
keyword turning, which will emit the same facing change once wired in Phase 4.
"""

from __future__ import annotations

import time
from typing import Optional

from blind_hunter import config
from blind_hunter.audio.heartbeat import Heartbeat
from blind_hunter.audio.spatial_mixer import SpatialMixer
from blind_hunter.events import ClapEvent, Direction
from blind_hunter.game import loop as game_loop
from blind_hunter.game.state import World
from blind_hunter.input.base import InputSource
from blind_hunter.render.camera import Camera
from blind_hunter.render.reveal import RevealRenderer


class GameApp:
    def __init__(
        self,
        world: World,
        source: Optional[InputSource] = None,
        enable_audio: bool = True,
    ) -> None:
        self.world = world
        self.source = source
        self.enable_audio = enable_audio
        self.renderer = RevealRenderer()
        self.camera = Camera(world.game_map, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.mixer = SpatialMixer()
        self.heartbeat = Heartbeat()
        self._running = False

    def _handle_clap(self, event: ClapEvent, now: float) -> None:
        sound_type = getattr(event, "sound_type", "clap")
        game_loop.apply_clap(self.world, event, now)
        # Reveal is centered on where the player ended up after the step.
        self.renderer.add_reveal(
            self.world.player.position,
            event.intensity,
            now,
            sound_type=sound_type,
            facing_deg=self.world.player.facing,
        )

    def _hud(self) -> str:
        p = self.world.player
        return (
            f"prey {p.prey_captured}/{self.world.required_prey}   "
            f"facing {int(p.facing) % 360}deg   "
            f"[arrows] turn  [space] clap  [S] snap  [P] ping  [esc] quit"
        )

    def run(self) -> None:
        import pygame

        self.renderer.init(config.WINDOW_WIDTH, config.WINDOW_HEIGHT, self.camera)

        if self.enable_audio:
            try:
                self.mixer.init()
                self.mixer.load_world(self.world)
                self.heartbeat.init()
            except Exception as exc:
                print(f"Audio unavailable ({exc}). Running muted.")
                self.enable_audio = False

        if self.source is not None:
            try:
                self.source.start()
            except Exception as exc:
                print(f"Could not open the mic ({exc}). Keyboard-only: SPACE = clap.")
                self.source = None

        clock = pygame.time.Clock()
        self._running = True
        last = time.monotonic()

        try:
            while self._running:
                now = time.monotonic()
                dt = now - last
                last = now

                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        self._running = False
                    elif e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_ESCAPE:
                            self._running = False
                        elif e.key == pygame.K_LEFT:
                            self.world.player.facing -= config.TURN_DEGREES
                        elif e.key == pygame.K_RIGHT:
                            self.world.player.facing += config.TURN_DEGREES
                        elif e.key == pygame.K_SPACE:
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=Direction.FORWARD,
                                    sound_type="clap",
                                ),
                                now,
                            )
                        elif e.key == pygame.K_s:
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=Direction.FORWARD,
                                    sound_type="snap",
                                ),
                                now,
                            )
                        elif e.key == pygame.K_p:
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=Direction.FORWARD,
                                    sound_type="ping",
                                ),
                                now,
                            )

                # Real claps from the mic (if any).
                if self.source is not None:
                    for clap in self.source.poll():
                        self._handle_clap(clap, now)

                game_loop.update_world(self.world, now, dt)

                if self.enable_audio:
                    self.mixer.update(self.world)
                    self.heartbeat.update(self.world, now)

                self.renderer.draw(self.world, now, hud=self._hud())

                if self.world.won or self.world.lost:
                    self._present_end_screen()
                    self._running = False

                clock.tick(config.TICK_RATE)
        finally:
            if self.source is not None:
                self.source.stop()
            if self.enable_audio:
                self.heartbeat.shutdown()
                self.mixer.shutdown()
            self.renderer.shutdown()

    def _present_end_screen(self) -> None:
        import pygame

        msg = "EXTRACTED — you win" if self.world.won else "CAUGHT — game over"
        print(msg)
        # Brief pause so the final frame/message is visible before the window closes.
        time.sleep(0.05)
        pygame.event.clear()
