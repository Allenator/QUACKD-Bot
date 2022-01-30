import copy

from b92 import B92
from crypto import sha3_digest
from globals import *
from utils import timestamp


class KeyChain:
    def __init__(self, **b92_kwargs):
        self.keychain = {}
        self.b92_kwargs = b92_kwargs


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
