import os

import numpy as np
import pandas as pd
import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from scipy.stats import rankdata
from statsmodels.formula.api import ols

from src.constants import ALL_DATA_BASE_URL, BASE_URL
from src.logged_in_tools import login
from src.userdata import load


def get_current_season(season=None):
    if season:
        url = BASE_URL + f"/allrundles.php?{season}"
    else:
        url = BASE_URL + "/allrundles.php"
    page = bs(requests.get(url).content, "html.parser")
    current_season = int(page.find("h1").text.split(":")[0].replace("LL", ""))
    matchday_table = page.find("table", {"class": "MDTable"}).find_all("tr")[1:-1]
    if (matchday_table[-1].find_all("td")[-1].text).isnumeric():
        current_matchday = (
            matchday_table[-1].find_all("td")[0].text.replace(" ", "_").lower()
        )
    else:
        current_matchday = (
            matchday_table[
                [i for i, row in enumerate(matchday_table) if len(row) < 12][0]
            ]
            .find("td")
            .text.replace(" ", "_")
            .lower()
        )
    return (current_season, current_matchday)


def get_leaguewide_data(season=None):
    current_season, current_matchday = get_current_season(season)
    if not season:
        season = current_season
    player_stats_url = ALL_DATA_BASE_URL.format(season)
    file = (
        os.path.expanduser("~")
        + "/.LearnedLeague/"
        + f"LL{season}_Leaguewide_{current_matchday}.csv"
    )
    if not os.path.isfile(file):
        with open(file, "wb+") as out_file:
            sess = login()
            content = sess.get(player_stats_url, stream=True).content
            out_file.write(content)
    data = (
        pd.read_csv(file, encoding="latin1", low_memory=False)
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
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors="ignore")
    return data


# def get_stats_data(season, rundle):
#     base_standings = f"{BASE_URL}/standings.php?{season}&{rundle}"
#     table = (
#         bs(
#             sess.get(base_standings).content,
#             "html.parser",
#         )
#         .find("table", {"class": "sortable std"})
#         .find_all("tr")
#     )
#     header_row = [val.text.strip() for val in table[0].find_all("td")]
#     rundle_data = []
#     for row in table[1:]:
#         row_data = {}
#         cells = row.find_all("td")
#         for i, val in enumerate(cells):
#             row_data[header_row[i]] = val.text.strip()
#         rundle_data.append(row_data)
#     data = pd.DataFrame(rundle_data).set_index("Player", drop=False)
#     data["Rundle"] = rundle
#     del data[""]
#     for col in data.columns:
#         data[col] = pd.to_numeric(data[col], errors="ignore")
#     return data


# def calc_luck(data):
#     count_stats = ["Rundle", "Player"]
#     sum_stats = ["Rundle", "FL", "FW", "TCA", "QPlayed"]
#     data["Matches"] = data["W"] + data["L"] + data["T"]
#     data["Played"] = data["Matches"] - data["FL"]
#     data["FPct"] = data["FL"] / data["Matches"]
#     data["QPlayed"] = 6 * data["Played"]
#     count = (
#         data[count_stats]
#         .groupby("Rundle", as_index=False)
#         .count()
#         .rename(columns={"Player": "Player_count"})
#     )
#     sum_data = (
#         data[sum_stats]
#         .groupby("Rundle", as_index=False)
#         .sum()
#         .rename(
#             columns={"FL": "rFL", "FW": "rFW", "TCA": "rTCA", "QPlayed": "rQPlayed"}
#         )
#     )
#     data = data.merge(count)
#     data = data.merge(sum_data)
#     data["xFW"] = (
#         ((data["rFL"] - data["FL"]) / (data["Player_count"] - 1)) / data["Matches"]
#     ) * data["Played"]
#     data["xTMP"] = data["TMP"] * (data["Played"] - data["xFW"]) / data["Played"]
#     data["rQPCT"] = (data["rTCA"] - data["TCA"]) / (data["rQPlayed"] - data["QPlayed"])
#     data["xCAA"] = data["rQPCT"] * 6 * (data["Played"] - data["xFW"])
#     data["xMPA"] = data["PCAA"] * data["rQPCT"] * 6 * (data["Played"] - data["xFW"])
#     data["SOS"] = data["CAA"] / (6 * (data["Matches"] - data["FW"]) * data["rQPCT"])
#     data["PWP"] = 1 / (1 + (data["xMPA"] / data["xTMP"]) ** 1.93)
#     data["xPTS"] = (
#         (2 * data["PWP"] * (data["Played"] - data["xFW"]))
#         + (2 * data["xFW"])
#         - data["FL"]
#     )
#     data["xRank"] = (
#         pd.to_numeric(
#             data.groupby("Rundle")["xPTS"].rank(method="dense", ascending=False),
#             errors="coerce",
#         )
#         .replace(np.nan, 0)
#         .astype(int)
#     )
#     data["Luck"] = data["PTS"] - data["xPTS"]
#     data["Luck_Rank"] = (data["Rank"] - data["xRank"]).astype(int)
#     data["LuckPctile"] = (
#         (data.groupby("Rundle")["Luck_Rank"].rank() - 1) / data["Player_count"] * 100
#     )
#     data.set_index("Player", inplace=True, drop=False)
#     return data


