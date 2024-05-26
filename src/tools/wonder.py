from analysis import load_data
from dotmap import DotMap


def mscore(score_u, score_t):
    """
    Return 2 for win, 1 for tie, 0 for loss, -1 for Forfeit
    """

    if score_u < 0 or score_t < 0:
        return -1
    if score_u < score_t:
        return 0
    if score_u > score_t:
        return 2
    return 1


def score_wonder(scores):
    """
    Find wonder value for a score in
    [[a - points, a - questions], [b - points, b - quesitons]] format.
    High Wonder value means defense helped in the success

    - if A and B questions are equal but A points are more, then wonder value = 1
    A goes up by 1 and B goes down by 1

    - if A and B points are equal but A questions are lower then Wonder value = 1
    A goes up by 1 and B goes down by 1

    - if A has less correct questions but won in points then Wonder Value = 2
    A goes up by 2 and B goes down by 2
    """
    if type(scores) is str:
        if "F" in scores:
            scores = scores.replace("F", "0")
        # print(scores)
        scores = [[int(scores[0]), int(scores[2])], [int(scores[5]), int(scores[7])]]

    # first compare questions correct return 0 if forfeit
    reg = mscore(scores[0][1], scores[1][1])
    if reg < 0:
        return 0
    # then compare points and subtract question difference to get wonder value
    # if 0 then defense doesnt play a roll in points (i.e. more questions and more points)
    return mscore(scores[0][0], scores[1][0]) - reg


user = load_data(user="fahmyb")
wonder = 0
optimal_scores = DotMap({"9(5)": 0, "8(4)": 0, "7(3)": 0, "5(2)": 0, "3(1)": 0})
for season in user.past_seasons.keys():
    for match in user.past_seasons[season].matches.values():
        wonder += score_wonder(match.score)
        my_score = match.score.split("-")[0]
        if my_score in optimal_scores.keys():
            optimal_scores[my_score] += 1

    print(f"Final - {season}: {wonder}")
    optimal_scores.pprint()
