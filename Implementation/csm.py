from concurrent.futures import ProcessPoolExecutor, as_completed

import os
import json
import copy
import numpy as np
import pandas as pd
from simulation_csm import run, gaussian_noise
from conditions import Condition

debug = False

n_simulations = 1000
perturb_simulations = 100
perturb = 3


def process_conditions(conds_list):
    table = []

    payloads = []
    for i, c in enumerate(conds_list):
        stim_index = c.get('index', i)
        payloads.append((c, stim_index))

    with ProcessPoolExecutor(max_workers=8) as ex:
        futures = [ex.submit(run_condition, p) for p in payloads]
        results = [f.result() for f in as_completed(futures)]

    for stim_index, rows in sorted(results, key=lambda x: x[0]):
        table.extend(rows)

    df = pd.DataFrame(table).sort_values(['stimulus', 'ball_index'], kind='mergesort').reset_index(drop=True)
    df.to_csv('csm_output.csv', index=False)


def run_condition(payload):
    c, stim_index = payload
    cond = Condition(
        index           = stim_index,
        angles          = c['angles'],
        preemption      = c['preemption'],
        jitter          = c['jitter'],
        ball_positions  = c['ball_positions'],
        filename        = c['filename'],
        order           = c['order']
    )

    results = []

    actual_output=run(cond, record=False, counterfactual=None, headless=(not debug))


    diff_maker_balls = []
    for c in range(cond.num_balls):
        print('DM ', c)
        diff_maker_balls += [difference_maker(actual_output, cond, c)]
            
    # whether cause
    whether_balls = []
    for c in range(cond.num_balls):
        print('whether ', c)
        whether_balls+= [whether(actual_output, cond, c)]

    # how cause
    how_balls = []
    for c in range(cond.num_balls):
        print('how ', c)
        how_balls += [how(actual_output, cond, c)]
    
    # sufficient cause
    sufficient_balls = []
    for c in range(cond.num_balls):
        print('sufficient ', c)
        sufficient_balls += [sufficient(actual_output,cond, c)]

    #robust cause
    robust_balls = []
    for c in range(cond.num_balls):
        print('robust ', c)
        robust_balls += [robust(actual_output, cond, c)]
    
    for b in range(cond.num_balls):
        row = {
            'stimulus': cond.index,
            'ball_index': b+1,
            'order': cond.order.index(b + 1) + 1,
            'DM': diff_maker_balls[b],
            'HOW': how_balls[b],
            'WHETHER': whether_balls[b],
            'SUFFICIENT': sufficient_balls[b],
            'ROBUST': robust_balls[b]
        }
        results.append(row)
    return stim_index, results

def difference_maker(actual_output, cond, c):
    new_cond = remove_ball(cond,c)
    outcomes = []
    for _ in range(0,n_simulations):
        output = run(new_cond, actual_data=actual_output, record=False, counterfactual=None, headless=(not debug))
        outcomes.append((output['final_pos'], output['sim_time']) != (actual_output['final_pos'] , actual_output['sim_time']))
    return sum(outcomes)/float(n_simulations)
         
def whether(actual_output, cond, c, num_sims=n_simulations):
    new_cond = remove_ball(cond,c)
    outcomes = []
    for _ in range(0,num_sims):
        output = run(new_cond, actual_data=actual_output,record=False, counterfactual=None, headless=(not debug))
        outcomes.append(actual_output['hit']!= output['hit'])
    return sum(outcomes)/float(num_sims)
    
def how(actual_output, cond, c):
    outcomes = []
    for _ in range(0, perturb_simulations):
        new_cond = change_ball(cond,c)
        output = run(new_cond, actual_data=actual_output, record=False, counterfactual=None, headless=(not debug))
        outcomes.append((output['final_pos'], output['sim_time']) != (actual_output['final_pos'] , actual_output['sim_time']))
    return sum(outcomes)/float(perturb_simulations)

def sufficient(actual_output, cond, c):
    new_cond = remove_others(cond, c)
    outcomes = []
    for _ in range(0,n_simulations):
        output = run(new_cond, actual_data=actual_output, record=False, counterfactual=None, headless=(not debug))
        # this is effectively the whether cause, comparing to all cause balls removed (always false)
        outcomes.append(output['hit'])
    return sum(outcomes)/float(n_simulations)

def robust(actual_output, cond, c):
    outcomes = []
    for _ in range(0,perturb_simulations):
        new_cond = change_others(cond,c)
        new_actual = run(new_cond, record=False, counterfactual=None, headless=(not debug))
        cond_whether = remove_ball(new_cond, c)
        new_whether = run(cond_whether, actual_data=new_actual, record=False, counterfactual=None, headless=(not debug))
        # if goal still occurs when changing others
        outcomes.append(new_whether['hit'] == False and new_actual['hit'] == True)
    return sum(outcomes)/float(perturb_simulations)

def remove_ball(cond, c):
    new_cond = copy.deepcopy(cond)

    del new_cond.angles[c]
    del new_cond.y_positions[c]
    del new_cond.radians[c]
    del new_cond.jitter['x'][c]
    del new_cond.jitter['y'][c]
    del new_cond.ball_positions[c]
    del new_cond.order[c]
    new_cond.num_balls -= 1

    return new_cond

def remove_others(cond, c):
    new_cond = copy.deepcopy(cond)
    inds = list(range(cond.num_balls))
    inds.pop(c)
    inds = sorted(inds, reverse=True)
    for i in inds:
        del new_cond.angles[i]
        del new_cond.y_positions[i]
        del new_cond.radians[i]
        del new_cond.jitter['x'][i]
        del new_cond.jitter['y'][i]
        del new_cond.order[i]
        del new_cond.ball_positions[i]
    
    new_cond.num_balls = 1
    
    return new_cond

def change_ball(cond, c):
    new_cond = copy.deepcopy(cond)
    new_cond.jitter['x'][c] += gaussian_noise(1)*perturb
    new_cond.jitter['y'][c] += gaussian_noise(1)*perturb
    return new_cond

def change_others(cond, c):
    new_cond = copy.deepcopy(cond)
    for i in range(cond.num_balls):
        if i != c :
            new_cond.jitter['x'][i] += gaussian_noise(1)*perturb
            new_cond.jitter['y'][i] += gaussian_noise(1)*perturb
    return new_cond


if __name__ == '__main__':
    filename = 'collisions.json'
    with open(filename, 'r') as f:
        data = json.load(f)

    process_conditions(data)