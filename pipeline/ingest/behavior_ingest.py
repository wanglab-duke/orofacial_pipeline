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

"""
For debugging purposes (to be removed)
from pipeline.ingest import behavior_ingest
from pipeline.ingest.loaders.vincent import VincentLoader
self = VincentLoader('Z:/Vincent/Ephys/', dj.config)
key= {'subject_id': 'vIRt49', 'session': 4}
subject_name = 'vIRt49'
"""


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

        session_basename = (experiment.Session & key).fetch1('session_basename')

        # Expecting the "loader.load_behavior()" method to return a list of dictionary
        # each member dict represents behavior data for one session

        # passing `key` as first arguments returns this error:
        # load_behavior() takes 4 positional arguments but 5 were given
        # that doesn't seem to be a problem for load_tracking ... Or is it?
        all_behavior_data = loader.load_behavior(session_dir, key['subject_id'], session_basename)

        for behavior_data in all_behavior_data:
            # ---- insert to relevant tables ----
            experiment.Photostim.insert([{**key, **photostim} for photostim in behavior_data['photostims']],
                                        allow_direct_insert=True, ignore_extra_fields=True)
            experiment.SessionTrial.insert([{**key, **trial} for trial in behavior_data['session_trials']],
                                           allow_direct_insert=True, ignore_extra_fields=True)
            experiment.BehaviorTrial.insert([{**key, **trial} for trial in behavior_data['behavior_trials']],
                                            allow_direct_insert=True, ignore_extra_fields=True)
            experiment.PhotostimTrial.insert([{**key, **photostim_trial} for photostim_trial in behavior_data['photostim_trials']],
                                           allow_direct_insert=True, ignore_extra_fields=True)
            experiment.PhotostimEvent.insert([{**key, **photostim_event} for photostim_event in behavior_data['photostim_events']],
                                           allow_direct_insert=True, ignore_extra_fields=True)

            # insert into self
            self.insert1(key)
            log.info(f'Inserted behavior data for: {key}')
