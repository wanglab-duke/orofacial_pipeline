import datajoint as dj
import numpy as np

from . import lab
from . import get_schema_name

schema = dj.schema(get_schema_name('experiment'))


@schema
class Session(dj.Manual):
    definition = """
    -> lab.Subject
    session: smallint 		# session number 
    ---
    session_date: date
    session_time: time  # t=0 is the start of the data acquisition from the master device (typically with the highest sampling rate, e.g., ephys acquisition device)
    unique index (subject_id, session_date, session_time)
    -> lab.Person
    -> lab.Rig
    """


@schema
class Task(dj.Lookup):
    definition = """
    # Type of tasks
    task            : varchar(24)                  # task type
    ----
    task_description : varchar(4000)
    """

    contents = [
        ('fm texture discrim', 'freely moving texture discrimination)'),
        ('hf texture discrim', 'head fixed texture discrimination)'),
        ('hf pole loc', 'head fixed pole localization)'),
        ('hf wall dist', 'head-fixed wall distance'),
        ('hf wheel', 'head-fixed wheel runing'),
        ('gen tun', 'unstructured generic tuning stimulation)')
    ]


@schema
class TaskProtocol(dj.Lookup):
    definition = """
    # SessionType
    -> Task
    task_protocol : tinyint # task protocol
    ---
    task_protocol_description : varchar(4000)
    """

    contents = []


# ---- Photostimulation ----

@schema
class Photostim(dj.Manual):
    definition = """  # Photostim protocol
    -> Session
    photo_stim :  smallint  # photostim protocol number
    ---
    -> lab.PhotostimDevice
    power : decimal(4,1)  # mW/mm²
    pulse_duration=null:  decimal(8,4)   # (s)
    pulse_frequency=null: decimal(8,4)   # (Hz)
    pulses_per_train=null: smallint #
    waveform=null:  longblob # normalized to maximal power.
    """
   
    class PhotostimLocation(dj.Part): 
        definition = """ # Location of Fiber Optic Cannula
        -> master
        -> lab.SkullReference
        ap_location: decimal(6, 2) # (um) anterior-posterior; ref is 0; more anterior is more positive
        ml_location: decimal(6, 2) # (um) medial axis; ref is 0 ; more right is more positive
        depth:       decimal(6, 2) # (um) manipulator depth relative to surface of the brain (0); more ventral is more negative
        theta:       decimal(5, 2) # (deg) - elevation - rotation about the ml-axis [0, 180] - w.r.t the z+ axis
        phi:         decimal(5, 2) # (deg) - azimuth - rotation about the dv-axis [0, 360] - w.r.t the x+ axis
        ---
        -> lab.BrainArea           # target brain area for photostim 
        """

@schema
class PhotostimBrainRegion(dj.Computed):
    definition = """
    -> Photostim
    ---
    -> lab.BrainArea.proj(stim_brain_area='brain_area')
    stim_laterality: enum('left', 'right', 'both')
    """

    def make(self, key):
        brain_areas, ml_locations = (Photostim.PhotostimLocation & key).fetch('brain_area', 'ml_location')
        ml_locations = ml_locations.astype(float)
        if len(set(brain_areas)) > 1:
            raise ValueError('Multiple different brain areas for one photostim protocol is unsupported')
        if (ml_locations > 0).any() and (ml_locations < 0).any():
            lat = 'both'
        elif (ml_locations > 0).all():
            lat = 'right'
        elif (ml_locations < 0).all():
            lat = 'left'
        else:
            assert (ml_locations == 0).all()  # sanity check
            raise ValueError('Ambiguous hemisphere: ML locations are all 0...')

        self.insert1(dict(key, stim_brain_area=brain_areas[0], stim_laterality=lat))

# --- Fiber photometry Imaging ----

@schema
class FPImaging(dj.Manual):
    definition = """  # Fiber photometry protocol
    -> Session
    ---
    -> lab.FiberPhotometryDevice
    wavelength_1_power : decimal(3,1)  # %
    wavelength_2_power : decimal(3,1)  # %
    NDF_ON : bool # The 470nm LED on FP3001 comes with a removable neutral density filter that reduces the output power to ~20% of its original power.
    isosbestic_power : decimal(3,1)  # %
    sampling_rate=null: decimal(8,4)   # (Hz)
    """

    class ImagingLocation(dj.Part): 
        definition = """ # Location of Fiber Optic Cannula
        -> master
        -> lab.SkullReference
        ap_location: decimal(6, 2) # (um) anterior-posterior; ref is 0; more anterior is more positive
        ml_location: decimal(6, 2) # (um) medial axis; ref is 0 ; more right is more positive
        depth:       decimal(6, 2) # (um) manipulator depth relative to surface of the brain (0); more ventral is more negative
        theta:       decimal(5, 2) # (deg) - elevation - rotation about the ml-axis [0, 180] - w.r.t the z+ axis
        phi:         decimal(5, 2) # (deg) - azimuth - rotation about the dv-axis [0, 360] - w.r.t the x+ axis
        ---
        -> lab.BrainArea           # target brain area for FP imaging 
        """


