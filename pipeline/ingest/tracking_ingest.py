import datajoint as dj
import logging

from pipeline import lab, experiment, tracking
from pipeline import get_schema_name

from pipeline.ingest import session_ingest, get_loader

schema = dj.schema(get_schema_name('ingestion'))

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


loader = get_loader()


@schema
class TrackingIngestion(dj.Imported):
    definition = """
    -> session_ingest.InsertedSession
    """

    class TrackingFile(dj.Part):
        definition = """  # file(s) associated with a session
        -> master
        filepath: varchar(255)  # relative filepath with respect to root data directory
        """

    # only run for sessions where the currently loaded LoaderClass is the same as the one used to load the experiment.Session
    key_source = session_ingest.InsertedSession & {'loader_method': loader.loader_name}

    def make(self, key):
        # ---- call loader ----
        session_dir = (session_ingest.InsertedSession & key).fetch1('sess_data_dir')
        session_dir = loader.root_data_dir / session_dir
        session_datetime = (experiment.Session & key).proj(
            session_datetime="cast(concat(session_date, ' ', session_time) as datetime)").fetch1('session_datetime')
        tracking_data = loader.load_tracking(key, session_dir, key['subject_id'], session_datetime)

        # ---- extract information from the imported data (from loader class) ----
        tracking_files = tracking_data.pop('tracking_files')
        part_tbl_data = {tbl_name: tracking_data.pop(tbl_name)
                         for tbl_name in tracking.Tracking.tracking_features if tbl_name in tracking_data}

        # ---- insert to relevant tracking tables ----
        with dj.conn().transaction:
            # insert to the main Tracking
            tracking.Tracking.insert1({**key, **tracking_data}, allow_direct_insert=True, ignore_extra_fields=True)
            # insert to the Tracking part-tables (different tracked features)
            for tbl_name, tbl_data in part_tbl_data.items():
                part_tbl = tracking.Tracking.tracking_features[tbl_name]
                if isinstance(tbl_data, dict):
                    part_tbl.insert1({**key, **tracking_data, **tbl_data}, allow_direct_insert=True, ignore_extra_fields=True)
                elif isinstance(tbl_data, list):
                    part_tbl.insert([{**key, **tracking_data, **d} for d in tbl_data], allow_direct_insert=True, ignore_extra_fields=True)
            # insert into self
            self.insert1(key)
            self.TrackingFile.insert([{**key, 'filepath': f.as_posix()} for f in tracking_files],
                                     allow_direct_insert=True, ignore_extra_fields=True)
            log.info(f'Inserted tracking for: {key}')


