import pandas as pd
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

from src.logged_in_tools import login
from src.userdata import load

sess = login()
user = load("FahmyBoldsoul", sess=sess)


def calc_elo(player_1_elo, player_2_elo, win):
    c = 400
    K = 32
    Ea = 10 ** (player_1_elo / c) / (
        10 ** (player_1_elo / c) + 10 ** (player_2_elo / c)
    )
    if win == "Win":
        return K * (1 - Ea)
    if win == "Tie":
        return K * (0.5 - Ea)
    if win == "Loss":
        return K * (0 - Ea)


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
            results = cells[2].text

            if player_1 not in players.keys():
                players[player_1] = 1000

            if player_2 not in players.keys():
                players[player_2] = 1000

            player_1_score = int(results.split("\xa0\xa0")[0].split("(")[0])
            player_1_val = results.split("\xa0\xa0")[0].split("(")[1].replace(")", "")
            player_1_cor = int(player_1_val) if player_1_val.isnumeric() else 0

            player_2_score = int(results.split("\xa0\xa0")[1].split("(")[0])
            player_2_val = results.split("\xa0\xa0")[1].split("(")[1].replace(")", "")
            player_2_cor = int(player_2_val) if player_2_val.isnumeric() else 0

            res = (
                f"Player 1 Score: {player_1_score} Correct: {player_1_cor}\n"
                + f"Player 2 Score: {player_2_score} Correct: {player_2_cor}"
            )

            if player_1_cor == player_2_cor == 0:
                Sa = 0.5
                Sa = 0.5
            else:
                Sa = player_1_cor / (player_1_cor + player_2_cor)
                Sb = player_2_cor / (player_2_cor + player_1_cor)

            if player_1_score > player_2_score:
                winner = players[player_1]
                loser = players[player_2]
                elo = calc_elo(winner, loser, "Win")
                players[player_1] += elo + (3 * Sa)
                players[player_2] -= elo - (3 * Sb)

            elif player_1_score == player_2_score:
                play1 = players[player_1]
                play2 = players[player_2]
                elo = calc_elo(play1, play2, "Tie")
                players[player_1] += elo + (3 * Sa)
                players[player_2] -= elo - (3 * Sb)

            elif player_1_score < player_2_score:
                winner = players[player_2]
                loser = players[player_1]
                elo = calc_elo(winner, loser, "Win")
                players[player_2] += elo + (3 * Sb)
                players[player_1] -= elo - (3 * Sa)

            res = (
                f"Player 1: {player_1} elo: {players[player_1]}\n"
                + f"Player 2: {player_2} elo: {players[player_2]}"
            )
            print(res)

data = pd.Series(players.toDict()).sort_values(ascending=False)
data.head()
