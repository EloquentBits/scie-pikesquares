#set working-directory := 'uwsgi'
#@uwsgi-dir:
#  pwd

#PYTHON := "python3"

default:
  just --list

build-scie:
  cargo run -p package -- --dest-dir dist/ scie

git-submodule-update:
   git submodule update --init --recursive

build-uwsgi-core:
  cd uwsgi && /usr/bin/python3 uwsgiconfig.py --build core

build-uwsgi-nolang: 
  cd uwsgi && /usr/bin/python3 uwsgiconfig.py --build nolang

build-uwsgi-pikesquares:
  cd uwsgi && /usr/bin/python3 uwsgiconfig.py --build pikesquares

build-python-plugin:
  cp pikesquares.ini uwsgi/buildconf
  cd uwsgi && /usr/bin/python3 uwsgiconfig.py \
    --plugin plugins/python pikesquares.ini python312

