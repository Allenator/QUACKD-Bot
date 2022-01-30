#!/bin/bash

PYTHON_PATH="python3"
SLACK_TOKENS_PATH="credentials/slack.json"
QI_AUTH_PATH="credentials/qi.json"

# Specify backend for B92 protocol
# Available options are "aer", "qi_sim", "qi_starmon"
BACKEND="qi_starmon"

${PYTHON_PATH} quackd/app.py ${SLACK_TOKENS_PATH} ${BACKEND} --qi_auth_path ${QI_AUTH_PATH}
