import hashlib

def double_sha256(msg):
    """sha256(sha256(msg)) -> bytes"""
    return hashlib.sha256(hashlib.sha256(msg).digest()).digest()

def hash160(msg):
    """ripemd160(sha256(msg)) -> bytes"""
    return hashlib.ripemd160(hashlib.sha256(msg).digest()).digest()

def sha256(msg):
    """one-line sha256(msg) -> bytes"""
    return hashlib.sha256(msg).digest()

def ripemd160(msg):
    """one-line rmd160(msg) -> bytes"""
    return hashlib.ripemd160(msg).digest()

def tagged_hash(tag, msg):
    """tagged hash: sha256(sha256(tag)+sha256(tag)+msg))"""
    tag_hash = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(tag_hash + tag_hash + msg).digest()
