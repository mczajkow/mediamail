#!/usr/bin/bash
while true
do
	python3 ../twitterbot.py -l $1 -c $2
    sleep 1
    echo "Restarting program ..."
done