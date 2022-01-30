import copy

from utils import timestamp


class KeyChain:
    def __init__(self):
        self.keychain = {}


    def add(self, host, members, src, dst, key):
        self.enroll(host, src, dst, key)
        recv_key = self.qkd(key)
        for m in members:
            self.enroll(m, src, dst, recv_key)
        return recv_key


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


    def qkd(self, key):
        return key
