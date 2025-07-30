#!/bin/zsh

# Ensure logs directory exists
mkdir -p ./logs

# start the alerting service
python3 ./found-him.py studio > /dev/null 2>&1 &

tail -F  /Users/scottfrancis/Library/Logs/Synergy/synergy.log | python3 ./waldo.py