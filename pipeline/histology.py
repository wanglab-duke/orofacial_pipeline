import datajoint as dj

from . import lab, experiment, ccf, ephys
from . import get_schema_name
[lab, experiment, ccf, ephys]  # schema imports only

schema = dj.schema(get_schema_name('histology'))


@schema
class ElectrodeCCFPosition(dj.Imported):
    definition = """
    -> ephys.ProbeInsertion
    """

    class ElectrodePosition(dj.Part):
        definition = """
        -> master
        -> lab.ElectrodeConfig.Electrode
        ---
        -> ccf.CCF
        """


@schema
class LabeledProbeTrack(dj.Imported):
    definition = """
    -> ephys.ProbeInsertion
    ---
    labeling_date=NULL:         date
    dye_color=NULL:             varchar(32)
    """

    class Point(dj.Part):
        definition = """
        -> master
        order: int
        shank: int
        ---
        ccf_x: float  # (um)
        ccf_y: float  # (um)
        ccf_z: float  # (um)    
        """
