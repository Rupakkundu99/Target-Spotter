"""Title Screen and Pause Menu overlays for Blind Hunter 2D Horror Upgrade (Phase 7).

Provides atmospheric UI screens:
1. **Title Screen**: Displayed before a run starts with mission briefing and controls.
2. **Pause Overlay**: Displayed when the game is paused during play.
"""

from __future__ import annotations

import time


def show_title_screen(screen, mission_text: str) -> bool:
    """Show title screen. Returns True if starting play, False if quitting."""
    import pygame

    width, height = screen.get_size()
    font_title = pygame.font.SysFont("consolas", 52, bold=True)
    font_sub = pygame.font.SysFont("consolas", 22)
    font_inst = pygame.font.SysFont("consolas", 18)

    # Background
    screen.fill((8, 8, 12))

    # Title
    title_surf = font_title.render("BLIND HUNTER", True, (200, 30, 40))
    sub_surf = font_sub.render("2D HORROR EDITION", True, (140, 150, 170))
    
    # Mission Briefing
    mission_surf = font_sub.render(mission_text, True, (220, 200, 100))

    # Instructions
    inst_lines = [
        "CONTROLS:",
        "  [SPACE] / [MIC CLAP] : Echolocation Reveal & Move Forward",
        "  [LEFT / RIGHT ARROW] : Turn Left / Right",
        "  [S / P]              : Snap / Ping (Different reveal radii)",
        "  [ESC]                : Quit / Pause",
        "",
        "PRESS [SPACE] OR [ENTER] TO ENTER THE DARKNESS...",
    ]

    screen.blit(title_surf, ((width - title_surf.get_width()) // 2, height // 5))
    screen.blit(sub_surf, ((width - sub_surf.get_width()) // 2, height // 5 + 60))
    screen.blit(mission_surf, ((width - mission_surf.get_width()) // 2, height // 5 + 130))

    y_off = height // 5 + 200
    for line in inst_lines:
        s = font_inst.render(line, True, (160, 170, 185) if line.startswith(" ") else (200, 200, 220))
        screen.blit(s, (width // 6, y_off))
        y_off += 28

    pygame.display.flip()

    while True:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                return False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    return False
                elif e.key in (pygame.K_SPACE, pygame.K_RETURN):
                    return True
        time.sleep(0.02)
