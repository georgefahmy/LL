import json
import os
import random

from dotmap import DotMap


def generate_random_day(all_data, seed=None):
    random_list = []
    if seed:
        random.seed(seed)
    while len(random_list) < 6:
        random_list.append(random.choice(list(all_data.keys())))
        random_list = list(set(random_list))
    chosen = DotMap()
    for x in random_list:
        chosen[x] = all_data[x]
    return chosen


datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
all_data = DotMap()
if os.path.isfile(datapath):
    with open(datapath, "r") as fp:
        all_data = DotMap(json.load(fp))

seed = None
days_questions = generate_random_day(all_data, seed=seed)
days_questions.pprint(pformat="json")

# TODO build layout similar to LL interface with above questions as input
# TODO make it so the questions are selected at the start of the day and don't change?
# TODO dont worry about metrics part
# TODO create a folder (if not exist) that stores answers for questions/days and generate metrics.
# TODO experiment - Do this with a database? make it online accessible for online competitions?
# TODO future - expand available questions to include all questions in oneday and mini league sources
