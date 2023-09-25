import json
import os
from pprint import pprint

from dotmap import DotMap

file = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"

data = DotMap(json.load(open(file)))


def rundle_percent_correct(rundle):
    if rundle not in ["A", "B", "C", "D", "E", "R", "ALL"]:
        return False
    categories = DotMap()
    for question in data.values():
        if rundle == "ALL":
            rundle = "percent"
        categories[question.category].percent += round(float(question[rundle]), 3)
        categories[question.category].total += 1
    for category in categories.keys():
        categories[category] = categories[category].percent / categories[category].total
    percent_correct = sum([val for val in categories.values()]) / len(categories.keys())
    pprint(sorted(categories.items(), key=lambda x: x[1], reverse=True))
    return percent_correct


rundle_percent_correct("A")
