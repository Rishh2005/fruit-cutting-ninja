"""
Fruit Cutting Ninja - Advanced animated game in Python (pygame)

Run: python3 fruit_ninja.py

No external image assets required — fruits and effects are drawn procedurally.
Requires: pygame

Features:
- Physics-based fruit arcs
- Slicing with mouse/touch (drag) and visual trail
- Fruit splitting into two halves with particles
- Bombs that end the game on slice
- Score, combos, multiplier, lives, highscore persistence
- Pause, restart

Author: Generated on behalf of the repository owner
"""

import math
import random
import os
import sys
import time
from collections import deque

import pygame
from pygame import gfxdraw

# ---- Config ----
WIDTH, HEIGHT = 900, 600
FPS = 60
GRAVITY = 600  # px/s^2
FRUIT_SPAWN_INTERVAL = 0.9  # seconds (will ramp)
MAX_LIVES = 3
HIGHSCORE_FILE = "highscore.txt"

# Colors
WHITE = (255, 255, 255)
BLACK = (10, 10, 10)
BG_COLOR = (25, 40, 60)
TRAIL_COLOR = (255, 220, 80)

# Pygame init helper
pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.display.set_caption("Fruit Cutting Ninja")
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
CLOCK = pygame.time.Clock()
FONT = pygame.font.SysFont("Segoe UI", 20)
BIG_FONT = pygame.font.SysFont("Segoe UI", 48)
SMALL_FONT = pygame.font.SysFont("Segoe UI", 14)

# Utility

def load_highscore():
    try:
        with open(HIGHSCORE_FILE, "r") as f:
            return int(f.read().strip() or 0)
    except Exception:
        return 0


def save_highscore(score):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            f.write(str(score))
    except Exception:
        pass


def clamp(x, a, b):
    return max(a, min(b, x))


# ---- Game Entities ----
class Particle:
    def __init__(self, pos, vel, color, life=0.6):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.color = color
        self.life = life
        self.age = 0

    def update(self, dt):
        self.vel.y += GRAVITY * dt * 0.4
        self.pos += self.vel * dt
        self.age += dt

    def draw(self, surf):
        if self.age >= self.life:
            return
        a = 255 * (1 - (self.age / self.life))
        r = int(self.color[0])
        g = int(self.color[1])
        b = int(self.color[2])
        s = max(1, int(4 * (1 - self.age / self.life)))
        surf.set_alpha(int(a))
        pygame.draw.circle(surf, (r, g, b), (int(self.pos.x), int(self.pos.y)), s)
        surf.set_alpha(None)


class Fruit:
    def __init__(self, kind, pos, vel, radius=34):
        self.kind = kind  # string
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.radius = radius
        self.alive = True
        self.angle = random.uniform(0, 360)
        self.ang_vel = random.uniform(-200, 200)
        self.sliced = False
        self.split_pieces = []
        self.color = self.pick_color(kind)
        # subtle pattern seed
        self.seed = random.randint(0, 10000)

    def pick_color(self, k):
        if k == "apple":
            return (200, 50, 50)
        if k == "orange":
            return (240, 140, 0)
        if k == "kiwi":
            return (80, 200, 120)
        if k == "melon":
            return (180, 240, 140)
        return (220, 180, 60)

    def update(self, dt):
        if not self.alive:
            return
        if not self.sliced:
            self.vel.y += GRAVITY * dt
            self.pos += self.vel * dt
            self.angle += self.ang_vel * dt
            # off-screen kill
            if self.pos.y - self.radius > HEIGHT + 100:
                self.alive = False
        else:
            # update split pieces
            for p in self.split_pieces:
                p["pos"] += p["vel"] * dt
                p["vel"].y += GRAVITY * dt
                p["angle"] += p["ang_vel"] * dt
                p["life"] -= dt
            if all(p["life"] <= 0 for p in self.split_pieces):
                self.alive = False

    def draw(self, surf):
        if not self.alive:
            return
        if not self.sliced:
            draw_fruit(surf, self.pos, self.radius, self.color, int(self.angle), self.seed)
        else:
            for p in self.split_pieces:
                draw_fruit_half(surf, p["pos"], self.radius, self.color, p["angle"], p["which"])

    def slice(self, line_p1, line_p2):
        if self.sliced or not self.alive:
            return False
        # check segment-circle intersection
        if segment_circle_intersect(line_p1, line_p2, self.pos, self.radius * 0.85):
            self.sliced = True
            # create two pieces
            dir_vector = (line_p2 - line_p1).normalize() if (line_p2 - line_p1).length() != 0 else pygame.Vector2(1, 0)
            perp = pygame.Vector2(-dir_vector.y, dir_vector.x)
            speed = self.vel.length() * 0.8 + 180
            p1 = {
                "pos": pygame.Vector2(self.pos) + perp * 6,
                "vel": pygame.Vector2(self.vel) + perp * speed * 0.01 + perp * 80,
                "angle": self.angle,
                "ang_vel": self.ang_vel + random.uniform(-200, 200),
                "life": 1.2 + random.random() * 0.6,
                "which": 0,
            }
            p2 = {
                "pos": pygame.Vector2(self.pos) - perp * 6,
                "vel": pygame.Vector2(self.vel) - perp * speed * 0.01 - perp * 80,
                "angle": self.angle,
                "ang_vel": self.ang_vel + random.uniform(-200, 200),
                "life": 1.2 + random.random() * 0.6,
                "which": 1,
            }
            self.split_pieces = [p1, p2]
            return True
        return False


