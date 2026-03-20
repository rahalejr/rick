from conditions import Condition
from random import shuffle
import numpy as np
import pygame
import os
from moviepy.editor import ImageSequenceClip
from Box2D import (b2World, b2PolygonShape, b2CircleShape, b2ContactListener, b2_staticBody, b2_dynamicBody)
import shutil
import math

digits = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]

# global parameters
width = 1000
height = 800
ball_radius = 28
border_width = 11
margin = 15
speed = 300
framerate = 30
time_step = 0.0001
gate_gap_height = 225

# radomly assign ball colors
red, green, yellow, blue, purple = (255, 0, 0), (20, 82, 20), (255, 255, 0), (0, 0, 255), (128, 0, 128)
colors = [green, red, yellow, blue, purple]

# fix this redundancy
col_dict = {
    'red': (255, 0, 0),
    'green': (20, 82, 20),
    'yellow': (255, 255, 0),
    'blue': (0, 0, 255),
    'purple': (128, 0, 128)
}

# Flip keys and values for reverse lookup
rgb_to_name = {v: k for k, v in col_dict.items()}


class Simulation:
    def __init__(self, balls, counterfactual = False, actual_data = None, noise=6):
        self.balls = balls
        if actual_data:
            self.actual_collisions = actual_data['collisions']
        else:
            self.actual_collisions = []
        self.num_balls = len(balls)-1
        self.counterfactual = True if counterfactual else False
        self.hit = False
        self.noise = noise
        self.collisions = []
        self.cause_ball = ''
        self.step = 0
        self.sim_seconds = 0

        self.pending_noise = []
    
    def find_ball(self, position):
        for ball in self.balls:
            if ball.slot == position:
                return ball
        return None


class Ball:
    def __init__(self, world, params):
        self.name = params['ball']
        xpos = round(width / 4) if self.name == 'effect' else width + 30 + params['x_jitter']

        self.body = world.CreateDynamicBody(position=(xpos, params['ypos']),shapes=b2CircleShape(radius=ball_radius))

        self.body.fixtures[0].restitution = 1.0
        self.body.fixtures[0].friction = 0
        self.body.linearDamping = 0
        self.body.linearVelocity = (0, 0) if self.name == 'effect' else (speed * np.cos(params['angle']), speed * np.sin(params['angle']))
        self.color = params['rgb']
        self.slot = params['position']
        self.noisy = False
        self.collided_with = set()
        self.ball_collisions = []
        self.all_collisions = []
        self.body.userData = self

    @property
    def position(self):
        return tuple(map(int, self.body.position))
    
    def add_collision(self, obj, step, time):
        if obj == 'wall':
            self.all_collisions.append({'name': 'wall', 'object': obj, 'step': step, 'time': time})
        elif isinstance(obj, Ball):
            if obj.noisy:
                    self.noisy = True
            # if obj.name != 'effect' and 'effect' not in self.collided_with:
            self.ball_collisions.append({'name': obj.name, 'object': obj, 'step': step, 'time': time})
            self.collided_with.add(obj.name)
            self.all_collisions.append({'name': obj.name, 'object': obj, 'step': step, 'time': time})
    
    def last_collision(self):
        return self.ball_collisions[-1]['object'] if len(self.ball_collisions) > 0 else None

    def rotate_velocity(self, theta):
        vx, vy = self.body.linearVelocity
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        new_vx = vx * cos_t - vy * sin_t
        new_vy = vx * sin_t + vy * cos_t
        self.body.linearVelocity = (new_vx, new_vy)


    def add_noise(self, noise=6):
        z = gaussian_noise(1)
        angle_deg = z * noise
        print(angle_deg, self.name)
        angle_rad = angle_deg * (math.pi / 180)

        self.rotate_velocity(angle_rad)
        self.noisy = True

