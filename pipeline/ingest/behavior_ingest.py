import datajoint as dj
import logging
from datetime import datetime

from pipeline import lab, experiment
from pipeline import get_schema_name

from pipeline.ingest import session_ingest, get_loader

schema = dj.schema(get_schema_name('ingestion'))

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


loader = get_loader()


@schema
class BehaviorIngestion(dj.Imported):
    definition = """
    -> session_ingest.InsertedSession
    """

    class BehaviorFile(dj.Part):
        definition = """  # file(s) associated with a session
        -> master
        filepath: varchar(255)  # relative filepath with respect to root data directory
        """
    # only run for sessions where the currently loaded LoaderClass is the same as the one used to load the experiment.Session
    key_source = session_ingest.InsertedSession & {'loader_method': loader.loader_name}

    def make(self, key):
        """
        Per session, insert data into:
        + Task
        + Photostim       return all info available
            + PhotostimLocation Location can be provided later
        + SessionTrial
        + PhotostimTrial
        + PhotostimEvent
        + Project
        """
        # print(f'Working on this key: {key}')
        # key = {'subject_id': 'vIRt47', 'session': 1}
        # all files related to the key have filename nomenclature <subject_id'>_<date>_<ref>
        # date is in %m%d format. For recordings, <ref> is typically the probe's insertion depth
        session_dir = (session_ingest.InsertedSession & key).fetch1('sess_data_dir')
        session_dir = loader.root_data_dir / session_dir
        # don't pass session_datetime as argument. Modify tracking ingest later
        session_datetime = (experiment.Session & key).proj(
            session_datetime="cast(concat(session_date, ' ', session_time) as "
                             "datetime)").fetch1('session_datetime')
        session_date_str = datetime.strftime(session_datetime, '%m%d')
        #session_ref =

        # Expecting the "loader.load_behavior()" method to return a list of dictionary
        # each member dict represents behavior data for one session

        # passing `key` as first arguments returns this error:
        # load_behavior() takes 4 positional arguments but 5 were given
        # that doesn't seem to be a problem for load_tracking ... Or is it?
        all_behavior_data = loader.load_behavior(session_dir, key['subject_id'], session_date_str)


