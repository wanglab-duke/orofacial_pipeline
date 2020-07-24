import logging

import datajoint as dj
import hashlib

log = logging.getLogger(__name__)


# safe-guard in case `custom` is not provided
if 'custom' not in dj.config:
    dj.config['custom'] = {}


def get_schema_name(name):
    try:
        return dj.config['custom']['{}.database'.format(name)]
    except KeyError:
        prefix = 'cosmo_'

    return prefix + name


def dict_to_hash(key):
    """
    Given a dictionary `key`, returns a hash string
    """
    hashed = hashlib.md5()
    for k, v in sorted(key.items()):
        hashed.update(str(k).encode())
        hashed.update(str(v).encode())
    return hashed.hexdigest()
