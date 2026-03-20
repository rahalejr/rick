from conditions import Condition
import numpy as np
import pygame
import os
from moviepy.editor import ImageSequenceClip
from Box2D import b2World, b2PolygonShape, b2CircleShape, b2ContactListener
import shutil
import math


digits = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

width = 1000
height = 800
ball_radius = 28
border_width = 11
margin = 15
speed = 300
framerate = 30
time_step = 0.0001
gate_gap_height = 225

red, green, yellow, blue, purple = (255, 0, 0), (20, 82, 20), (255, 255, 0), (0, 0, 255), (128, 0, 128)
colors = [green, red, yellow, blue, purple]

col_dict = {
    'red': (255, 0, 0),
    'green': (20, 82, 20),
    'yellow': (255, 255, 0),
    'blue': (0, 0, 255),
    'purple': (128, 0, 128)
}

rgb_to_name = {v: k for k, v in col_dict.items()}

left_edge_x = margin + border_width / 2
top_edge_y = margin + border_width / 2
bottom_edge_y = height - margin - border_width / 2
wall_len = (height - gate_gap_height - 2 * margin) / 2
wall_half_len = wall_len / 2


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def gaussian_noise(standard_dev):
    u = 1 - np.random.random()
    v = 1 - np.random.random()
    return standard_dev * np.sqrt(-2 * np.log(u)) * np.cos(2 * np.pi * v)


def rotate_velocity_components(vx, vy, theta):
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    new_vx = vx * cos_t - vy * sin_t
    new_vy = vx * sin_t + vy * cos_t
    return new_vx, new_vy


def sort_collision_objects(items):
    return sorted(items, key=lambda x: (x == 'wall', str(x)))


def get_collision_roles(ball_a, ball_b):
    ax = float(ball_a.body.position[0])
    bx = float(ball_b.body.position[0])

    if ax > bx:
        return ball_a, ball_b
    if bx > ax:
        return ball_b, ball_a

    avx = float(ball_a.body.linearVelocity[0])
    bvx = float(ball_b.body.linearVelocity[0])

    if avx < bvx:
        return ball_a, ball_b
    if bvx < avx:
        return ball_b, ball_a

    return (ball_a, ball_b) if str(ball_a.name) < str(ball_b.name) else (ball_b, ball_a)


def collision_magnitude(collider, collided):
    cx, cy = float(collider.body.position[0]), float(collider.body.position[1])
    tx, ty = float(collided.body.position[0]), float(collided.body.position[1])

    nx = tx - cx
    ny = ty - cy
    dist = math.hypot(nx, ny)
    if dist == 0:
        return 0.0

    nx /= dist
    ny /= dist

    cvx, cvy = float(collider.body.linearVelocity[0]), float(collider.body.linearVelocity[1])
    tvx, tvy = float(collided.body.linearVelocity[0]), float(collided.body.linearVelocity[1])

    collider_speed = math.hypot(cvx, cvy)
    if collider_speed == 0:
        return 0.0

    rel_closing_speed = (cvx - tvx) * nx + (cvy - tvy) * ny
    return clamp(rel_closing_speed / collider_speed, 0.0, 1.0)


