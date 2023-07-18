from setuptools import setup, find_packages
from markdown import markdown
from bs4 import BeautifulSoup
import re

VERSION = re.compile("[^0-9\.]").sub(
    "",
    (
        BeautifulSoup(markdown(open("changelog.md", "r").read()), "html.parser")
        .find_all(string=re.compile("[v]"))[0]
        .split()[0]
    ),
)
with open("resources/VERSION", "w") as f:
    f.write(VERSION)


APP = ["learnedLeague.py"]
DATA_FILES = [
    "resources",
    "resources/VERSION",
    "resources/ll_logo.icns",
    "onedays.py",
]
OPTIONS = {
    "excludes": ["numpy", "matplotlib"],
    "includes": [
        "PySimpleGUI",
        "requests",
        "beautifulsoup4",
        "wikipedia",
        "jellyfish",
    ],
    "iconfile": "/Users/GFahmy/Documents/projects/LL/resources/ll_logo.icns",
    "arch": "x86_64",
    # "arch": "universal2",
}

setup(
    app=APP,
    version=VERSION,
    data_files=DATA_FILES,
    name="Learned League",
    options={"py2app": OPTIONS},
    author="George Fahmy",
    description="LearnedLeague",
    python_requires=">=3.10",
    long_description="""The Learned League app allows access to the learned league seasons from the past and allows users
        to experience difficult trivia. Some stats are provided about the difficulty of each question based on the % of
        people that got that question correct.""",
)
