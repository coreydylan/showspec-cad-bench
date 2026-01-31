#!/bin/bash
set -e

# Start virtual framebuffer for FreeCAD (even in headless mode it needs X)
Xvfb :99 -screen 0 1024x768x24 &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Execute command
exec "$@"
