#!/bin/bash

PYTHON_PATH="python3"
TOKENS_PATH="credentials/slack.json"

${PYTHON_PATH} quackd/app.py ${TOKENS_PATH}