@schema
class FPImagingBrainRegion(dj.Computed):
    definition = """
    -> FP_Imaging
    ---
    -> lab.BrainArea.proj(FP_brain_area='brain_area')
    FOC_laterality: enum('left', 'right', 'both')
    """

    def make(self, key):
        brain_areas, ml_locations = (FPImaging.ImagingLocation & key).fetch('brain_area', 'ml_location')
        ml_locations = ml_locations.astype(float)
        if len(set(brain_areas)) > 1:
            raise ValueError('Multiple different brain areas for one fiber photometry  is unsupported')
        if (ml_locations > 0).any() and (ml_locations < 0).any():
            lat = 'both'
        elif (ml_locations > 0).all():
            lat = 'right'
        elif (ml_locations < 0).all():
            lat = 'left'
        else:
            assert (ml_locations == 0).all()  # sanity check
            raise ValueError('Ambiguous hemisphere: ML locations are all 0...')

        self.insert1(dict(key, FP_brain_area=brain_areas[0], FOC_laterality=lat))


# ---- Session Trial structure ----

@schema
class SessionTrial(dj.Imported):
    definition = """
    -> Session
    trial : smallint 		# trial number (1-based indexing)
    ---
    trial_uid : int  # unique across sessions/animals
    start_time : decimal(9, 4)  # (s) relative to session beginning 
    stop_time : decimal(9, 4)  # (s) relative to session beginning 
    """


@schema 
class TrialNoteType(dj.Lookup):
    definition = """
    trial_note_type : varchar(12)
    """
    contents = zip(('autolearn', 'protocol #', 'bad', 'bitcode'))


@schema
class TrialNote(dj.Imported):
    definition = """
    -> SessionTrial
    -> TrialNoteType
    ---
    trial_note  : varchar(255) 
    """


@schema
class TrainingType(dj.Lookup):
    definition = """
    # Mouse training
    training_type : varchar(100) # mouse training
    ---
    training_type_description : varchar(2000) # description
    """
    contents = []


@schema
class SessionTraining(dj.Manual):
    definition = """
    -> Session
    -> TrainingType
    """


@schema
class SessionTask(dj.Manual):
    definition = """
    -> Session
    -> TaskProtocol
    """


@schema
class SessionComment(dj.Manual):
    definition = """
    -> Session
    session_comment : varchar(767)
    """


# ---- behavioral trials ----

@schema
class BehaviorTrial(dj.Imported):
    definition = """
    -> SessionTrial
    ----
    -> TaskProtocol
    """


@schema
class TrialOutcome(dj.Imported):
    definition = """
    -> BehaviorTrial
    ---
    outcome: enum('correct', 'incorrect')
    """


@schema
class TrialObject(dj.Imported):
    definition = """
    -> BehaviorTrial
    -> lab.ExperimentObject
    ---
    distance_x: decimal(8,4)  # (mm) from the animal's face (0 is centered on whisker pad) to the object's center / tip.
    distance_y: decimal(8,4)  # (mm) from the animal's face (0 is centered on whisker pad) to the object's center / tip.
    distance_z: decimal(8,4)  # (mm) from the animal's face (0 is centered on whisker pad) to the object's center / tip.
    direction=null: varchar(50)     # (forward, backward, looming ...) - If not static
    texture=null: varchar(50)       # (rough / smooth / grit density) - For texture panels
    strength=null: decimal(8,4)     # (in g) - for von Freys
    temperature=null: decimal(8,4)  # (degrees Celsius) - for heat/cold experiments
    """


# -- trial events and action events --

@schema
class TrialEventType(dj.Lookup):
    definition = """
    trial_event_type  : varchar(12)  
    """
    contents = zip(('delay', 'go', 'sample', 'presample', 'trialend'))


@schema
class TrialEvent(dj.Imported):
    definition = """
    -> BehaviorTrial 
    trial_event_id: smallint
    ---
    -> TrialEventType
    trial_event_time : decimal(8, 4)   # (s) from trial start, not session start
    duration : decimal(8,4)  #  (s)  
    """


@schema
class ActionEventType(dj.Lookup):
    definition = """
    action_event_type : varchar(32)
    ----
    action_event_description : varchar(1000)
    """

    contents = [('left lick', ''),
                ('right lick', ''),
                ('middle lick', '')]


@schema
class ActionEvent(dj.Imported):
    definition = """
    -> BehaviorTrial
    action_event_id: smallint
    ---
    -> ActionEventType
    action_event_time : decimal(8,4)  # (s) from trial start
    """


# ---- Photostim trials ----


@schema
class PhotostimTrial(dj.Imported):
    definition = """
    -> SessionTrial
    """


@schema
class PhotostimEvent(dj.Imported):
    definition = """
    -> PhotostimTrial
    photostim_event_id: smallint
    ---
    -> Photostim
    photostim_event_time : decimal(8,3)   # (s) from trial start
    power : decimal(8,3)   # Maximal power (mW)
    """


# ============================= PROJECTS ==================================================


@schema
class Project(dj.Lookup):
    definition = """
    project_name: varchar(128)
    ---
    project_desc='': varchar(1000) 
    publication='': varchar(256)  # e.g. publication doi    
    """

    contents = [('vIRt', 'rhythmic whisking premotor circuits', ''),
                ('trigeminal', 'whisker touch brainstem neurophysiology', '')]
