#!/usr/bin/bash
pwd=`pwd`
echo $pwd
python3 $pwd/mailbot.py -l $1 -c $2
