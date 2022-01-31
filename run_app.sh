#!/bin/bash

CONDA_PATH="conda"
CONDA_ENV="quackd"
PYTHON_PATH="python3"

SLACK_TOKENS_PATH="credentials/slack.json"
QI_AUTH_PATH="credentials/qi.json"
KEYCHAIN_PATH="data/keychain.json"

# Specify backend for B92 protocol
# Available options are "aer", "qi_sim", "qi_starmon"
BACKEND="aer"

eval "$(${CONDA_PATH} shell.bash hook)"
${CONDA_PATH} activate ${CONDA_ENV}

${PYTHON_PATH} quackd/app.py \
    ${SLACK_TOKENS_PATH} ${BACKEND} \
    --qi_auth_path ${QI_AUTH_PATH} \
    --keychain_path ${KEYCHAIN_PATH}
