import sys
import os
import json
import argparse
import pandas as pd
import numpy as np
from scipy.stats import rankdata
from statsmodels.formula.api import ols

def norm_vars(data, normalize_vars):
    for var in normalize_vars:
        norm_var = f"norm_{var}"
        data[norm_var] = data.groupby("Rundle")[var].transform(
            lambda x: (x - x.mean()) / (x.std() if x.std() != 0 else 1)
        )
    return data

def calculate_luck_data(data, formula):
    normalize_vars = ["OE", "DE", "QPct", "CAA", "FL", "MPD", "TCA", "SOS"]
    data["Level"] = data["Rundle"].str[0]
    data["Matches"] = data["W"] + data["L"] + data["T"]
    data["Played"] = data["Matches"] - data["FL"]
    data["Player_count"] = data.groupby("Rundle")["Rundle"].transform("count")
    data["SOS"] = data["CAA"] / (
        6
        * (data["Matches"] - data["FW"])
        * data.groupby("Rundle")["QPct"].transform("mean")
    )
    data = norm_vars(data, normalize_vars)
    model = ols(formula, data=data).fit()
    
    mean_rundle_size = (
        data.groupby("Rundle", as_index=True)
        .agg({"Player": lambda x: len(set(x))})
        .mean()
        .astype(float)
    ).Player

    data["Exp_PTS"] = model.predict(data)
    data = data.replace([np.inf, -np.inf, np.nan, "--"], 0)
    data["Exp_Rank"] = (
        data.groupby("Rundle")["Exp_PTS"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    data["Luck"] = data["PTS"] - data["Exp_PTS"]
    data["Luck_Rank"] = (data["Exp_Rank"] - data["Rank"]).astype(int)
    data["Luck_Rank_adj"] = (
        data["Luck_Rank"] / data["Player_count"]
    ) * mean_rundle_size

    data["LuckPctile"] = (
        rankdata(data["Luck_Rank_adj"], method="max") / len(data) * 100
    ).round(2)
    data.sort_values(by="LuckPctile", ascending=False, inplace=True)
    return data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", required=True, help="Path to the leaguewide stats CSV file")
    parser.add_argument("-u", "--usernames", nargs="+", default=[])
    parser.add_argument("-r", "--rundle", action="store_true", default=False)
    args = parser.parse_args()

    try:
        if not os.path.isfile(args.file):
            print(json.dumps({"success": False, "error": f"CSV file not found: {args.file}"}))
            return

        data = (
            pd.read_csv(args.file, encoding="latin1", low_memory=False)
            .set_index("Player", drop=False)
            .rename(
                columns={
                    "Wins": "W",
                    "Losses": "L",
                    "Ties": "T",
                    "Pts": "PTS",
                    "Rundle Rank": "Rank",
                }
            )
        )
        data = data.replace([np.inf, -np.inf, np.nan, "--"], 0)
        data = data.convert_dtypes()
        
        formula = "PTS ~ 0 + Played + norm_OE*FL + norm_QPct*FL + norm_DE"
        data = calculate_luck_data(data, formula=formula)
        
        fields = [
            "Player", "W", "L", "T", "QPct", "TCA", "CAA", 
            "PTS", "Exp_PTS", "Luck", "LuckPctile", "Rank", "Exp_Rank", "Rundle"
        ]
        
        if args.rundle and args.usernames:
            user_rundles = []
            for u in args.usernames:
                if u in data.index:
                    user_rundles.append(data.loc[u]["Rundle"])
            
            luck_data = data[data["Rundle"].isin(user_rundles)][fields]
        elif args.usernames:
            valid_users = [u for u in args.usernames if u in data.index]
            luck_data = data.loc[valid_users][fields]
        else:
            luck_data = data[fields]
            
        luck_data = luck_data.round(3)
        records = luck_data.to_dict(orient="records")
        print(json.dumps({
            "success": True, 
            "data": records
        }))
        
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == "__main__":
    main()
