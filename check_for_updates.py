import os
import PySimpleGUI as sg
import requests
import sys
from packaging import version
import base64


WD = os.getcwd()

FILENAME = "LearnedLeague.dmg"
VOLUME_NAME = FILENAME.split(".")[0]


# Check if outdated
def check_for_update():
    restart = False

    version_response = requests.get("https://github.com/georgefahmy/LL/releases/latest")
    new_version = version_response.url.split("/")[-1].strip("v") if version_response.ok else None

    current_version = open(WD + "/resources/VERSION", "r").read().strip()

    if version.parse(current_version) >= version.parse(new_version):
        print("Version is up to date")

    elif version.parse(current_version) < version.parse(new_version):
        print("New Version available")
        icon_file = WD + "/resources/ll_app_logo.png"
        sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
        update_window = sg.Window(
            "Learned League Practice Tool Update Available",
            [
                [
                    sg.Text(
                        "Update available...",
                        font=("Arial", 16),
                        key="title",
                    )
                ],
                [
                    sg.Text("", font=("Arial", 13), key="p_status", size=(50, 1)),
                ],
                [
                    sg.ProgressBar(
                        max_value=100,
                        orientation="h",
                        size=(150, 20),
                        key="progress",
                        visible=False,
                    ),
                ],
                [
                    sg.Button("Download", key="d_b", auto_size_button=True),
                    sg.Button("Cancel", key="c_b", auto_size_button=True),
                ],
            ],
            disable_close=False,
            size=(300, 150),
            element_justification="c",
        )

        while True:
            update_event, values = update_window.read()
            if update_event:
                print(update_event, values)
            if update_event in ("c_b", sg.WIN_CLOSED):
                update_window.close()
                break

            if update_event == "d_b":
                update_window["p_status"].update(value="Downloading")
                update_window["progress"].update(visible=True)
                update_window["d_b"].update(visible=False)
                update_window["c_b"].update(visible=False)
                update_window["progress"].update(10)
                os.system("cd $HOME/Downloads")
                os.system(
                    'cd  $HOME/Downloads; curl -L -o LearnedLeague.dmg "https://github.com/georgefahmy/LL/releases/latest/download/LearnedLeague.dmg"'
                )
                update_window["progress"].update(30)
                update_window["p_status"].update(value="Installing...")
                os.system("cd $HOME/Downloads; hdiutil attach LearnedLeague.dmg")
                update_window["progress"].update(50)
                update_window["p_status"].update(value="Removing old files...")
                os.system("cd /Volumes/LearnedLeague/; \cp -rf *.app /Applications")
                update_window["progress"].update(65)
                update_window["p_status"].update(value="Cleaning up download")

                os.system('hdiutil detach "/Volumes/LearnedLeague"')
                update_window["progress"].update(80)
                update_window["p_status"].update(value="Done!...Restarting...")
                os.system("cd $HOME/Downloads; rm -rf LearnedLeague.dmg")
                update_window["progress"].update(100)
                restart = True
                update_window.close()
                break

    return restart
