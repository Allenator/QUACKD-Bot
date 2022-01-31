#!/bin/bash

CONDA_PATH="/opt/miniconda3/condabin/conda"
CONDA_ENV="quackd"
PYTHON_PATH="python3"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SLACK_TOKENS_PATH="${SCRIPT_DIR}/credentials/slack.json"
QI_AUTH_PATH="${SCRIPT_DIR}/credentials/qi.json"
KEYCHAIN_PATH="${SCRIPT_DIR}/data/keychain.json"

# Specify backend for B92 protocol
# Available options are "aer", "qi_sim", "qi_starmon"
BACKEND="aer"

eval "$(${CONDA_PATH} shell.bash hook)"
conda activate ${CONDA_ENV}

exec ${PYTHON_PATH} ${SCRIPT_DIR}/quackd/app.py \
    ${SLACK_TOKENS_PATH} ${BACKEND} \
    --qi_auth_path ${QI_AUTH_PATH} \
    --keychain_path ${KEYCHAIN_PATH}
