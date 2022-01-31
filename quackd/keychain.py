import copy
from datetime import datetime
import json

from b92 import B92
from crypto import sha3_digest
from globals import *
from utils import timestamp


class KeyChain:
    def __init__(self, keychain_path=None, **b92_kwargs):
        self.keychain_path=keychain_path
        self.b92_kwargs = b92_kwargs
        self.keychain = {}
        try:
            self._load_keychain()
        except OSError:
            return


    def _save_keychain(self):
        if self.keychain_path is None:
            return
        kc_temp = {}
        for host, kc_local in self.keychain.items():
            kc_temp[host] = {}
            for (src, dst), (key, ts) in kc_local.items():
                kc_temp[host][f'{src}+{dst}'] = (key, datetime.isoformat(ts))
        with open(self.keychain_path, 'w') as f:
            json.dump(kc_temp, f, sort_keys=False, indent=4)


    def _load_keychain(self):
        if self.keychain_path is None:
            return
        with open(self.keychain_path, 'r') as f:
            kc_temp = json.load(f)
        kc = {}
        for host, kc_local in kc_temp.items():
            kc[host] = {}
            for src_dst, (key, ts_iso) in kc_local.items():
                kc[host][tuple(src_dst.split('+'))] = (
                    key, datetime.fromisoformat(ts_iso)
                )
        self.keychain = kc


    def add(self, host, members, src, dst, key, pbar):
        sent_key, recv_key = self.qkd(key, pbar)
        if len(sent_key) >= KEY_MIN_SIZE:
            self.enroll(host, src, dst, sent_key)
            if len(recv_key) >= KEY_MIN_SIZE:
                for m in members:
                    self.enroll(m, src, dst, recv_key)
        return sent_key, recv_key


    def enroll(self, host, src, dst, key):
        if host not in self.keychain:
            self.keychain[host] = {}
        idx = (src, dst)
        self.keychain[host][idx] = (key, timestamp())
        try:
            self._save_keychain()
        except OSError:
            return


    def query(self, host, src, dst):
        if host not in self.keychain:
            return (None, None)
        idx = (src, dst)
        return self.keychain[host].get(idx, (None, None))


    def validate(self, h_val, src, dst):
        sent_key = self.query(src, src, dst)

        if sent_key is not None:
            h_sent = sha3_digest(sent_key[0])
            return h_val == h_sent, h_val[:6], h_sent[:6]
        else:
            return False, h_val[:6], None


    def get_keychain(self, host):
        return copy.deepcopy(self.keychain.get(host))


    def qkd(self, key, pbar):
        scheme = B92(key, pbar, **self.b92_kwargs)
        return scheme.get_key_pair()
