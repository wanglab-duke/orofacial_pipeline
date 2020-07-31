
'''
MAP Motion Tracking Schema
'''

import datajoint as dj
import numpy as np

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
        position_x=null:  longblob # 
        position_y=null:  longblob # 
        speed=null:       longblob # 
        """

    class ObjectTracking(dj.Part):
        definition = """  # x, y coordinates over time of a representative point on the object (e.g. the centroid)
        -> master
        -> lab.ExperimentObject
        ---
        object_x:     longblob  # (px) 
        object_y:     longblob  # (px) 
        """

    class ObjectPoint(dj.Part):
        definition = """  # Tracked points per object
        -> master
        -> Tracking.ObjectTracking
        point_id:     int       # point id
        ---
        point_x:     longblob  # (px) 
        point_y:     longblob  # (px)  
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


# ---- Processed object data ----


@schema
class WhiskerObjectDistance(dj.Computed):
    definition = """
    -> Tracking.ObjectTracking
    -> Tracking.WhiskerTracking
    ---
    distance: longblob  #  euclidean distance over time between a whisker and an object, relative to animal's face
    """

    def make(self, key):
        # example code
        obj_x, obj_y = (Tracking.ObjectTracking & key).fetch1('object_x', 'object_y')
        fol_x, fol_y, face_x, face_y = (Tracking.ObjectTracking & key).fetch1(
            'follicle_x', 'follicle_y', 'face_x', 'face_y')

        face_pos = np.array([face_x, face_y])
        obj_pos = np.array([obj_x, obj_y])
        fol_pos = np.array([fol_x, fol_y])

        dist = np.linalg.norm((fol_pos - face_pos) - (obj_pos - face_pos), axis=0)

        self.insert1({**key, 'distance': dist})
