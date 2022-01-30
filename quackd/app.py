import argparse
import html
import re

from qiskit import Aer
from quantuminspire.qiskit import QI
from slack_bolt import App # type:ignore
from slack_bolt.adapter.socket_mode import SocketModeHandler # type:ignore

from crypto import encrypt_text, decrypt_text, fernet_keygen, sha3_digest
from globals import *
from keychain import KeyChain
from progress import SlackProgress
from utils import load_slack_tokens, set_qi_auth


parser = argparse.ArgumentParser()
parser.add_argument(
    'slack_tokens_path',
    help='specify path to the file containing Slack tokens'
)
parser.add_argument(
    'backend',
    choices=['aer', 'qi_sim' or 'qi_starmon'],
    help='specify backend for running B92 protocol'
)
parser.add_argument(
    '--qi_auth_path',
    help='specify path to the file containing QI authentication details'
)
args = parser.parse_args()

slack_app_token, slack_bot_token = load_slack_tokens(args.slack_tokens_path)
app = App(token=slack_bot_token)

if args.backend == 'aer':
    backend = Aer.get_backend('aer_simulator')
else:
    if args.qi_auth_path is None:
        raise ValueError('QI authentication file must be specified '
            'when the Aer backend is not in use')
    set_qi_auth(args.qi_auth_path)
    if args.backend == 'qi_sim':
        backend = QI.get_backend('QX single-node simulator')
    elif args.backend == 'qi_starmon':
        backend = QI.get_backend('Starmon-5')
    else:
        raise ValueError(f'unknown backend specification "{args.backend}"')

kc_global = KeyChain(backend=backend, **B92_DEFAULT_KWARGS)


def _tag(type, id):
    return f'<{type}{id}>'

bot_id = app.client.auth_test()['user_id']
bot_tag = _tag(TYPE_USER, bot_id)


def _parse_command(command):
    src_id = command['user_id']
    src_tag = _tag(TYPE_USER, src_id)

    regex = r'<(@|#)([UC][A-Z0-9]{10})\|(.*?)> `(.+?)`'

    res = re.search(regex, html.unescape(command['text']))

    dst_type = None
    dst_id = None
    dst_tag = None
    key = None

    if res is not None:
        dst_type = res.groups()[0]
        dst_id = res.groups()[1]
        dst_tag = _tag(dst_type, dst_id)
        key = res.groups()[3]

    return (src_id, src_tag), \
        (dst_type, dst_id, dst_tag), \
        key


@app.command('/qkd')
def qkd(ack, respond, command):
    ack()

    (src_id, src_tag), \
        (dst_type, dst_id, dst_tag), \
        key_orig = _parse_command(command)

    if dst_id is None:
        respond(f'Usage: /qkd @user/#channel `key`')
        return

    h_key = sha3_digest(key_orig)
    key = bin(int(h_key, 16))[2:][:KEY_INIT_SIZE]

    respond(f'Sharing key `{key_orig}` to {dst_tag} as `{key}` ({KEY_INIT_SIZE} bits).')

    if dst_type == TYPE_CHANNEL:
        members = app.client.conversations_members(channel=dst_id)['members']
        if src_id in members:
            members.remove(src_id)
    elif dst_type == TYPE_USER:
        members = [dst_id]
    else:
        raise NotImplementedError(f'Unknown destination type "{dst_type}"')

    sp = SlackProgress(app, src_id)
    pbar = sp.new(total=N_PBAR_ITEMS)
    pbar.pos = 0

    sent_key, recv_key = kc_global.add(src_id, members, src_id, dst_id, key, pbar)

    if len(sent_key) >= KEY_MIN_SIZE:
        respond(f'Stored key `{sent_key}` after reconciliation.')
    else:
        respond(f'Shared key `{sent_key}` is discarded '
            f'(minimum length of {KEY_MIN_SIZE} required).')

    if len(recv_key) >= KEY_MIN_SIZE:
        for m in members:
            app.client.chat_postMessage(
                channel=m,
                text=f'Received new key `{recv_key}` for {src_tag} ➡️ {dst_tag} via QKD!'
            )
    else:
        for m in members:
            app.client.chat_postMessage(
                channel=m,
                text=f'Received key `{recv_key}` for {src_tag} ➡️ {dst_tag} is dicarded '
                    f'(minimum length of {KEY_MIN_SIZE} required).'
            )


