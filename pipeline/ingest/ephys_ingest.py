import datajoint as dj
from pipeline import lab, experiment, tracking
from pipeline import get_schema_name

from pipeline.ingest import session_ingest, get_loader

schema = dj.schema(get_schema_name('ingestion'))

loader = get_loader()


@schema
class EphysIngestion(dj.Imported):
    definition = """
    -> session_ingest.InsertedSession
    """

    class EphysFile(dj.Part):
        definition = """  # file(s) associated with a session
        -> master
        filepath: varchar(255)  # relative filepath with respect to root data directory
        """

    def make(self, key):
        """
        Per probe, insert data into:
        + ProbeInsertion
            + lab.Probe
            + lab.ElectrodeConfig
        + ProbeInsertion.RecordingSystemSetup
        + LFP and LFP.Channel (if applicable)
        + Clustering
        + Unit and Unit.Waveform
        + PhotoTaggedUnit (if applicable)
        """
        # ---- call loader ----
        session_dir = (session_ingest.InsertedSession & key).fetch1('sess_data_dir')
        session_dir = loader.root_data_dir / session_dir
        session_basename = (experiment.Session & key).fetch1('session_basename')

        # Expecting the "loader.load_ephys()" method to return a list of dictionary
        # each member dict represents ephys data from one probe
        all_ephys_data = loader.load_ephys(key, session_dir, key['subject_id'], session_basename)

        # DO the table insert
        pass