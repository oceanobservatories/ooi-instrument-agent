#!/bin/bash

gunicorn --log-config logging.conf -w 2 -k gevent -b 0.0.0.0:12572 ooi_instrument_agent:app