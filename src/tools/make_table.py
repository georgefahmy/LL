from io import StringIO


def maketable(frame, season):
    fields = [
        "Player",
        "W",
        "L",
        "T",
        "PTS",
        "Exp_PTS",
        "Luck",
        "Rank",
        "Exp_Rank",
        "SOS",
        "Rundle",
    ]
    s = StringIO()
    zeta = "ζ"
    frame.to_csv(
        s, columns=fields, index=False, sep=zeta, float_format=lambda x: f"{x:.2f}"
    )
    lines = s.getvalue().split("\n")
    out = ["[table]"]
    out.append("[tr][th][b]")
    out.append(lines[0].replace(zeta, "[/th][th]"))
    out.append("[/th][/tr]")
    for line in lines[1:]:
        out.append("[tr][td]")
        out.append(line.replace(zeta, "[/td][td]"))
        out.append("[/td][/tr]")
    out.append("[/table]")
    return "".join(out)


# outfile = f"luck_table_{season}.bbcode"

# with open(outfile, "w") as f:
#     f.write(maketable(data[fields]))
