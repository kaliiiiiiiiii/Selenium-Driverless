#!/bin/bash

echo "Starting window manager..."
fluxbox -display $DISPLAY &

echo "Starting VNC server..."
x11vnc -forever -shared -rfbport 5900 -display $DISPLAY &

echo "Starting Chromewhip..."
python3.7 -m chromewhip.__init__ --js-profiles-path /usr/jsprofiles