def stats_model_luck(data_df):
    normalize_vars = ["OE", "DE", "QPct", "CAA"]
    data_df["Level"] = data_df["Rundle"].str[0]
    data_df["Matches"] = data_df["W"] + data_df["L"] + data_df["T"]
    data_df["Played"] = data_df["Matches"] - data_df["FL"]
    data_df["Player_count"] = data_df.groupby("Rundle")["Rundle"].transform("count")
    for var in normalize_vars:
        norm_var = f"norm_{var}"
        data_df[norm_var] = data_df.groupby("Rundle")[var].transform(
            lambda x: (x - x.mean()) / x.std()
        )
    formula = "PTS ~ norm_QPct + norm_OE + norm_DE + Played + FL + FL:norm_OE + FL:norm_QPct + 0"
    model = ols(formula, data=data_df).fit()
    data_df["xPTS"] = model.predict(data_df)
    data_df["xRank"] = (
        data_df.groupby("Rundle")["xPTS"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    data_df["SOS"] = data_df["CAA"] / (
        6
        * (data_df["Matches"] - data_df["FW"])
        * data_df.groupby("Rundle")["QPct"].transform("mean")
    )
    data_df["Luck"] = data_df["PTS"] - data_df["xPTS"]
    data_df["Luck_Rank"] = (data_df["xRank"] - data_df["Rank"]).astype(int)
    data_df["LuckPctile"] = rankdata(data_df["Luck"], method="max") / len(data_df) * 100
    data_df.sort_values(by="LuckPctile", ascending=False, inplace=True)
    return data_df


def predict(user1, user2, data, sess=None):
    data["xPPM"] = data["PCA"] * data["TCA"] / data["Matches"]
    user1 = load(username=user1, sess=sess)
    user1.stats.total["Matches"] = (
        int(user1.stats.total.W) + int(user1.stats.total.T) + int(user1.stats.total.L)
    )
    user1.stats.total["xPPM"] = int(user1.stats.total.TMP) / user1.stats.total.Matches
    user2 = load(username=user2, sess=sess)
    user2.stats.total["Matches"] = (
        int(user2.stats.total.W) + int(user2.stats.total.T) + int(user2.stats.total.L)
    )
    user2.stats.total["xPPM"] = int(user2.stats.total.TMP) / user2.stats.total.Matches
    print(data.loc[user1.formatted_username]["xPPM"])
    print(data.loc[user2.formatted_username]["xPPM"])
    return


def specifc_user_field(data, usernames, fields, rundle=False):
    try:
        if rundle:
            rundle = data.loc[usernames]["Rundle"]
            if "Rundle" not in fields:
                fields.append("Rundle")
            luck_data = (data[data["Rundle"].isin(rundle)][fields]).sort_values(
                by=["Rundle", "Luck"], ascending=[True, False]
            )
        else:
            luck_data = (data.loc[usernames][fields]).sort_values(
                by=["Luck"], ascending=False
            )
        headers = luck_data.columns.tolist()
        values = luck_data.round(3).values.tolist()
        ind = luck_data.index.get_loc(
            luck_data[
                luck_data["Player"].str.len() == luck_data["Player"].str.len().max()
            ].values[0][0]
        )
        calc_widths = list(map(lambda x: len(str(x)) + 1, values[ind]))
        col_widths = [
            max(calc_widths[i], len(headers[i]) + 2) for i in range(0, len(headers))
        ]
        sg.theme("Reddit")
        sg.set_options(font=("Arial", 16))
        layout = [
            [
                sg.Table(
                    size=(None, len(values)),
                    values=values,
                    headings=headers,
                    # Set column widths for empty record of table
                    auto_size_columns=False,
                    col_widths=col_widths,
                    expand_x=True,
                    expand_y=True,
                    alternating_row_color="light gray",
                )
            ]
        ]
        window = sg.Window("Luck Table", layout, resizable=True)
        event, value = window.read()
        return
    except Exception as e:
        print(e)


if __name__ == "__main__":
    pd.options.display.float_format = "{:,.3f}".format
    sess = login()
    # data = get_stats_data(100, "D_Orange_Div_2")
    data_df_100 = stats_model_luck(get_leaguewide_data(100))
    data_df_101 = stats_model_luck(get_leaguewide_data(101))
    # data = calc_luck(get_leaguewide_data(100))
    usernames = [
        "FahmyG",
        "FahmyB",
        "FahmyBoldsoul",
        "LefortS",
        "HarperD",
        "HulseM",
        "HammondM",
        "PantaloneG",
        "JenkinsK",
        "MooneyJ2",
    ]
    fields = [
        "Player",
        "W",
        "L",
        "T",
        "PTS",
        "xPTS",
        "TCA",
        "PCA",
        "CAA",
        "PCAA",
        "Luck",
        "Rank",
        "xRank",
        "SOS",
        "Rundle",
    ]
    specifc_user_field(data_df_101, usernames=usernames, fields=fields)
    specifc_user_field(data_df_101, usernames=["HulseM"], fields=fields, rundle=True)