def draw_checkerboard_square(surface, center, side, num_checks=16):
    x0, y0 = center
    half = (side // 2) + 5
    check_size = side // num_checks
    checker_colors = [(200, 200, 200), (255, 255, 255)]

    for row in range(num_checks):
        for col in range(num_checks):
            c = checker_colors[(row + col) % 2]
            rect = pygame.Rect(
                x0 - half + col * check_size,
                y0 - half + row * check_size,
                check_size,
                check_size
            )
            pygame.draw.rect(surface, c, rect)


def create_world():
    world = b2World(gravity=(0, 0), doSleep=True)

    wall_shapes = [
        ((left_edge_x, margin + wall_half_len), b2PolygonShape(box=(border_width / 2, wall_half_len))),
        ((left_edge_x, height - margin - wall_half_len), b2PolygonShape(box=(border_width / 2, wall_half_len))),
        ((width / 2, top_edge_y), b2PolygonShape(box=((width - 2 * margin) / 2, border_width / 2))),
        ((width / 2, bottom_edge_y), b2PolygonShape(box=((width - 2 * margin) / 2, border_width / 2))),
    ]

    for position, shape in wall_shapes:
        body = world.CreateStaticBody(position=position)
        fixture = body.CreateFixture(shape=shape)
        fixture.restitution = 1.0
        fixture.friction = 0.0
        body.userData = 'wall'

    return world


class Ball:
    def __init__(self, world, params=None, state=None):
        if state is not None:
            self.name = state['name']
            self.slot = state['slot']
            self.color = tuple(state['color'])
            self.noisy = bool(state.get('noisy', False))
            xpos, ypos = state['position']
            vx, vy = state['velocity']
        else:
            self.name = params['ball']
            self.slot = params['position']
            self.color = params['rgb']
            self.noisy = False

            xpos = round(width / 4) if self.name == 'effect' else width + 30 + params['x_jitter']
            ypos = params['ypos']
            vx = 0.0 if self.name == 'effect' else speed * np.cos(params['angle'])
            vy = 0.0 if self.name == 'effect' else speed * np.sin(params['angle'])

        self.body = world.CreateDynamicBody(
            position=(float(xpos), float(ypos)),
            shapes=b2CircleShape(radius=ball_radius)
        )

        self.body.fixtures[0].restitution = 1.0
        self.body.fixtures[0].friction = 0.0
        self.body.linearDamping = 0.0
        self.body.linearVelocity = (float(vx), float(vy))
        self.body.userData = self

        self.collided_with = set()
        self.ball_collisions = []
        self.all_collisions = []

    @property
    def position(self):
        return tuple(map(float, self.body.position))

    def add_collision(self, obj, step, time):
        if obj == 'wall':
            self.all_collisions.append({
                'name': 'wall',
                'slot': 'wall',
                'step': step,
                'time': time
            })
            return

        if isinstance(obj, Ball):
            if obj.noisy:
                self.noisy = True

            self.ball_collisions.append({
                'name': obj.name,
                'slot': obj.slot,
                'step': step,
                'time': time
            })
            self.collided_with.add(obj.name)
            self.all_collisions.append({
                'name': obj.name,
                'slot': obj.slot,
                'step': step,
                'time': time
            })

    def last_collision(self):
        return self.ball_collisions[-1] if len(self.ball_collisions) > 0 else None

    def rotate_velocity(self, theta):
        vx, vy = float(self.body.linearVelocity[0]), float(self.body.linearVelocity[1])
        new_vx, new_vy = rotate_velocity_components(vx, vy, theta)
        self.body.linearVelocity = (new_vx, new_vy)

    def add_noise(self, noise=6):
        z = gaussian_noise(1)
        angle_deg = z * noise
        angle_rad = angle_deg * (math.pi / 180.0)
        self.rotate_velocity(angle_rad)
        self.noisy = True

    def to_state(self):
        return {
            'name': self.name,
            'slot': self.slot,
            'color': list(self.color),
            'position': [float(self.body.position[0]), float(self.body.position[1])],
            'velocity': [float(self.body.linearVelocity[0]), float(self.body.linearVelocity[1])],
            'noisy': bool(self.noisy)
        }


class Simulation:
    def __init__(self, world, balls, noise=6):
        self.world = world
        self.balls = balls
        self.effect_ball = next(ball for ball in balls if ball.name == 'effect')
        self.num_balls = len([b for b in balls if b.name != 'effect'])
        self.noise = noise

        self.hit = False
        self.step = 0
        self.sim_seconds = 0.0
        self.collisions = []
        self.snapshots = []

        self._pending_collision_indices = []

    def find_ball_by_slot(self, slot):
        for ball in self.balls:
            if ball.slot == slot:
                return ball
        return None

    def find_ball_by_name(self, name):
        for ball in self.balls:
            if ball.name == name:
                return ball
        return None

    def snapshot_world(self):
        return {
            'step': int(self.step),
            'sim_seconds': float(self.sim_seconds),
            'hit': bool(self.hit),
            'balls': [ball.to_state() for ball in self.balls]
        }

    def finalize_collisions_for_step(self):
        if not self._pending_collision_indices:
            return

        snapshot_id = len(self.snapshots)
        snapshot = self.snapshot_world()
        snapshot['snapshot_id'] = snapshot_id
        self.snapshots.append(snapshot)

        for idx in self._pending_collision_indices:
            collision = self.collisions[idx]
            collision['snapshot_id'] = snapshot_id
            collision['snapshot_step'] = int(snapshot['step'])
            collision['snapshot_time'] = float(snapshot['sim_seconds'])

            collider_name = collision.get('collider_name')
            collided_name = collision.get('collided_name')

            if collider_name is not None and collided_name is not None:
                collider = self.find_ball_by_name(collider_name)
                collided = self.find_ball_by_name(collided_name)

                collision['collider_post_position'] = [
                    float(collider.body.position[0]),
                    float(collider.body.position[1])
                ]
                collision['collided_post_position'] = [
                    float(collided.body.position[0]),
                    float(collided.body.position[1])
                ]
                collision['collider_post_velocity'] = [
                    float(collider.body.linearVelocity[0]),
                    float(collider.body.linearVelocity[1])
                ]
                collision['collided_post_velocity'] = [
                    float(collided.body.linearVelocity[0]),
                    float(collided.body.linearVelocity[1])
                ]

        self._pending_collision_indices.clear()


class CollisionListener(b2ContactListener):
    def __init__(self, sim):
        super().__init__()
        self.sim = sim

    def BeginContact(self, contact):
        A = contact.fixtureA.body.userData
        B = contact.fixtureB.body.userData

        objects = [
            A.slot if isinstance(A, Ball) else 'wall',
            B.slot if isinstance(B, Ball) else 'wall'
        ]

        if isinstance(A, Ball):
            A.add_collision(B, self.sim.step, self.sim.sim_seconds)

        if isinstance(B, Ball):
            B.add_collision(A, self.sim.step, self.sim.sim_seconds)

        collision_record = {
            'objects': sort_collision_objects(objects),
            'step': int(self.sim.step),
            'time': float(self.sim.sim_seconds),
            'snapshot_id': None,
            'snapshot_step': None,
            'snapshot_time': None,
            'collider': None,
            'collider_name': None,
            'collided': None,
            'collided_name': None,
            'magnitude': None,
            'collider_pre_position': None,
            'collided_pre_position': None,
            'collider_pre_velocity': None,
            'collided_pre_velocity': None,
            'collider_post_position': None,
            'collided_post_position': None,
            'collider_post_velocity': None,
            'collided_post_velocity': None
        }

        if isinstance(A, Ball) and isinstance(B, Ball):
            collider, collided = get_collision_roles(A, B)

            collision_record['collider'] = collider.slot
            collision_record['collider_name'] = collider.name
            collision_record['collided'] = collided.slot
            collision_record['collided_name'] = collided.name
            collision_record['magnitude'] = float(collision_magnitude(collider, collided))
            collision_record['collider_pre_position'] = [
                float(collider.body.position[0]),
                float(collider.body.position[1])
            ]
            collision_record['collided_pre_position'] = [
                float(collided.body.position[0]),
                float(collided.body.position[1])
            ]
            collision_record['collider_pre_velocity'] = [
                float(collider.body.linearVelocity[0]),
                float(collider.body.linearVelocity[1])
            ]
            collision_record['collided_pre_velocity'] = [
                float(collided.body.linearVelocity[0]),
                float(collided.body.linearVelocity[1])
            ]

        self.sim.collisions.append(collision_record)
        self.sim._pending_collision_indices.append(len(self.sim.collisions) - 1)


def build_ball_params(condition):
    ball_colors = [colors[i - 1] for i in condition.ball_positions]

    ball_params = [{
        'ball': 'effect',
        'rgb': (180, 180, 180),
        'ypos': round(height / 2),
        'angle': 0,
        'position': -1,
        'x_jitter': 0,
        'y_jitter': 0
    }]

    for i in range(condition.num_balls):
        ball_params.append({
            'ball': i + 1,
            'rgb': ball_colors[i],
            'position': condition.ball_positions[i],
            'ypos': condition.y_positions[i] + condition.jitter['y'][i],
            'angle': condition.radians[i],
            'x_jitter': condition.jitter['x'][i],
            'y_jitter': condition.jitter['y'][i]
        })

    return ball_params, ball_colors


def build_simulation_from_condition(condition, noise=6):
    world = create_world()
    ball_params, ball_colors = build_ball_params(condition)
    balls = [Ball(world, params=params) for params in ball_params]
    sim = Simulation(world, balls, noise=noise)
    world.contactListener = CollisionListener(sim)
    return sim, ball_colors


def build_simulation_from_snapshot(snapshot, noise=6):
    world = create_world()
    balls = [Ball(world, state=state) for state in snapshot['balls']]
    sim = Simulation(world, balls, noise=noise)
    sim.step = int(snapshot.get('step', 0))
    sim.sim_seconds = float(snapshot.get('sim_seconds', 0.0))
    sim.hit = bool(snapshot.get('hit', False))
    world.contactListener = CollisionListener(sim)
    return sim


def is_hit(sim):
    effect_x = float(sim.effect_ball.body.position[0])
    if effect_x < -5:
        final_pos = float(sim.effect_ball.body.position[1])
        sim.hit = True
        return True, final_pos
    return False, 0.0


def apply_noise_to_snapshot_state(sim, noise=6, target_slots=None, include_effect=False):
    for ball in sim.balls:
        if ball.name == 'effect' and not include_effect:
            continue

        if target_slots is not None:
            if ball.slot not in target_slots and ball.name not in target_slots:
                continue

        vx, vy = float(ball.body.linearVelocity[0]), float(ball.body.linearVelocity[1])
        if math.hypot(vx, vy) == 0:
            continue

        ball.add_noise(noise=noise)


def render_scene(screen, sim, effect_start_pos):
    screen.fill((255, 255, 255))

    draw_checkerboard_square(
        screen,
        [effect_start_pos[0] + 6, effect_start_pos[1] + 6],
        side=ball_radius * 2 + 12
    )

    vert_wall_len = (height - gate_gap_height - 2 * margin) / 2

    pygame.draw.rect(screen, (0, 0, 0), (margin, margin, border_width, vert_wall_len))
    pygame.draw.rect(screen, (0, 0, 0), (margin, height - margin - vert_wall_len, border_width, vert_wall_len))
    pygame.draw.rect(screen, (0, 0, 0), (margin, margin, width - margin, border_width))
    pygame.draw.rect(screen, (0, 0, 0), (margin, height - margin - border_width, width - margin, border_width))
    pygame.draw.rect(screen, (255, 130, 150), (margin, margin + vert_wall_len, border_width, gate_gap_height))

    for ball in sim.balls:
        pygame.draw.circle(
            screen,
            (0, 0, 0),
            (int(ball.body.position[0]), int(ball.body.position[1])),
            ball_radius + 1
        )
        pygame.draw.circle(
            screen,
            ball.color,
            (int(ball.body.position[0]), int(ball.body.position[1])),
            ball_radius
        )


def simulate_loop(sim, record=False, headless=False, filename=None, max_time=6.0):
    frame_count = 0
    final_pos = round(height / 2)
    hit_time = None
    running = True
    SIM_FRAME_TIME = 1.0 / framerate

    if record:
        shutil.rmtree("frames") if os.path.exists("frames") else None
        os.makedirs("frames")

    if not headless:
        pygame.init()
        screen = pygame.display.set_mode((width, height))
        clock = pygame.time.Clock()
        effect_start_pos = (
            float(sim.effect_ball.body.position[0]),
            float(sim.effect_ball.body.position[1])
        )

    while running:
        steps = int(SIM_FRAME_TIME / time_step)

        for _ in range(steps):
            sim.step += 1
            sim.sim_seconds += time_step
            sim.world.Step(time_step, 20, 10)
            sim.finalize_collisions_for_step()

            if hit_time is None:
                hit_now, final_pos = is_hit(sim)
                if hit_now:
                    hit_time = float(sim.sim_seconds)

            if (hit_time is not None and sim.sim_seconds > hit_time + 2.0) or sim.sim_seconds > max_time:
                running = False
                break

        if not headless:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            render_scene(screen, sim, effect_start_pos)

            if record:
                pygame.image.save(screen, f"frames/frame_{frame_count:05d}.png")

            frame_count += 1
            pygame.display.flip()
            clock.tick(framerate)

    if not headless:
        pygame.quit()

    if record and filename is not None:
        frames = sorted(
            os.path.join("frames", fname)
            for fname in os.listdir("frames")
            if fname.endswith(".png")
        )
        clip = ImageSequenceClip(frames, fps=framerate)
        clip.write_videofile(filename, codec="libx264")

    cause_ball = sim.effect_ball.last_collision()

    return {
        'num_balls': sim.num_balls,
        'sim_time': float(sim.sim_seconds),
        'hit': bool(sim.hit),
        'cause_ball': cause_ball['name'] if cause_ball else None,
        'cause_ball_slot': cause_ball['slot'] if cause_ball else None,
        'cause_collisions': sim.effect_ball.all_collisions,
        'final_pos': float(final_pos),
        'collisions': sim.collisions,
        'snapshots': sim.snapshots,
        'final_state': sim.snapshot_world()
    }


def run(
    condition,
    pause=10,
    actual_data=None,
    noise=6,
    cause_color='red',
    cause_ball=1,
    record=False,
    counterfactual=None,
    headless=False,
    clip_num=1,
    is_cf=False,
    max_time=6.0
):
    sim, ball_colors = build_simulation_from_condition(condition, noise=noise)
    output = simulate_loop(
        sim,
        record=record,
        headless=headless,
        filename=condition.filename if record else None,
        max_time=max_time
    )
    output['angles'] = condition.angles
    output['colors'] = [rgb_to_name[c] for c in ball_colors]
    return output


def run_from_snapshot(
    snapshot,
    noise=6,
    target_slots=None,
    include_effect=False,
    record=False,
    headless=True,
    filename=None,
    max_time=6.0
):
    sim = build_simulation_from_snapshot(snapshot, noise=noise)

    if noise and noise > 0:
        apply_noise_to_snapshot_state(
            sim,
            noise=noise,
            target_slots=target_slots,
            include_effect=include_effect
        )

    return simulate_loop(
        sim,
        record=record,
        headless=headless,
        filename=filename,
        max_time=max_time
    )


def monte_carlo_goal_probability(
    snapshot,
    n_simulations=100,
    noise=6,
    target_slots=None,
    include_effect=False,
    max_time=6.0
):
    hits = 0
    for _ in range(n_simulations):
        out = run_from_snapshot(
            snapshot=snapshot,
            noise=noise,
            target_slots=target_slots,
            include_effect=include_effect,
            record=False,
            headless=True,
            max_time=max_time
        )
        if out['hit']:
            hits += 1
    return hits / float(n_simulations)


if __name__ == '__main__':
    pass