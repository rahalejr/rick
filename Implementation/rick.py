from concurrent.futures import ProcessPoolExecutor, as_completed

import json
import os
import numpy as np
import pandas as pd

from conditions import Condition
from simulation import run, monte_carlo_goal_probability

debug = False

mapping_simulations = 200
mapping_noise = 6
max_workers = 8
effect_slot = -1


def process_conditions(conds_list, output_file='rick_output.csv'):
    table = []

    payloads = []
    for i, c in enumerate(conds_list):
        stim_index = c.get('index', i)
        payloads.append((c, stim_index))

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(run_condition, p) for p in payloads]
        results = [f.result() for f in as_completed(futures)]

    for stim_index, rows in sorted(results, key=lambda x: x[0]):
        table.extend(rows)

    df = pd.DataFrame(table).sort_values(['stimulus', 'ball_index'], kind='mergesort').reset_index(drop=True)
    df.to_csv(output_file, index=False)
    return df


def run_condition(payload):
    c, stim_index = payload

    np.random.seed((os.getpid() * 1000003 + stim_index) % (2**32))

    cond = Condition(
        index=stim_index,
        angles=c['angles'],
        preemption=c['preemption'],
        jitter=c['jitter'],
        ball_positions=c['ball_positions'],
        filename=c['filename'],
        order=c['order']
    )

    actual_output = run(cond, record=False, headless=(not debug))

    chain = build_causal_chain(actual_output, effect_slot=effect_slot)
    score_by_slot = score_chain(actual_output, chain)

    slot_to_ball_index = {
        cond.ball_positions[i]: i + 1
        for i in range(cond.num_balls)
    }

    score_by_ball = {}
    for slot, score in score_by_slot.items():
        ball_index = slot_to_ball_index.get(slot)
        if ball_index is not None:
            score_by_ball[ball_index] = score

    results = []
    for b in range(cond.num_balls):
        ball_index = b + 1
        row = {
            'stimulus': cond.index,
            'ball_index': ball_index,
            'order': cond.order.index(ball_index) + 1,
            'RICK': score_by_ball.get(ball_index, 0.0)
        }
        results.append(row)

    return stim_index, results


def build_causal_chain(actual_output, effect_slot=-1):
    collisions = actual_output.get('collisions', [])

    indexed = []
    for idx, c in enumerate(collisions):
        if c.get('collider') is None:
            continue
        if c.get('collided') is None:
            continue
        if c.get('snapshot_id') is None:
            continue
        indexed.append((idx, c))

    chain = []
    target = effect_slot
    before_key = None

    while True:
        candidates = []
        for idx, c in indexed:
            key = (c['step'], idx)
            if c['collided'] != target:
                continue
            if before_key is not None and not (key < before_key):
                continue
            candidates.append((key, c))

        if not candidates:
            break

        candidates.sort(key=lambda x: x[0])
        _, chosen = candidates[-1]
        chain.append(chosen)
        target = chosen['collider']
        chosen_idx = collisions.index(chosen)
        before_key = (chosen['step'], chosen_idx)

    return chain


def score_chain(actual_output, chain):
    raw_scores = {}
    ease_cache = {}

    for collision in chain:
        collider = collision.get('collider')
        magnitude = float(collision.get('magnitude') or 0.0)
        snapshot_id = collision.get('snapshot_id')

        if collider is None or snapshot_id is None:
            continue

        if snapshot_id not in ease_cache:
            snapshot = actual_output['snapshots'][snapshot_id]
            ease_cache[snapshot_id] = monte_carlo_goal_probability(
                snapshot=snapshot,
                n_simulations=mapping_simulations,
                noise=mapping_noise,
                target_slots=None,
                include_effect=False
            )

        ease = ease_cache[snapshot_id]
        score = magnitude * ease

        if collider not in raw_scores:
            raw_scores[collider] = 0.0
        raw_scores[collider] += score

    total = sum(raw_scores.values())

    if total > 0:
        normalized_scores = {
            ball: (score / total) * 100.0
            for ball, score in raw_scores.items()
        }
    else:
        normalized_scores = {}

    return normalized_scores


if __name__ == '__main__':
    filename = 'collisions.json'
    with open(filename, 'r') as f:
        data = json.load(f)

    process_conditions(data)