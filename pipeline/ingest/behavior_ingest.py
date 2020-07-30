import datajoint as dj

from pipeline import lab, experiment
from pipeline import get_schema_name
from . import session_loaders

schema = dj.schema(get_schema_name('behavior_ingest'))

# obtain user configured root data directory and session loader from dj.config
try:
    data_dir = dj.config['custom']['data_root_dir']
except KeyError:
    raise KeyError('Unspecified data root directory! Please specify "data_root_dir" under dj.config["custom"]')

try:
    session_loader_method = dj.config['custom']['session_loader_method']
except KeyError:
    raise KeyError('Unspecified session loader method! Please specify "session_loader_method" under dj.config["custom"]')

if session_loader_method in session_loaders.__dict__:
    session_loader = session_loaders.__dict__[session_loader_method]
else:
    raise RuntimeError(f'Unknown session loading function: {session_loader_method}')


@schema
class InsertedSession(dj.Imported):
    definition = """  # Ingestion-specific information about a session
    -> experiment.Session
    ---
    loader_method: varchar(16)  # name of loader method used
    """

    class SessionFile(dj.Part):
        definition = """  # file(s) associated with a session
        -> master
        filepath: varchar(255)  # relative filepath with respect to root data directory
        """


@schema
class SessionIngestion(dj.Imported):
    definition = """
    -> lab.Subject
    """

    def make(self, key):
        try:
            sessions_to_ingest = session_loaders(data_dir, key['subject_id'])
        except FileNotFoundError as e:
            print(str(e))
            return

        for sess in sessions_to_ingest:
            session_files = sess.pop('session_files')

            if experiment.Session & sess:
                continue

            # synthesize session number
            sess_num = (dj.U().aggr(experiment.Session()
                                    & {'subject_id': key['subject_id']},
                                    n='max(session)').fetch1('n') or 0) + 1
            # insert
            sess_key = {**sess, 'session': sess_num}

            experiment.Session.insert1(sess_key)
            InsertedSession.insert1({**sess_key, 'loader_method': session_loader_method})
            InsertedSession.SessionFile.insert([{**sess_key, 'filepath': f} for f in session_files])
            