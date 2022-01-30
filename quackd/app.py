import argparse
import html
import re

from slack_bolt import App # type:ignore
from slack_bolt.adapter.socket_mode import SocketModeHandler # type:ignore

from globals import *
from progress import SlackProgress
from keychain import KeyChain
from utils import load_slack_tokens


parser = argparse.ArgumentParser()
parser.add_argument(
    'tokens_path',
    help='specify path to the file containing Slack tokens'
)
args = parser.parse_args()

slack_app_token, slack_bot_token = load_slack_tokens(args.tokens_path)
app = App(token=slack_bot_token)
kc_global = KeyChain()


def _parse_command(command, with_key):
    src_id = command['user_id']
    src_name = command['user_name']
    src_tag = f'<{TYPE_USER}{src_id}|{src_name}>'

    if with_key:
        regex = r'<(@|#)([UC][A-Z0-9]{10})\|(.*?)> `(.+?)`'
    else:
        regex = r'<(@|#)([UC][A-Z0-9]{10})\|(.*?)>'

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
        if with_key:
            key = res.groups()[3]

    if with_key:
        return (src_id, src_name, src_tag), \
            (dst_type, dst_id, dst_name, dst_tag), \
            key
    else:
        return (src_id, src_name, src_tag), \
            (dst_type, dst_id, dst_name, dst_tag)


@app.command('/qkd')
def qkd(ack, respond, command):
    ack()

    (src_id, _, src_tag), \
        (dst_type, dst_id, _, dst_tag), \
        key = _parse_command(command, True) # type:ignore

    if dst_id is None:
        respond(f'Usage: /qkd @user/#channel `key`')
    else:
        respond(f'Sharing key `{key}` to {dst_tag}...')

        if dst_type == TYPE_CHANNEL:
            members = app.client.conversations_members(channel=dst_id)['members']
        elif dst_type == TYPE_USER:
            members = [dst_id]
        else:
            raise NotImplementedError(f'Unknown key type {dst_type}')

        sp = SlackProgress(app, src_id)
        pbar = sp.new(total=N_PBAR_ITEMS)
        pbar.pos = 0

        sent_key, recv_key = kc_global.add(src_id, members, src_id, dst_id, key, pbar)

        if len(sent_key) >= N_KEY_MIN_BITS:
            respond(f'Stored key `{sent_key}` after reconciliation')
        else:
            respond(f'Shared key `{sent_key}` is discarded '
                f'(minimum length of {N_KEY_MIN_BITS} required)')

        if len(recv_key) >= N_KEY_MIN_BITS:
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
                        f'(minimum length of {N_KEY_MIN_BITS} required)'
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
                resp_idx += 1
                resp += f'\n└ {resp_idx}. {src_tag} → {dst_tag} : `{key}` @ {ts}'
            respond(resp)


# @app.command('/query')
# def query(ack, respond, command):
#     ack()

#     (src_id, _, src_tag), \
#         (_, dst_id, _, dst_tag) = _parse_command(command, False) # type:ignore

#     if dst_id is None:
#         respond(f'Usage: /query @user/#channel')
#     else:
#         key = kc_global.query(src_id, src_id, dst_id)
#         print(kc_global.keychain)

#         if key is None:
#             respond(f'Cannot find a key from {src_tag} to {dst_tag}.')
#         else:
#             respond(f'The shared key from {src_tag} to {dst_tag} is `{key}`.')


if __name__ == '__main__':
    SocketModeHandler(app, slack_app_token).start()
