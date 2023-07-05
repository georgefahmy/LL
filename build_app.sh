#!/bin/bash

INVENV=$(/usr/local/bin/python3.11 -c 'import sys; print( True if "virtual" in sys.prefix else False)')
VERSION=v$(/usr/local/bin/python3.11 setup.py --version)

if [ $INVENV == "True" ]; then
    echo "Please deactivate the virtual environment and run again"
    exit 0
else
    rm -rf build dist
    /usr/local/bin/pip3.11 install -r requirements.txt
    /usr/local/bin/python3.11 setup.py py2app
    cd dist
    ln -s /Applications/
    echo "Creating Installation Image"
    hdiutil create -srcfolder . -volname "LearnedLeague" LearnedLeague.dmg
    rm -rf "LearnedLeague.app"
    rm ./Applications
    cd ..
    echo "Creating release $VERSION and uploading app to github"
    gh release create $VERSION dist/*.dmg -t "LearnedLeague $VERSION"
fi