class CollisionListener(b2ContactListener):
    def __init__(self, sim):
        super().__init__()
        self.events = []
        self.sim = sim

    def BeginContact(self, contact):
        A = contact.fixtureA.body.userData
        B = contact.fixtureB.body.userData
        between = {A.slot if isinstance(A, Ball) else 'wall', B.slot if isinstance(B, Ball) else 'wall'}

        if self.sim.actual_collisions:
            matching = False
            for collision in self.sim.actual_collisions:
                if collision['step'] == self.sim.step and collision['objects'] == between:
                    matching = True
                    break
            if not matching:
                print('noise add')
                for obj in [A,B]:
                    if isinstance(obj, Ball):
                        self.sim.pending_noise.append(obj)

        positions, noisy = [], False
        if isinstance(A, Ball):
            A.add_collision(B, self.sim.step, self.sim.sim_seconds)
            positions.append(A.slot)
        else:
            positions.append('wall')
        
        if isinstance(B, Ball):
            B.add_collision(A, self.sim.step, self.sim.sim_seconds)
            positions.append(B.slot)
        else:
            positions.append('wall')

        self.sim.collisions.append({'objects': set(positions), 'step': self.sim.step})


def rotate_velocity(body, theta):
    vx, vy = body.linearVelocity
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    new_vx = vx * cos_t - vy * sin_t
    new_vy = vx * sin_t + vy * cos_t
    body.linearVelocity = (new_vx, new_vy)

