
'''
MAP Motion Tracking Schema
'''

import datajoint as dj

from . import experiment, lab
from . import get_schema_name

schema = dj.schema(get_schema_name('tracking'))
[experiment]  # NOQA flake8


@schema
class TrackingDevice(dj.Lookup):
    definition = """
    tracking_device:                    varchar(20)     # device type/function
    ---
    sampling_rate:                      decimal(8, 4)   # sampling rate (Hz)
    tracking_device_description:        varchar(100)    # device description
    """

    contents = []


@schema
class Tracking(dj.Imported):
    definition = """
    -> experiment.Session
    -> TrackingDevice
    ---
    tracking_timestamps: longblob  # (s) timestamps with respect to the start of the session
    """

    class PositionTracking(dj.Part):
        definition = """
        -> master
        ---
        position_x=null:  longblob # (px)
        position_x=null:  longblob # (px)
        speed=null:       longblob # (px/s)
        """

    class ObjectTracking(dj.Part):
        definition = """
        -> master
        -> lab.ExperimentObject
        ---
        object_x:     longblob  # (px)
        object_y:     longblob  # (px)
        """

    class WhiskerTracking(dj.Part):
        definition = """
        -> master
        whisker_idx:          int             # 0, 1, 2
        ---
        angle:         longblob  # mean angle at follicle
        curvature:     longblob  # mean curvature (1/mm)
        face_x:        longblob  # approximate center of whisker pad, x (px)
        face_y:        longblob  # approximate center of whisker pad, y (px) 
        follicle_x:    longblob  # follicle position: x (px)
        follicle_y:    longblob  # follicle position: y (px)
        tip_x:         longblob  # tip position: x (px)
        tip_y:         longblob  # tip position: y (px)
        """


@schema
class TrackedWhisker(dj.Manual):
    definition = """
    -> Tracking.WhiskerTracking
    """

    class Whisker(dj.Part):
        definition = """
        -> master
        -> lab.Whisker
        """


# ---- Processed Whisker data ----

@schema
class WhiskerProcessingParams(dj.Lookup):
    definition = """
    param_id: int
    ---
    
    """


@schema
class ProcessedWhisker(dj.Computed):
    definition = """
    -> Tracking.WhiskerTracking
    ---
    -> WhiskerProcessingParams
    amplitude: longblob
    velocity: longblob
    set_point: longblob
    angle: longblob
    angle_raw: longblob
    angle_bp: longblob
    frequency: longblob
    phase: longblob
    """

    def make(self, key):
        # call whisker processing function here
        pass

