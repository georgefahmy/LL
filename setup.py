from setuptools import setup, find_packages

VERSION = open("VERSION", "r").read().strip()

APP = ["learnedLeague.py"]
DATA_FILES = [
    "resources",
    "VERSION",
    "resources/ll_logo.icns",
]
OPTIONS = {
    "iconfile": "/Users/GFahmy/Documents/projects/LL/resources/ll_logo.icns",
    "arch": "x86_64",
}

CONSOLE = [
    {
        "script": "learnedLeague.py",
    }
]

setup(
    app=APP,
    version=VERSION,
    data_files=DATA_FILES,
    console=CONSOLE,
    name="Learned League",
    options={"py2app": OPTIONS},
    setup_requires=[
        "py2app",
        "PySimpleGUI",
        "requests",
        "beautifulsoup4",
    ],
    packages=find_packages(),
    author="George Fahmy",
    description="LearnedLeague",
    python_requires=">=3.9",
    long_description="""The Learned League app allows access to the learned league seasons from the past and allows users
        to experience difficult trivia. Some stats are provided about the difficulty of each question based on the % of
        people that got that question correct.""",
)
