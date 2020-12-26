#!/usr/bin/bash
while true
do
	pwd=`pwd`
	echo $pwd
	python3 $pwd/twitterbot.py -l $1 -c $2
	sleep 1
	echo "Restarting program ..."
done