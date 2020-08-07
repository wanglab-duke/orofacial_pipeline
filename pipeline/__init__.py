import logging

import datajoint as dj
import hashlib

log = logging.getLogger(__name__)

default_db_prefix = 'cosmo_'

# safe-guard in case `custom` is not provided
if 'custom' not in dj.config:
    dj.config['custom'] = {}


def get_schema_name(name):
    return dj.config['custom'].get('database.prefix', default_db_prefix) + name


def dict_to_hash(key):
    """
    Given a dictionary `key`, returns a hash string
    """
    hashed = hashlib.md5()
    for k, v in sorted(key.items()):
        hashed.update(str(k).encode())
        hashed.update(str(v).encode())
    return hashed.hexdigest()
