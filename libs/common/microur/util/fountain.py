from .random_sampler import RandomSampler
from .xoshiro256 import Xoshiro256

CACHE = {}

def shuffled(seq_len, rng, degree):
    remaining = list(range(seq_len))
    result = []
    while len(result) < degree:
        index = rng.next_int(0, len(remaining) - 1)
        item = remaining.pop(index)
        result.append(item)
    return result

def choose_degree(seq_len, rng):
    if CACHE.get("n") == seq_len:
        sampler = CACHE.get("sampler")
    else:
        sampler = RandomSampler([1.0/i for i in range(1, seq_len+1)])
        CACHE["n"] = seq_len
        CACHE["sampler"] = sampler
    return sampler.next(lambda: rng.next_double()) + 1

def choose_fragments(seq_num, seq_len, checksum):
    # The first `seq_len` parts are the "pure" fragments, not mixed with any
    # others. This means that if you only generate the first `seq_len` parts,
    # then you have all the parts you need to decode the message.
    if seq_num <= seq_len:
        return frozenset({seq_num - 1})
    else:
        seed = seq_num.to_bytes(4, 'big') + checksum.to_bytes(4, 'big')
        rng = Xoshiro256.from_bytes(seed)
        degree = choose_degree(seq_len, rng)
        shuffled_indexes = shuffled(seq_len, rng, degree)
        return frozenset(shuffled_indexes)

def part_sets_is_complete(part_sets, seq_len):
    return all([frozenset({i}) in part_sets for i in range(seq_len)])

def part_sets_add(part_sets, newset, reduce_callback=None):
    """
    Adds a new set into set of sets
    and reduces existing sets
    taking into account the new one.
    """
    # if it's already there - do nothing
    if newset in part_sets:
        return False
    newset = frozenset(newset)
    # if we have all individual sets already
    if all([frozenset({i}) in part_sets for i in newset]):
        return False
    # sets we will add
    new_sets = {newset}
    # reduce newset by other sets if it's complex
    if len(newset) > 1:
        for s in part_sets:
            if s.issubset(newset):
                if reduce_callback:
                    reduce_callback(newset, s)
                newset = newset.difference(s)
        new_sets.add(newset)
    # reduce complex sets by newset
    for s in part_sets:
        if len(s) > len(newset) and newset.issubset(s):
            if reduce_callback:
                reduce_callback(s, newset)
            new_sets.add(s.difference(newset))
    for s in new_sets:
        part_sets.add(s)

def reduce_parts(parts, streams, payload_len):
    """
    Goes through input streams and reduces them into streams dict.
    """
    return
#     setofsets = {}
#     buf1 = bytearray(payload_len)
#     buf2 = bytearray(payload_len)
#     for part_set in parts:
#         # duplicate
#         streamdict = streams[part_set]
#         if streamdict["written"]:
#             continue
#         assert streamdict["in"] is not None
#         assert payload_len = streamdict["in"].readinto(buf1)
#         streamdict["in"].seek(-payload_len, 1)
#         streamdict["out"].write(buf1)
#         streamdict["written"] = True
