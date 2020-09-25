import os
import sys
import logging
from code import interact
from datetime import datetime
from textwrap import dedent
import time
import numpy as np
import pandas as pd
import re
import datajoint as dj
from pymysql.err import OperationalError


from pipeline import (lab, experiment, tracking, ephys, psth, ccf, histology, get_schema_name)

pipeline_modules = [lab, ccf, experiment, ephys, histology, tracking, psth]

log = logging.getLogger(__name__)


# ==== UTILITY METHODS ====

def usage_exit():
    print(dedent(
        '''
        usage: {} cmd args

        where 'cmd' is one of:

        {}
        ''').lstrip().rstrip().format(
            os.path.basename(sys.argv[0]),
            str().join("  - {}: {}\n".format(k, v[1])
                       for k, v in actions.items())))

    sys.exit(0)


def shell(*args):
    interact('map shell.\n\nschema modules:\n\n  - {m}\n'
             .format(m='\n  - '.join(
                 '.'.join(m.__name__.split('.')[1:])
                 for m in pipeline_modules)),
             local=globals())


def logsetup(*args):
    level_map = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET,
    }
    level = level_map[args[0]] if args else logging.INFO

    logfile = dj.config.get('custom', {'logfile': None}).get('logfile', None)

    if logfile:
        handlers = [logging.StreamHandler(), logging.FileHandler(logfile)]
    else:
        handlers = [logging.StreamHandler()]

    datefmt = '%Y-%m-%d %H:%M:%S'
    msgfmt = '%(asctime)s:%(levelname)s:%(module)s:%(funcName)s:%(message)s'

    logging.basicConfig(format=msgfmt, datefmt=datefmt, level=logging.ERROR,
                        handlers=handlers)

    log.setLevel(level)

    logging.getLogger('pipeline').setLevel(level)
    logging.getLogger('pipeline.psth').setLevel(level)
    logging.getLogger('pipeline.ccf').setLevel(level)
    logging.getLogger('pipeline.ingest.session_ingest').setLevel(level)
    logging.getLogger('pipeline.ingest.behavior_ingest').setLevel(level)
    logging.getLogger('pipeline.ingest.tracking_ingest').setLevel(level)


# ==== ROUTINE TO OPERATE THE PIPELINE ====


def ingest_all(subject_id):
    populate_settings = {'reserve_jobs': True, 'suppress_errors': True, 'display_progress': True}

    from .ingest import behavior_ingest, tracking_ingest, ephys_ingest
    from .ingest.session_ingest import load_all_sessions

    load_all_sessions(subject_id)

    behavior_ingest.BehaviorIngestion.populate(**populate_settings)
    tracking_ingest.TrackingIngestion.populate(**populate_settings)
    ephys_ingest.EphysIngestion.populate(**populate_settings)


# ==== Action Mapper - for interactive shell ====

actions = {
    'ingest-all': (ingest_all, 'run auto ingest job (load all types)'),
    'shell': (shell, 'interactive shell')
}

