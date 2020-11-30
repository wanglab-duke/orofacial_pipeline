import datajoint as dj
import logging

from pipeline import lab, experiment
from pipeline import get_schema_name
from pipeline.ingest import get_loader

schema = dj.schema(get_schema_name('ingestion'))


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

"""
For debugging purposes (to be removed)
from pipeline.ingest import session_ingest
#from pipeline.ingest.loaders.wenxi import WenxiLoader
#self = WenxiLoader('Z:/all_staff/Wenxi/PrV_Wall_Recordings/', dj.config)
from pipeline.ingest.loaders.vincent import VincentLoader
self = VincentLoader('Z:/Vincent/Ephys/', dj.config)
key= {'subject_id': 'vIRt47', 'session': 1}
subject_name = 'vIRt47'
"""

# ============== SESSION INGESTION ==================


@schema
class InsertedSession(dj.Imported):
    definition = """  # Ingestion-specific information about a session
    -> experiment.Session
    ---
    loader_method: varchar(16)  # name of loader method used
    sess_data_dir: varchar(255) # directory path for this session, relative to root data directory
    """

    class SessionFile(dj.Part):
        definition = """  # file(s) associated with a session
        -> master
        filepath: varchar(255)  # relative filepath with respect to root data directory
        """


def load_all_sessions(subject_id):
    loader = get_loader()
    # ---- parse data dir and load all sessions ----
    """
        For each session, return 
        + subject_name
        + session_date
        + session_time
        + session_basename
        + session_files
        + username
        + rig
    """
    try:
        sessions_to_ingest = loader.load_sessions(subject_id)
    except FileNotFoundError as e:
        print(str(e))
        return

    # ---- work on each session ----
    for sess in sessions_to_ingest:
        session_files = sess.pop('session_files')

        if experiment.Session & sess:
            log.info(f'Session {sess} already exists. Skipping...')
            continue

        # ---- synthesize session number ----
        sess_num = (dj.U().aggr(experiment.Session()
                                & {'subject_id': subject_id},
                                n='max(session)').fetch1('n') or 0) + 1
        # ---- insert ----
        sess_key = {**sess, 'session': sess_num}

        with dj.conn().transaction:
            experiment.Session.insert1(sess_key)
            InsertedSession.insert1({**sess_key,
                                     'loader_method': loader.loader_name,
                                     'sess_data_dir': session_files[0].parent.as_posix()},
                                    allow_direct_insert=True, ignore_extra_fields=True)
            InsertedSession.SessionFile.insert([{**sess_key, 'filepath': f.as_posix()} for f in session_files],
                                               allow_direct_insert=True, ignore_extra_fields=True)
            log.info(f'Inserted new session: {sess}')