class Bomb(Fruit):
    def __init__(self, pos, vel, radius=28):
        super().__init__("bomb", pos, vel, radius)
        self.color = (40, 40, 40)
        self.spark_time = 0

    def draw(self, surf):
        # draw bomb body
        if not self.sliced:
            x, y = int(self.pos.x), int(self.pos.y)
            pygame.gfxdraw.filled_circle(surf, x, y, self.radius, (30, 30, 30))
            pygame.gfxdraw.aacircle(surf, x, y, self.radius, (80, 80, 80))
            # fuse
            fx = x + int(math.cos(time.time() * 8 + self.seed) * 8)
            fy = y - self.radius - 6
            pygame.draw.line(surf, (255, 210, 80), (fx, fy), (fx, fy - 8), 3)
            pygame.draw.circle(surf, (255, 120, 40), (fx, fy - 12), 6)
        else:
            # explosion visual (simple)
            for i in range(12):
                ang = i / 12.0 * math.pi * 2
                rx = int(self.pos.x + math.cos(ang) * (40 - self.split_pieces[0]["life"] * 40))
                ry = int(self.pos.y + math.sin(ang) * (40 - self.split_pieces[0]["life"] * 40))
                pygame.draw.circle(surf, (255, 140, 60), (rx, ry), 6)


# ---- Drawing helpers ----

def draw_fruit(surface, pos, radius, color, angle, seed=0):
    x, y = int(pos.x), int(pos.y)
    s = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
    rect = s.get_rect(center=(radius + 3, radius + 3))
    # base circle
    gfxdraw.filled_circle(s, rect.centerx, rect.centery, radius, color)
    gfxdraw.aacircle(s, rect.centerx, rect.centery, radius, (255, 255, 255, 20))
    # core highlight
    for i in range(3):
        r = int(radius * (0.4 + i * 0.08))
        alpha = int(20 * (3 - i))
        pygame.gfxdraw.filled_circle(s, rect.centerx - int(radius * 0.3), rect.centery - int(radius * 0.35), r, (255, 255, 255, alpha))
    # rotate and blit
    rotated = pygame.transform.rotate(s, angle)
    rrect = rotated.get_rect(center=(x, y))
    surface.blit(rotated, rrect.topleft)


