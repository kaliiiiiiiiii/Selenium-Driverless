#!/bin/bash

docker build . -t chromewhip
#docker run --init -it --rm --name chromewhip --shm-size=1024m --cap-add=SYS_ADMIN -p=127.0.0.1:80:33233 chromewhip
docker run --init -it --rm --name chromewhip --shm-size=1024m --cap-add=SYS_ADMIN -p=33233:8080 -p 5900:5900 chromewhip
