import argparse
import html
import re

import numpy as np
from slack_bolt import App # type:ignore
from slack_bolt.adapter.socket_mode import SocketModeHandler # type:ignore

from globals import *
from progress import SlackProgress
from keychain import KeyChain
from utils import load_slack_tokens, sha3_digest


parser = argparse.ArgumentParser()
parser.add_argument(
    'tokens_path',
    help='specify path to the file containing Slack tokens'
)
args = parser.parse_args()

slack_app_token, slack_bot_token = load_slack_tokens(args.tokens_path)
app = App(token=slack_bot_token)
kc_global = KeyChain()


def _parse_command(command):
    src_id = command['user_id']
    src_name = command['user_name']
    src_tag = f'<{TYPE_USER}{src_id}|{src_name}>'

    regex = r'<(@|#)([UC][A-Z0-9]{10})\|(.*?)> `(.+?)`'

    res = re.search(regex, html.unescape(command['text']))

    dst_type = None
    dst_id = None
    dst_name = None
    dst_tag = None
    key = None

    if res is not None:
        dst_type = res.groups()[0]
        dst_id = res.groups()[1]
        dst_name = res.groups()[2]
        dst_tag = f'<{dst_type}{dst_id}|{dst_name}>'
        key = res.groups()[3]

    return (src_id, src_name, src_tag), \
        (dst_type, dst_id, dst_name, dst_tag), \
        key


@app.command('/qkd')
def qkd(ack, respond, command):
    ack()

    (src_id, _, src_tag), \
        (dst_type, dst_id, _, dst_tag), \
        key_orig = _parse_command(command)

    if dst_id is None:
        respond(f'Usage: /qkd @user/#channel `key`')
    else:
        h_key = sha3_digest(key_orig)
        key = bin(int(h_key, 16))[2:][:KEY_INIT_SIZE]

        respond(f'Sharing key `{key_orig}` to {dst_tag} as `{key}` ({KEY_INIT_SIZE} bits)')

        if dst_type == TYPE_CHANNEL:
            members = app.client.conversations_members(channel=dst_id)['members']
        elif dst_type == TYPE_USER:
            members = [dst_id]
        else:
            raise NotImplementedError(f'Unknown destination type {dst_type}')

        sp = SlackProgress(app, src_id)
        pbar = sp.new(total=N_PBAR_ITEMS)
        pbar.pos = 0

        sent_key, recv_key = kc_global.add(src_id, members, src_id, dst_id, key, pbar)

        if len(sent_key) >= KEY_MIN_SIZE:
            respond(f'Stored key `{sent_key}` after reconciliation')
        else:
            respond(f'Shared key `{sent_key}` is discarded '
                f'(minimum length of {KEY_MIN_SIZE} required)')

        if len(recv_key) >= KEY_MIN_SIZE:
            for m in members:
                app.client.chat_postMessage(
                    channel=m,
                    text=f'{src_tag} has shared a key `{recv_key}` to {dst_tag} via QKD!'
                )
        else:
            for m in members:
                app.client.chat_postMessage(
                    channel=m,
                    text=f'Received key `{recv_key}` from {src_tag} to {dst_tag} is dicarded '
                        f'(minimum length of {KEY_MIN_SIZE} required)'
                )


@app.command('/kc')
def kc(ack, respond, command):
    ack()

    src_id = command['user_id']
    src_name = command['user_name']
    src_tag = f'<{TYPE_USER}{src_id}|{src_name}>'

    if command['text'] != '':
        respond(f'Usage: /kc')
    else:
        kc_local = kc_global.get_keychain(src_id)
        if kc_local is None:
            respond(f'{src_tag}\'s keychain hasn\'t been created!')
        elif len(kc_local) == 0:
            respond(f'{src_tag}\'s keychain is empty!')
        else:
            resp = f'{src_tag}\'s keychain:'
            resp_idx = 0
            for (src_id, dst_id), (key, ts) in kc_local.items():
                src_name = app.client.users_info(user=src_id)['user']['name']
                src_tag = f'<{TYPE_USER}{src_id}|{src_name}>'
                if dst_id[0] == PREFIX_CHANNEL:
                    dst_name = app.client.conversations_info(channel=dst_id)['channel']['name']
                    dst_tag = f'<{TYPE_CHANNEL}{dst_id}|{dst_name}>'
                elif dst_id[0] == PREFIX_USER:
                    dst_name = app.client.users_info(user=dst_id)['user']['name']
                    dst_tag = f'<{TYPE_USER}{dst_id}|{dst_name}>'
                else:
                    raise ValueError(f'ID "{dst_id}" contains an invalid prefix')
                is_equal, h_val, _ = kc_global.validate(src_id, dst_id, key)
                repr_equal = '✅' if is_equal else '❌'
                resp_idx += 1
                resp += f'\n└ {resp_idx}. {src_tag} ➡️ {dst_tag} : '\
                    f'🔑 `{key}` {repr_equal} {h_val} ⏱️ {ts}'
            respond(resp)


if __name__ == '__main__':
    SocketModeHandler(app, slack_app_token).start()
