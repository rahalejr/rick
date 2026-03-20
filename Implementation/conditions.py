import numpy as np


width = 1000
height = 800
ball_radius = 28

class Condition:

    def __init__(self, angles, ball_positions, preemption=False, unambiguous=False, jitter=None, filename='', order=[-1,-1,-1], index=-1):
        self.num_balls = len(angles)
        
        self.y_positions = []
        spacing = height / 6

        for i in ball_positions:
            self.y_positions.append(round(spacing*i))
        self.order = order
        self.ball_positions = ball_positions
        self.angles = angles
        self.radians = [ang*np.pi/180 for ang in angles]
        self.preemption = preemption
        self.cause_ball = None
        self.collisions = 0
        self.unambiguous = unambiguous
        self.sim_time = None
        self.diverge = 0
        self.noise_ball = None
        self.filename = filename
        self.index = index

        if not jitter:
            jitter_scale = 20 if self.num_balls > 2 else 50
            max_jitter = spacing - (ball_radius * 2)
            self.jitter = {
                'x': list(np.clip(np.random.normal(loc=0, scale=jitter_scale, size=self.num_balls), -max_jitter, max_jitter)),
                'y': list(np.clip(np.random.normal(loc=0, scale=jitter_scale, size=self.num_balls), -max_jitter, max_jitter))
            }
        else:
            self.jitter = jitter

    def adjust_angle(self, deg, index):
        self.angles[index] += deg
        self.radians[index] = self.angles[index]*np.pi/180

    
    def info(self):
        return {
            'num_balls': self.num_balls,
            'angles': self.angles,
            'preemption': self.preemption,
            'cause_ball': self.cause_ball,
            'collisions': self.collisions,
            'unambiguous': self.unambiguous,
            'jitter': self.jitter
        }

