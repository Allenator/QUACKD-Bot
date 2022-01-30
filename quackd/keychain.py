import copy

from b92 import B92

from globals import N_KEY_MIN_BITS
from utils import timestamp


class KeyChain:
    def __init__(self):
        self.keychain = {}


    def add(self, host, members, src, dst, key, pbar):
        sent_key, recv_key = self.qkd(key, pbar)
        if len(sent_key) >= N_KEY_MIN_BITS:
            self.enroll(host, src, dst, sent_key)
            if len(recv_key) >= N_KEY_MIN_BITS:
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
            return None
        idx = (src, dst)
        return self.keychain[host].get(idx)


    def get_keychain(self, host):
        return copy.deepcopy(self.keychain.get(host))


    def qkd(self, key, pbar, **kwargs):
        scheme = B92(key, pbar, **kwargs)
        return scheme.get_key_pair()
