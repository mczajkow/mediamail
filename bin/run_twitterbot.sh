#!/bin/bash
while true
do
	python3 $1/twitterbot.py -l $2 -c $3
	sleep 1
	echo "Restarting program ..."
done