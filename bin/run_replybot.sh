#!/usr/bin/bash
pwd=`pwd`
echo $pwd
python3 $pwd/replybot.py -l $1 -c $2
