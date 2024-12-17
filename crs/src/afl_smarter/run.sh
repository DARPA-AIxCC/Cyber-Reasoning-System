#!/bin/bash

cd /home/ubuntu

flask --app server run --host=0.0.0.0 -p 9043