@app.command('/kc')
def kc(ack, respond, command):
    ack()

    host_id = command['user_id']
    host_tag = _tag(TYPE_USER, host_id)

    if command['text'] != '':
        respond(f'Usage: /kc')
        return

    kc_local = kc_global.get_keychain(host_id)
    if kc_local is None:
        respond(f'{host_tag}\'s local keychain hasn\'t been created!')
    elif len(kc_local) == 0:
        respond(f'{host_tag}\'s local keychain is empty!')
    else:
        resp = f'{host_tag}\'s local keychain:'
        resp_idx = 0
        for (src_id, dst_id), (key, ts) in kc_local.items():
            src_tag = _tag(TYPE_USER, src_id)
            if dst_id[0] == PREFIX_CHANNEL:
                dst_tag = _tag(TYPE_CHANNEL, dst_id)
            elif dst_id[0] == PREFIX_USER:
                dst_tag = _tag(TYPE_USER, dst_id)
            else:
                raise ValueError(f'ID "{dst_id}" contains an invalid prefix')
            is_equal, h_val, _ = kc_global.validate(sha3_digest(key), src_id, dst_id)
            repr_equal = '✅' if is_equal else '❌'
            resp_idx += 1
            resp += f'\n└ {resp_idx}. {src_tag} ➡️ {dst_tag} : '\
                f'🔑 `{key}` {repr_equal} {h_val} ⏱️ {ts}'
        respond(resp)


def _parse_event(event):
    src_id = event['user']
    src_tag = _tag(TYPE_USER, src_id)

    regex = r'<(@|#)([UC][A-Z0-9]{10})\|?(>)'

    text_orig = html.unescape(event['text'])
    res = re.search(regex, text_orig)

    dst_type = None
    dst_id = None
    dst_tag = None
    text = None

    if res is not None:
        i_start, i_end = res.span()
        text_trunc = text_orig[i_end:]
        if i_start == 0 and text_trunc and not str.isspace(text_trunc):
            dst_type = res.groups()[0]
            dst_id = res.groups()[1]
            dst_tag = _tag(dst_type, dst_id)
            text = text_trunc

    return (src_id, src_tag), \
        (dst_type, dst_id, dst_tag), \
        text


@app.event('message')
def message(body, logger):
    if body['event'].get('subtype') == 'message_changed':
        return

    (src_id, src_tag), \
        (dst_type, dst_id, dst_tag), \
        text = _parse_event(body['event'])

    if dst_id is None:
        app.client.chat_postEphemeral(
            channel=src_id,
            user=src_id,
            text=f'Usage: @user/#channel message'
        )
        return

    if dst_type == TYPE_CHANNEL:
        channel_id = dst_id
    elif dst_type == TYPE_USER:
        channel_id = app.client.conversations_open(
            return_im=True,
            users=f'{src_id},{dst_id}'
        )['channel']['id']
    else:
        raise NotImplementedError(f'Unknown destination type "{dst_type}"')

    plain_text = text.strip() # type: ignore
    key, _ = kc_global.query(src_id, src_id, dst_id)

    if key is None:
        app.client.chat_postEphemeral(
            channel=src_id,
            user=src_id,
            text=f'No key is found for {src_tag} ➡️ {dst_tag} on local keychain. '
                'Try distributing a key via QKD first.'
        )
        return

    cipher_text = encrypt_text(plain_text, fernet_keygen(key))
    app.client.chat_postMessage(
        channel=channel_id,
        text=f'{src_tag} ➡️ {dst_tag} :\n```{cipher_text}```'
    )

    if dst_type == TYPE_CHANNEL:
        members = app.client.conversations_members(channel=dst_id)['members']
        if src_id in members:
            members.remove(src_id)
    elif dst_type == TYPE_USER:
        members = [dst_id]
    else:
        raise NotImplementedError(f'Unknown destination type "{dst_type}"')

    for m in members:
        m_key, _ = kc_global.query(m, src_id, dst_id)

        if m_key is None:
            app.client.chat_postEphemeral(
                channel=m,
                user=m,
                text=f'Unable to decode message for {src_tag} ➡️ {dst_tag} '
                    '(key not present on local keychain). '
                    f'Please contact {src_tag} to obtain a key via QKD.'
            )
            return

        decrypted_text = decrypt_text(cipher_text, fernet_keygen(m_key))
        app.client.chat_postMessage(
            channel=m,
            text=f'{src_tag} ➡️ {dst_tag} : {decrypted_text}'
        )


if __name__ == '__main__':
    SocketModeHandler(app, slack_app_token).start()