def draw_fruit_half(surface, pos, radius, color, angle, which):
    # draw a half by masking
    x, y = int(pos.x), int(pos.y)
    s = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
    c = (radius + 3, radius + 3)
    gfxdraw.filled_circle(s, c[0], c[1], radius, color)
    # mask half
    mask = pygame.Surface(s.get_size(), pygame.SRCALPHA)
    mask.fill((0, 0, 0, 0))
    poly = []
    if which == 0:
        poly = [(0, 0), (s.get_width(), 0), (s.get_width(), s.get_height() // 2), (0, s.get_height() // 2)]
    else:
        poly = [(0, s.get_height() // 2), (s.get_width(), s.get_height() // 2), (s.get_width(), s.get_height()), (0, s.get_height())]
    pygame.draw.polygon(mask, (0, 0, 0, 255), poly)
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
    # core highlight
    pygame.gfxdraw.aacircle(s, c[0], c[1], radius, (255, 255, 255, 20))
    rotated = pygame.transform.rotate(s, angle)
    rrect = rotated.get_rect(center=(x, y))
    surface.blit(rotated, rrect.topleft)


def segment_circle_intersect(p1, p2, center, radius):
    # compute distance from center to segment
    v = p2 - p1
    w = center - p1
    if v.length_squared() == 0:
        return w.length_squared() <= radius * radius
    t = max(0, min(1, w.dot(v) / v.length_squared()))
    proj = p1 + v * t
    return (proj - center).length_squared() <= radius * radius


# ---- Trail ----
class SliceTrail:
    def __init__(self):
        self.points = deque(maxlen=18)
        self.decay = 0.4
        self.last_time = 0

    def update(self, pos, dt):
        now = time.time()
        if pos is None:
            # let it fade
            if self.points and now - self.last_time > self.decay:
                self.points.popleft()
            return
        self.last_time = now
        self.points.append(pygame.Vector2(pos))

    def draw(self, surf):
        if len(self.points) < 2:
            return
        pts = list(self.points)
        for i in range(len(pts) - 1):
            a = pts[i]
            b = pts[i + 1]
            t = i / max(1, len(pts) - 1)
            width = int(18 * (1 - t))
            col = (TRAIL_COLOR[0], TRAIL_COLOR[1], TRAIL_COLOR[2], int(200 * (1 - t)))
            anti_line(surf, a, b, width, col)


def anti_line(surf, a, b, width, color):
    # draw thick anti-aliased line by drawing circles along the segment
    points = int(max(1, (a - b).length() // 6))
    for i in range(points + 1):
        t = i / max(1, points)
        p = a.lerp(b, t)
        s = pygame.Surface((width * 2, width * 2), pygame.SRCALPHA)
        pygame.gfxdraw.filled_circle(s, width, width, width, color)
        surf.blit(s, (int(p.x - width), int(p.y - width)))


# ---- Game ----
class Game:
    def __init__(self):
        self.running = True
        self.score = 0
        self.mult = 1
        self.combo = 0
        self.lives = MAX_LIVES
        self.entities = []
        self.particles = []
        self.trail = SliceTrail()
        self.last_spawn = 0
        self.spawn_interval = FRUIT_SPAWN_INTERVAL
        self.mouse_down = False
        self.highscore = load_highscore()
        self.paused = False
        self.game_over = False
        self.last_slice_time = 0

    def spawn(self, difficulty=1.0):
        # spawn arcs from bottom
        side = random.choice(["left", "right", "center"])
        x = 0
        vx = 0
        if side == "left":
            x = random.randint(80, 240)
            vx = random.uniform(150, 300)
        elif side == "right":
            x = random.randint(WIDTH - 240, WIDTH - 80)
            vx = random.uniform(-300, -150)
        else:
            x = random.randint(160, WIDTH - 160)
            vx = random.uniform(-120, 120)
        y = HEIGHT + 40
        vy = -random.uniform(650, 900) * difficulty
        # choose fruit or bomb
        if random.random() < 0.08 * difficulty:
            e = Bomb((x, y), (vx, vy))
        else:
            kind = random.choice(["apple", "orange", "kiwi", "melon"])
            r = random.randint(26, 40)
            e = Fruit(kind, (x, y), (vx, vy), r)
        self.entities.append(e)

    def update(self, dt):
        if self.paused or self.game_over:
            return
        self.last_spawn += dt
        # ramp difficulty over time
        t = pygame.time.get_ticks() / 1000.0
        difficulty = 1 + (t / 40.0)
        if self.last_spawn > max(0.25, self.spawn_interval / difficulty):
            self.spawn(difficulty)
            self.last_spawn = 0
        # update entities
        for ent in list(self.entities):
            ent.update(dt)
            if not ent.alive:
                if isinstance(ent, Fruit) and not ent.sliced:
                    # missed fruit costs life
                    if not isinstance(ent, Bomb):
                        self.lives -= 1
                        self.combo = 0
                        self.mult = 1
                        if self.lives <= 0:
                            self.end_game()
                self.entities.remove(ent)
        # update particles
        for p in list(self.particles):
            p.update(dt)
            if p.age >= p.life:
                self.particles.remove(p)
        # trail decay handled in update call

    def draw_ui(self):
        # score
        score_s = FONT.render(f"Score: {self.score}", True, WHITE)
        SCREEN.blit(score_s, (12, 12))
        mult_s = SMALL_FONT.render(f"x{self.mult}  Combo:{self.combo}", True, (200, 200, 220))
        SCREEN.blit(mult_s, (12, 44))
        # lives
        for i in range(self.lives):
            pygame.draw.circle(SCREEN, (240, 80, 80), (WIDTH - 30 - i * 30, 30), 10)
        # highscore
        hs = SMALL_FONT.render(f"Highscore: {self.highscore}", True, (200, 200, 200))
        SCREEN.blit(hs, (WIDTH - 200, 12))

    def slice_check(self, p1, p2):
        hit_any = False
        for ent in list(self.entities):
            if ent.slice(p1, p2):
                hit_any = True
                if isinstance(ent, Bomb):
                    # immediate explosion game over
                    self.create_explosion(ent.pos)
                    self.end_game(bomb=True)
                else:
                    # score
                    pts = 50 + int(ent.radius * 2)
                    now = time.time()
                    if now - self.last_slice_time < 0.4:
                        self.combo += 1
                        self.mult = 1 + min(5, self.combo // 3)
                    else:
                        self.combo = 1
                        self.mult = 1
                    self.last_slice_time = now
                    gained = pts * self.mult
                    self.score += gained
                    # particle burst
                    self.create_particles(ent.pos, ent.color, count=18)
                # slice sound (optional)
        return hit_any

    def create_particles(self, pos, color, count=12):
        for i in range(count):
            ang = random.random() * math.pi * 2
            sp = random.uniform(80, 360)
            vel = pygame.Vector2(math.cos(ang) * sp, math.sin(ang) * sp - 120)
            life = 0.6 + random.random() * 0.8
            self.particles.append(Particle(pos, vel, color, life))

    def create_explosion(self, pos):
        # lots of orange particles
        for i in range(60):
            ang = random.random() * math.pi * 2
            sp = random.uniform(40, 540)
            vel = pygame.Vector2(math.cos(ang) * sp, math.sin(ang) * sp - 60)
            color = (255, random.randint(80, 200), 40)
            self.particles.append(Particle(pos, vel, color, 1.4))

    def end_game(self, bomb=False):
        self.game_over = True
        if self.score > self.highscore:
            self.highscore = self.score
            save_highscore(self.score)
        # create final particle celebration
        self.create_explosion(pygame.Vector2(WIDTH / 2, HEIGHT / 2))

    def reset(self):
        self.score = 0
        self.mult = 1
        self.combo = 0
        self.lives = MAX_LIVES
        self.entities = []
        self.particles = []
        self.trail = SliceTrail()
        self.last_spawn = 0
        self.game_over = False
        self.paused = False


# ---- Main loop ----

def main():
    game = Game()
    running = True
    last_mouse = None
    mouse_positions = deque(maxlen=6)
    while running:
        dt = CLOCK.tick(FPS) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                if event.key == pygame.K_p:
                    game.paused = not game.paused
                if event.key == pygame.K_r:
                    game.reset()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    game.mouse_down = True
                    mouse_positions.clear()
                    mouse_positions.append(pygame.Vector2(event.pos))
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    game.mouse_down = False
                    # finalize slicing along last trail
                    pts = list(mouse_positions)
                    if len(pts) >= 2:
                        for i in range(len(pts) - 1):
                            p1 = pts[i]
                            p2 = pts[i + 1]
                            game.slice_check(p1, p2)
                    mouse_positions.clear()
            elif event.type == pygame.MOUSEMOTION:
                if game.mouse_down:
                    mouse_positions.append(pygame.Vector2(event.pos))
                    game.trail.update(event.pos, dt)

        # continuous slicing while dragging: check the latest segment
        if game.mouse_down and len(mouse_positions) >= 2:
            p1 = mouse_positions[-2]
            p2 = mouse_positions[-1]
            game.slice_check(p1, p2)

        game.update(dt)

        # draw
        SCREEN.fill(BG_COLOR)

        # background parallax
        for i in range(4):
            pygame.draw.rect(SCREEN, (20 + i * 6, 30 + i * 8, 45 + i * 6), (0, i * (HEIGHT // 6), WIDTH, HEIGHT // 6))

        # entities
        for ent in game.entities:
            ent.draw(SCREEN)
        # particles
        for p in game.particles:
            p.draw(SCREEN)
        # trail
        game.trail.draw(SCREEN)

        # UI
        game.draw_ui()

        if game.paused:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((10, 10, 10, 180))
            SCREEN.blit(overlay, (0, 0))
            t = BIG_FONT.render("PAUSED", True, WHITE)
            SCREEN.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2)))
        if game.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 200))
            SCREEN.blit(overlay, (0, 0))
            t = BIG_FONT.render("GAME OVER", True, (220, 100, 80))
            SCREEN.blit(t, t.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
            s = FONT.render(f"Final Score: {game.score}", True, WHITE)
            SCREEN.blit(s, s.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 8)))
            r = SMALL_FONT.render("Press R to Restart", True, (220, 220, 220))
            SCREEN.blit(r, r.get_rect(center=(WIDTH // 2, HEIGHT // 2 + 48)))

        # FPS small
        fps_s = SMALL_FONT.render(str(int(CLOCK.get_fps())), True, (180, 180, 220))
        SCREEN.blit(fps_s, (WIDTH - 40, HEIGHT - 28))

        pygame.display.flip()

    pygame.quit()


if __name__ == '__main__':
    main()