def draw_checkerboard_square(surface, center, side, num_checks=16):
    x0, y0 = center
    half = (side // 2) + 5
    check_size = side // num_checks
    colors = [(200, 200, 200), (255,255,255)]

    for row in range(num_checks):
        for col in range(num_checks):
            c = colors[(row+col)%2]
            rect = pygame.Rect(
                x0 - half + col*check_size,
                y0 - half + row*check_size,
                check_size,
                check_size
            )
            pygame.draw.rect(surface, c, rect)

# wall geom constants
left_edge_x = margin + border_width / 2
top_edge_y = margin + border_width / 2
bottom_edge_y = height - margin - border_width / 2
wall_len = (height - gate_gap_height - 2 * margin) / 2
wall_half_len = wall_len / 2

def gaussian_noise(standard_dev):
	u = 1 - np.random.random()
	v = 1 - np.random.random()
	return standard_dev * np.sqrt(-2*np.log(u)) * np.cos(2 * np.pi * v)

def create_world():
    world = b2World(gravity=(0, 0), doSleep=True)

    wall_shapes = [
        ((left_edge_x, margin + wall_half_len), b2PolygonShape(box=(border_width/2, wall_half_len))),
        ((left_edge_x, height - margin - wall_half_len), b2PolygonShape(box=(border_width/2, wall_half_len))),
        ((width / 2, top_edge_y), b2PolygonShape(box=((width - 2*margin)/2, border_width/2))),
        ((width / 2, bottom_edge_y), b2PolygonShape(box=((width - 2*margin)/2, border_width/2))),
    ]

    for position, shape in wall_shapes:
        body = world.CreateStaticBody(position=position)
        fixture = body.CreateFixture(shape=shape)
        fixture.restitution = 1.0
        fixture.friction = 0.0
        body.userData = 'wall'

    return world


def is_hit(sim, effect_ball, sim_seconds):
    effect_x = effect_ball.body.position[0]
    if effect_x < -5:
        final_pos = effect_ball.body.position[1]
        sim.hit = True
        return sim_seconds, final_pos
    return False, 0


def run(condition, pause = 10, actual_data = None, noise = 6, cause_color='red', cause_ball = 1, record=False, counterfactual=None, headless=False, clip_num=1, is_cf = False):
    ball_colors = [colors[i-1] for i in condition.ball_positions]

    # ball parameters
    ball_params = [{'ball': 'effect', 'rgb': (180, 180, 180), 'ypos': round(height / 2), 'angle': 0, 'position': -1}]
    for i in range(len(ball_colors)):
        ball_params.append({'ball': i+1, 'rgb': ball_colors[i], 'position': condition.ball_positions[i]})

    if record:
        shutil.rmtree("frames") if os.path.exists("frames") else None
        os.makedirs("frames")

    if not headless:
        pygame.init()
        screen = pygame.display.set_mode((width, height), display = 1)
        clock = pygame.time.Clock()

    remove = counterfactual['remove'] if counterfactual else None
    frame_count = 0
    world = create_world()

    for i in range(condition.num_balls):
        ball_params[i + 1]['ypos'] = condition.y_positions[i] + condition.jitter['y'][i]
        ball_params[i + 1]['angle'] = condition.radians[i]
        ball_params[i + 1]['y_jitter'] = condition.jitter['y'][i]
        ball_params[i + 1]['x_jitter'] = condition.jitter['x'][i]

    filtered_params = [params for params in ball_params[0:condition.num_balls + 1] if not (remove == params['ball'])]

    balls = []
    for i, params in enumerate(filtered_params):
        ball = Ball(world, params)
        if ball.name == 'effect':
            effect_ball = ball
        balls.append(ball)

    sim = Simulation(balls, remove, actual_data = actual_data, noise=noise)
    collision_listener = CollisionListener(sim)
    world.contactListener = collision_listener 

    moving_ball = sim.balls[1] if len(sim.balls) > 1 else None

    effect_start_pos = (effect_ball.body.position[0], effect_ball.body.position[1])
    moving_start_pos = (moving_ball.body.position[0], moving_ball.body.position[1]) if moving_ball else None

    initial_distance_to_effect = math.sqrt(
    (moving_start_pos[0] - effect_start_pos[0])**2 +
    (moving_start_pos[1] - effect_start_pos[1])**2
    ) if moving_ball else None

    running, hit = True, False
    sim_seconds = 0
    final_pos = round(height / 2)
    SIM_FRAME_TIME = 1.0 / framerate

    while running:

        if not hit:
            hit, final_pos = is_hit(sim, effect_ball, sim_seconds)

        steps = int(SIM_FRAME_TIME / time_step)

        for _ in range(steps):
            world.Step(time_step, 20, 10)

            sim.step        += 1
            sim.sim_seconds += time_step
            sim_seconds     += time_step


            if sim.pending_noise:
                for b in set(sim.pending_noise):
                    b.add_noise(sim.noise)
                sim.pending_noise.clear()

            if actual_data:
                actual_collisions = actual_data['collisions']
                cf_currents = [c for c in sim.collisions if c['step'] == sim.step - 1]

                for ac in actual_collisions:
                    if sim.step - ac['step'] == 1:
                        matched = any(cf['objects'] == ac['objects'] for cf in cf_currents)
                        if not matched:
                            for obj in ac['objects']:
                                b = sim.find_ball(obj)
                                if isinstance(b, Ball):
                                    sim.pending_noise.append(b)


        if (hit and sim_seconds > hit + 2) or sim_seconds > 6:
            break

        if not headless:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            screen.fill((255, 255, 255))


            draw_checkerboard_square(screen, [effect_start_pos[0]+6, effect_start_pos[1]+6], side=ball_radius * 2 + 12)

            vert_wall_len = (height - gate_gap_height - 2 * margin) / 2

            pygame.draw.rect(screen, (0, 0, 0), (margin, margin, border_width, vert_wall_len))
            pygame.draw.rect(screen, (0, 0, 0), (margin, height - margin - vert_wall_len, border_width, vert_wall_len))
            pygame.draw.rect(screen, (0, 0, 0), (margin, margin, width - margin, border_width))
            pygame.draw.rect(screen, (0, 0, 0), (margin, height - margin - border_width, width - margin, border_width))
            pygame.draw.rect(screen, (255, 130, 150), (margin, margin + vert_wall_len, border_width, gate_gap_height))

            for ball in balls:
                pygame.draw.circle(screen, (0, 0, 0),
                                    (int(ball.body.position[0]), int(ball.body.position[1])),
                                    ball_radius + 1)
                pygame.draw.circle(screen, ball.color,
                                    (int(ball.body.position[0]), int(ball.body.position[1])),
                                    ball_radius)

            if record:
                pygame.image.save(screen, f"frames/frame_{frame_count:05d}.png")

            frame_count += 1
            pygame.display.flip()
            clock.tick(framerate)

    if not headless:
        pygame.quit()


    if record:
        frames = sorted([os.path.join("frames", fname) for fname in os.listdir("frames") if fname.endswith(".png")])
        clip = ImageSequenceClip(frames, fps=framerate)
        clip.write_videofile(condition.filename, codec="libx264")


    cause_ball = effect_ball.last_collision()


    return {
        'num_balls': sim.num_balls,
        'angles': condition.angles,
        'sim_time': sim_seconds,
        'hit': isinstance(hit, float),
        'cause_ball': cause_ball.name if cause_ball else None,
        'cause_collisions': cause_ball.all_collisions if cause_ball else None,
        'colors': [rgb_to_name[c] for c in ball_colors],
        'final_pos': final_pos,
        'collisions': sim.collisions
    }

if __name__ == '__main__':
    pass

