from dotmap import DotMap

from src.userdata import load

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
    user = load(username="fahmyg")

    for season in user.past_seasons.keys():
        for match in user.past_seasons[season].matches.values():
            my_score = match.score.split("-")[0]
            print(my_score)
            if my_score in scorigami.keys():
                scorigami[my_score] += 1
            else:
                print("error")
    scorigami.pprint()
