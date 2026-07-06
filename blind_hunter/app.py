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
import pygame

from blind_hunter import config
from blind_hunter.audio.ambient import AmbientDrone
from blind_hunter.audio.heartbeat import Heartbeat
from blind_hunter.audio.spatial_mixer import SpatialMixer
from blind_hunter.events import ClapEvent, Direction
from blind_hunter.game import loop as game_loop
from blind_hunter.game.state import World
from blind_hunter.input.base import InputSource
from blind_hunter.render.camera import Camera
from blind_hunter.render.horror_renderer import HorrorRenderer


class GameApp:
    def __init__(
        self,
        world: World,
        source: Optional[InputSource] = None,
        webcam_tracker: Optional["WebcamTracker"] = None,
        enable_audio: bool = True,
        show_title: bool = False,
    ) -> None:
        self.world = world
        self.source = source
        self.webcam_tracker = webcam_tracker
        self.enable_audio = enable_audio
        self.show_title = show_title
        self.renderer = HorrorRenderer()
        self.camera = Camera(world.game_map, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.mixer = SpatialMixer()
        self.heartbeat = Heartbeat()
        self.ambient = AmbientDrone()
        self._running = False

    def _handle_clap(self, event: ClapEvent, now: float) -> None:
        sound_type = getattr(event, "sound_type", "clap")
        print(f"[DEBUG] clap! type={sound_type} intensity={event.intensity:.2f} pos={self.world.player.position}")
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
        # Show webcam pointing direction when tracker is active
        if self.webcam_tracker is not None and self.webcam_tracker.hand_detected:
            aim = self.webcam_tracker.latest_direction.value.upper()
            return (
                f"prey {p.prey_captured}/{self.world.required_prey}   "
                f"facing {int(p.facing) % 360}deg   "
                f"aim: {aim}   "
                f"[point+clap] move  [S] snap  [P] ping  [esc] quit"
            )
        elif self.webcam_tracker is not None:
            return (
                f"prey {p.prey_captured}/{self.world.required_prey}   "
                f"facing {int(p.facing) % 360}deg   "
                f"aim: ---   "
                f"[point+clap] move  [S] snap  [P] ping  [esc] quit"
            )
        return (
            f"prey {p.prey_captured}/{self.world.required_prey}   "
            f"facing {int(p.facing) % 360}deg   "
            f"[arrows] turn  [space] clap  [S] snap  [P] ping  [esc] quit"
        )

    def run(self) -> None:
        import pygame

        self.renderer.init(config.WINDOW_WIDTH, config.WINDOW_HEIGHT, self.camera)

        if self.show_title and self.renderer._screen:
            from blind_hunter.render.menu import show_title_screen

            mission_text = f"MISSION: Extract {self.world.required_prey} prey and reach extraction."
            if not show_title_screen(self.renderer._screen, mission_text):
                self.renderer.shutdown()
                return

        if self.enable_audio:
            try:
                self.mixer.init()
                self.mixer.load_world(self.world)
                self.heartbeat.init()
                self.ambient.init()
            except Exception as exc:
                print(f"Audio unavailable ({exc}). Running muted.")
                self.enable_audio = False

        # Start webcam tracker before the mic so direction is ready at first clap.
        if self.webcam_tracker is not None:
            try:
                self.webcam_tracker.start()
            except Exception as exc:
                print(f"Could not start webcam tracker ({exc}). Arrow-key turning only.")
                self.webcam_tracker = None

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
                            dir_val = self.webcam_tracker.latest_direction if self.webcam_tracker is not None else Direction.FORWARD
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=dir_val,
                                    sound_type="clap",
                                ),
                                now,
                            )
                        elif e.key == pygame.K_s:
                            dir_val = self.webcam_tracker.latest_direction if self.webcam_tracker is not None else Direction.FORWARD
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=dir_val,
                                    sound_type="snap",
                                ),
                                now,
                            )
                        elif e.key == pygame.K_p:
                            dir_val = self.webcam_tracker.latest_direction if self.webcam_tracker is not None else Direction.FORWARD
                            self._handle_clap(
                                ClapEvent(
                                    intensity=config.DEBUG_CLAP_INTENSITY,
                                    direction=dir_val,
                                    sound_type="ping",
                                ),
                                now,
                            )
                        elif e.key == pygame.K_c:
                            if not game_loop._attempt_capture(self.world):
                                print("[CAPTURE FAILED] No prey within range! Use S (snap) to sneak close to a yellow dot first.")

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
            if self.webcam_tracker is not None:
                self.webcam_tracker.stop()
            if self.enable_audio:
                self.heartbeat.shutdown()
                self.ambient.shutdown()
                self.mixer.shutdown()
            self.renderer.shutdown()

    def _present_end_screen(self) -> None:
        import pygame
        import time

        if not self.renderer._screen:
            return

        screen = self.renderer._screen
        width, height = screen.get_size()
        
        # Dramatic horror overlay
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((20, 0, 5, 200) if self.world.lost else (5, 20, 15, 200))
        screen.blit(overlay, (0, 0))

        font_large = pygame.font.SysFont("consolas", 48, bold=True)
        font_small = pygame.font.SysFont("consolas", 20)

        if self.world.won:
            title_text = font_large.render("EXTRACTED", True, (120, 255, 180))
            sub_text = font_small.render("You escaped the darkness.", True, (200, 220, 210))
        else:
            title_text = font_large.render("CONSUMED", True, (255, 60, 60))
            sub_text = font_small.render("The predator found its prey.", True, (220, 150, 150))

        prompt_text = font_small.render("[ Press any key or wait to continue ]", True, (150, 150, 160))

        screen.blit(title_text, ((width - title_text.get_width()) // 2, height // 2 - 50))
        screen.blit(sub_text, ((width - sub_text.get_width()) // 2, height // 2 + 10))
        screen.blit(prompt_text, ((width - prompt_text.get_width()) // 2, height // 2 + 70))

        pygame.display.flip()

        # Wait for key press or timeout (3.0 seconds)
        start_t = time.monotonic()
        while time.monotonic() - start_t < 3.0:
            for e in pygame.event.get():
                if e.type in (pygame.QUIT, pygame.KEYDOWN):
                    return
            time.sleep(0.05)
