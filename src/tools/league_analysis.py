import json
import os

import pandas as pd
from dotmap import DotMap


def load_data(file=None, user=None):
    if user:
        filename = f"/.LearnedLeague/user_data/{user}.json"
    if file:
        filename = f"/.LearnedLeague/{file}"
    full_file = os.path.expanduser("~") + filename
    try:
        with open(full_file, "r") as fp:
            if full_file.endswith("csv"):
                return pd.read_csv(fp)
            elif full_file.endswith("json"):
                return DotMap(json.load(fp))
            else:
                return DotMap()
    except Exception as e:
        print(e)
        return DotMap()


if __name__ == "__main__":

    all_data_file = "all_data.json"
    season = 102
    all_data = load_data(file=all_data_file)

    cat_data = DotMap()
    for question in all_data.values():
        cat_data[question["category"]] += 1

    cat_df = pd.Series(cat_data.toDict()).sort_values(ascending=False)
    norm_df = round(cat_df / cat_df.sum() * 100, 3)

    data = pd.DataFrame([cat_df, norm_df], index=["Total", "% of Qs"]).transpose()
    current_season = (
        pd.DataFrame(all_data).transpose().filter(like=f"S{season}", axis=0)
    )

    cat_specific_data = DotMap()
    for question in all_data.values():
        cat = question.category
        if type(question) is not DotMap:
            continue
        if not len(cat_specific_data[cat]):
            cat_specific_data[cat] = []
        cat_specific_data[cat].append(int(question.percent))

    data["Avg Correct"] = (
        pd.DataFrame(cat_specific_data.values(), index=cat_specific_data.keys())
        .transpose()
        .mean()
    )
    data["Median Cor"] = (
        pd.DataFrame(cat_specific_data.values(), index=cat_specific_data.keys())
        .transpose()
        .median()
    )

    data.sort_values(by="Avg Correct", ascending=False)
