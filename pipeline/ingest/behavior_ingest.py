import datajoint as dj

from pipeline import lab, experiment
from pipeline import get_schema_name
from pipeline.ingest import session_loaders

schema = dj.schema(get_schema_name('behavior_ingest'))

# ============== SETUP the LOADER ==================

try:
    data_dir = dj.config['custom']['data_root_dir']
except KeyError:
    raise KeyError('Unspecified data root directory! Please specify "data_root_dir" under dj.config["custom"]')

try:
    session_loader_class = dj.config['custom']['session_loader_class']
except KeyError:
    raise KeyError('Unspecified session loader method! Please specify "session_loader_method" under dj.config["custom"]')

if session_loader_class in dir(session_loaders):
    # instantiate a loader class with "data_dir" and "config" (optional)
    loader_class = getattr(session_loaders, session_loader_class)
else:
    raise RuntimeError(f'Unknown session loading function: {session_loader_class}')

# instantiate a loader class with "data_dir" and "config" (optional)
session_loader = loader_class(data_dir, dj.config)

# ============== BEHAVIOR INGESTION ==================


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
    # ---- parse data dir and load all sessions ----
    try:
        sessions_to_ingest = session_loader.load_sessions(subject_id)
    except FileNotFoundError as e:
        print(str(e))
        return

    # ---- work on each session ----
    for sess in sessions_to_ingest:
        session_files = sess.pop('session_files')

        if experiment.Session & sess:
            print(f'Session {sess} already exists. Skipping...')
            continue

        # ---- synthesize session number ----
        sess_num = (dj.U().aggr(experiment.Session()
                                & {'subject_id': subject_id},
                                n='max(session)').fetch1('n') or 0) + 1
        # ---- insert ----
        sess_key = {**sess, 'session': sess_num}

        experiment.Session.insert1(sess_key)
        InsertedSession.insert1({**sess_key,
                                 'loader_method': session_loader_class,
                                 'sess_data_dir': session_files[0].parent.as_posix()}, allow_direct_insert=True,
                                ignore_extra_fields=True)
        InsertedSession.SessionFile.insert([{**sess_key, 'filepath': f.as_posix()} for f in session_files],
                                           allow_direct_insert=True, ignore_extra_fields=True)


@schema
class SessionDetailsIngestion(dj.Imported):
    definition = """
    -> InsertedSession
    """

    def make(self, key):
        # ingest the remaining session related data (e.g. trials, objects, task protocol, photostim, etc.)
        session_loader.load_session_details()
        # ...
        pass