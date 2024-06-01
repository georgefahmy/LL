import pandas as pd
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

from src.logged_in_tools import login
from src.userdata import load

sess = login()
user = load("FahmyG", sess=sess)

my_elo = 1000
c = 400
K = 40
opponents = DotMap()


def calc_elo(player_1_elo, player_2_elo, win, Sa):
    c = 400
    K = 32
    L = 12
    Ea = 10 ** (player_1_elo / c) / (
        10 ** (player_1_elo / c) + 10 ** (player_2_elo / c)
    )
    if win == "Win":
        return K * (1 - Ea) + (L * Sa)
    if win == "Tie":
        return K * (0.5 - Ea)
    if win == "Loss":
        return K * (0 - Ea) - (L * Sa)


for season in user.past_seasons.values():
    opponents = DotMap()
    my_elo = 1000
    for match in season.matches.values():
        if match.opponent not in opponents.keys():
            opponent_elo = opponents[match.opponent] = 1000
        Qa = 10 ** (my_elo / c)
        Qb = 10 ** (opponents[match.opponent] / c)
        Ea = Qa / (Qa + Qb)
        if match.result == "Win":
            elo_diff = K * (1 - Ea)
        if match.result == "Tie":
            elo_diff = K * (0.5 - Ea)
        if match.result == "Loss":
            elo_diff = K * (0 - Ea)
        my_elo += elo_diff
        opponents[match.opponent] += elo_diff
    print(season.season.name)
    opponents.pprint()
    print(f"My ELO: {my_elo}")

# season_analysis
players = DotMap()
for season in list(reversed(user.past_seasons.keys())):
    rundle = (
        user.past_seasons[season].rundle.name.replace(" ", "_").replace("Rundle_", "")
    )
    print(rundle)
    for MD in range(1, 26):
        print(MD)
        link = f"https://learnedleague.com/match.php?{season.replace('LL', '')}&{MD}&{rundle}"
        page = bs(sess.get(link).content, "html.parser")
        if "not yet" in page.text:
            break
        table = page.find("table", {"class": "gamelinetbl"}).find_all("tr")
        for row in table:
            cells = row.find_all("td")
            player_1 = cells[1].text
            player_2 = cells[3].text
            if player_1 not in players.keys():
                players[player_1] = 1000
            if player_2 not in players.keys():
                players[player_2] = 1000
            player_1_score = int(cells[2].text.split("\xa0\xa0")[0].split("(")[0])
            player_1_val = (
                cells[2].text.split("\xa0\xa0")[0].split("(")[1].replace(")", "")
            )
            if player_1_val.isnumeric():
                player_1_cor = int(player_1_val)
            else:
                player_1_val = 0
            player_2_score = int(cells[2].text.split("\xa0\xa0")[1].split("(")[0])
            player_2_val = (
                cells[2].text.split("\xa0\xa0")[1].split("(")[1].replace(")", "")
            )
            if player_2_val.isnumeric():
                player_2_cor = int(player_2_val)
            else:
                player_2_cor = 0
            if player_1_cor == player_2_cor == 0:
                Sa = 0.5
            else:
                Sa = player_1_cor / (player_1_cor + player_2_cor)
            if player_1_score > player_2_score:
                elo = calc_elo(players[player_1], players[player_2], "Win", Sa)
                players[player_1] += elo
                players[player_2] -= elo
            elif player_1_score == player_2_score:
                elo = calc_elo(players[player_1], players[player_2], "Tie", Sa)
                players[player_1] += elo
                players[player_2] -= elo
            elif player_1_score < player_2_score:
                elo = calc_elo(players[player_1], players[player_2], "Loss", Sa)
                players[player_1] += elo
                players[player_2] -= elo
            res = (
                f"Player 1: {player_1} elo: {players[player_1]}\n"
                + f"Player 2: {player_2} elo: {players[player_2]}"
            )
            print(res)

data = pd.Series(players.toDict()).sort_values(ascending=False)
