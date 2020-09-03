import datajoint as dj
from pipeline import lab, experiment, tracking
from pipeline import get_schema_name

from pipeline.ingest import session_ingest, get_loader

schema = dj.schema(get_schema_name('ingestion'))


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
        loader = get_loader()
        sess_dir = (session_ingest.InsertedSession & key).fetch1('sess_data_dir')
        sess_dir = loader.root_data_dir / sess_dir
        ephys_data = loader.load_ephys(key, sess_dir)

        # iterate through each probe, insert data into relevant tables (see docstring)
        for probe_data in ephys_data:
            # parse and insert data
            pass
