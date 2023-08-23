import os

import requests
from bs4 import BeautifulSoup as bs
from delocate.fuse import fuse_wheels

python_version = "311"
arm64 = "arm64"
x86 = "x86_64"
numpy_files = "https://pypi.org/project/numpy/#files"
pillow_files = "https://pypi.org/project/Pillow/#files"

numpy_page = bs(requests.get(numpy_files).content, "html.parser")
pillow_page = bs(requests.get(pillow_files).content, "html.parser")
np_files = numpy_page.find_all("div", {"class": "card file__card"})
pillow_files = pillow_page.find_all("div", {"class": "card file__card"})

numpy_links = [
    link
    for link in [link.a.get("href") for link in np_files if "whl" in link.a.get("href")]
    if "macosx" in link and python_version in link and (arm64 in link or x86 in link)
]
np_filenames = [
    os.getcwd() + "/universal_wheels/" + url.split("/")[-1] for url in numpy_links
]

pillow_links = [
    link
    for link in [
        link.a.get("href") for link in pillow_files if "whl" in link.a.get("href")
    ]
    if "macosx" in link and python_version in link and (arm64 in link or x86 in link)
]
pillow_filenames = [
    os.getcwd() + "/universal_wheels/" + url.split("/")[-1] for url in pillow_links
]
links = numpy_links + pillow_links

for url in links:
    filename = os.getcwd() + "/universal_wheels/" + url.split("/")[-1]
    with open(filename, "wb+") as out_file:
        content = requests.get(url, stream=True).content
        out_file.write(content)
        print(f"Saved {url}")

cwd = os.getcwd()
site_packages = (
    "/Library/Frameworks/Python.framework/Versions/3.11/lib/python3.11/site-packages/"
)
numpy_universal = (
    os.getcwd()
    + "/universal_wheels/numpy-1.25.2-cp311-cp311-macosx_11_0_universal2.whl"
)
fuse_wheels(np_filenames[0], np_filenames[1], numpy_universal)
pillow_universal = (
    os.getcwd()
    + "/universal_wheels/Pillow-10.0.0-cp311-cp311-macosx_11_0_universal2.whl"
)
fuse_wheels(pillow_filenames[0], pillow_filenames[1], pillow_universal)

os.system(f"pip install ./{'/'.join(pillow_universal.split('/')[-2:])}")
os.system(f"pip install ./{'/'.join(numpy_universal.split('/')[-2:])}")
