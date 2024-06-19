import numpy as np
from dotmap import DotMap

from src.userdata import load


def calc_DE(opp_correct_answers, opp_points):
    max_min_unforced = DotMap(
        {  # correct answers - (max allowed, min allowed) scores
            0: (0, 0),
            1: (3, 0),
            2: (5, 1),
            3: (7, 2),
            4: (8, 4),
            5: (9, 6),
            6: (9, 9),
        }
    ).get(opp_correct_answers)
    UfPA = opp_points - max_min_unforced[1]
    pUfPA = max_min_unforced[0] - max_min_unforced[1]
    return UfPA, pUfPA


def calc_OE(my_correct_answers, my_points):
    max_min_unforced = DotMap(
        {  # correct answers - (max allowed, min allowed) scores
            0: (0, 0),
            1: (3, 0),
            2: (5, 1),
            3: (7, 2),
            4: (8, 4),
            5: (9, 6),
            6: (9, 9),
        }
    ).get(my_correct_answers)
    UfPE = my_points - max_min_unforced[1]
    pUfPE = max_min_unforced[0] - max_min_unforced[1]
    return UfPE, pUfPE


scorigami = DotMap(
    {
        "0(0)": 0,
        "0(1)": 0,
        "1(1)": 0,
        "2(1)": 0,
        "3(1)": 0,
        "1(2)": 0,
        "2(2)": 0,
        "3(2)": 0,
        "4(2)": 0,
        "5(2)": 0,
        "2(3)": 0,
        "3(3)": 0,
        "4(3)": 0,
        "5(3)": 0,
        "6(3)": 0,
        "7(3)": 0,
        "4(4)": 0,
        "5(4)": 0,
        "6(4)": 0,
        "7(4)": 0,
        "8(4)": 0,
        "6(5)": 0,
        "7(5)": 0,
        "8(5)": 0,
        "9(5)": 0,
        "9(6)": 0,
    }
)

if __name__ == "__main__":
    user = load(username="fahmyb")
    for season in user.past_seasons.keys():
        for match in user.past_seasons[season].matches.values():
            my_score = match.score.split("-")[0]
            print(my_score)
            if my_score in scorigami.keys():
                scorigami[my_score] += 1
            else:
                print("error")

    scorigami.pprint()
    debug = True
    for season in user.past_seasons.keys():
        print(f"Season {season}")
        UfPA = []
        pUfPA = []
        UfPE = []
        pUfPE = []
        for key, match in user.past_seasons[season].matches.items():
            scores = match.score_breakdown
            if scores.opp_correct == "F" or scores.correct == "F":
                continue
            ufpa, pufpa = calc_DE(int(scores.opp_correct), int(scores.opp_points))
            UfPA.append(ufpa)
            pUfPA.append(pufpa)
            ufpe, pufpe = calc_OE(int(scores.correct), int(scores.points))
            UfPE.append(ufpe)
            pUfPE.append(pufpe)
            if debug:
                try:
                    oe = ufpe / pufpe
                except Exception:
                    oe = 0
                try:
                    de = 1 - (ufpa / pufpa)
                except Exception:
                    de = 0
                print(
                    f"{key.capitalize()}\n"
                    + f"Me:\t\t{int(scores.correct)} correct answers for {int(scores.points)} points\n"
                    + f"Opponent:\t{int(scores.opp_correct)} correct answers for {int(scores.opp_points)} points\n"
                    + f"OE: {oe:3.3f}, DE: {de:3.3f}\n"
                )
        de = 1 - (np.array(UfPA).sum() / np.array(pUfPA).sum())
        oe = np.array(UfPE).sum() / np.array(pUfPE).sum()
        print(f"{season} - Overall OE: {oe:3.3f} and Overall DE: {de:3.3f}\n")
