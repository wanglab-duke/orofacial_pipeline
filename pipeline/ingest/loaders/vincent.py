import pathlib
import re
import json
from datetime import datetime
import scipy.io as spio
import numpy as np

"""
This module houses a LoaderClass for Vincent's data format
    Input: 
        + root_data_dir: root directory of the data for all subjects
        + config: configuration parameters (typically, dj.config) 
        
Any loader class must have the following interfaces:

    `load_sessions` function:   finds the recording sessions for a subject, within the 
                                root data directory and locates the session files  
        Input: 
            + subject_name: subject name (i.e. "subject_id" in lab.Subject
        Output: A list of dictionary, each represents one session to be ingested, with the following keys:
            + subject_id: (str) subject id
            + session_date: (date) session's date 
            + session_time: (time) session's time 
            + session_basename: (str) the id to reference all session files 
            + username: experimenter's username associated with this session (i.e. "username" in lab.Person)
            + rig: the rig the session performed on (i.e. "rig" in lab.Rig)
            + session_files: list of associated files (relative path with respect to the root data directory)

    `load_behavior` function:   loads data related to trial structure, TTLs and 
                                any data not originating from ephys or video tracking
        Input: 
            + session_dir
            + subject_name 
            + session_basename
        Output:
        
    `load_tracking` function:   loads data output from video tracking
        Input:
        Output:
        
    `load_ephys` function:  loads processed ephys data
        Input:
        Output:
"""


class VincentLoader:

    tracking_camera = 'WT_Camera_Vincent 0'
    tracking_fps = 500
    default_task = 'hf wheel'

    def __init__(self, root_data_dir, config={}):
        self.config = config
        self.root_data_dir = pathlib.Path(root_data_dir)
        self.loader_name = self.__class__.__name__

    def load_sessions(self, subject_name):
        subj_dir = self.root_data_dir / subject_name
        if not subj_dir.exists():
            raise FileNotFoundError(f'{subj_dir} not found!')

        # find all 'Analysis' folders, which contain the processed files for each session
        all_sessions = list(subj_dir.rglob('**/*info.json'))

        # ---- parse processed data folders:
        for sess in all_sessions:
            with open(sess.absolute()) as f:
                sessinfo = json.load(f)
            sess_datetime = datetime.strptime(sessinfo['date'], '%d-%b-%Y %H:%M:%S')
            # if needed, short form date can be retrieved here. Else, get it from sess_datetime
            # sess_shortdate = sessinfo['shortDate']
            # find the basename of the other related files for this session
            sess_basename = sessinfo['baseName']
            data_dir = sess.parent
            # find all associated files
            session_files = [sess.relative_to(self.root_data_dir)
                             for sess in data_dir.glob(f'{sess_basename}*')]

            yield {'subject_id': subject_name,
                   'session_date': sess_datetime.date(),
                   'session_time': sess_datetime.time(),
                   'session_basename': sess_basename,
                   'session_files': session_files,
                   'username': self.config['custom']['username'],
                   'rig': self.config['custom']['rig']}

    def load_behavior(self, session_dir, subject_name, session_basename):
        # TODO: return data entries for tables
        #   Task            task
        #   Photostim       return all info available,
        #           PhotostimLocation Location can be provided later
        #   SessionTrial    trial number / start_time stop_time
        #   PhotostimTrial  trial number for trials that contain photostim
        #   PhotostimEvent  PhotostimTrial photostim_event_id  Photostim photostim_event_time power
        #   Project         project_name

        # ---- get task type from the session file ----
        session_info_file = list(session_dir.glob(f'{session_basename}*.json'))
        with open(session_info_file[0]) as f:
            sessinfo = json.load(f)
        task = sessinfo.get('task', 'hf wheel') # if task not specified, default to head-fixed wheel running

        # ---- get Photostim parameters (TODO: need to export that from notes first) ----
        photostim_params = sessinfo.get('photostim')  #
        if photostim_params:
            for psp in photostim_params: # TODO: change that bit of code to be able to ingest multiple protocols
                photo_stim = psp['protocolNum']
                photostimDevice = psp['photostimDevice']
                power = psp['power']
                pulse_duration = psp['pulse_duration']
                pulse_frequency = psp['pulse_frequency']
                pulses_per_train = psp['pulses_per_train']
                try:
                    waveform = psp['waveform']
                except KeyError:
                    waveform = []
                photostimLocation = psp['photostimLocation']

        # ---- get trial data (TODO: either add that to json file, or read from trial.csv) ----
        # let's assume it's in the json file (probably most straightforward solution)
        trial_structure = sessinfo.get('trials')
        if trial_structure:
            for tr in trial_structure:
                trial = tr['trialNum']
                start_time = tr['start_time']
                stop_time = tr['stop_time']
                if tr['isphotostim']:
                    photostimTrial = tr['trialNum']

        # ---- identify files with TTLs and trial data ----
        ephys_dir = session_dir / 'SpikeSorting' / session_basename
        if not ephys_dir.exists():
            raise FileNotFoundError(f'{ephys_dir} not found!')
        

    def load_tracking(self, session_dir, subject_name, session_datetime):
        # TODO: decide where wheel position data from rotary encoder goes.
        #  For now, this is considered tracking data, although it's not video based.

        # ---- identify the .mat file for tracking data ----
        tracking_dir = session_dir / 'WhiskerTracking'
        if not tracking_dir.exists():
            raise FileNotFoundError(f'{tracking_dir} not found!')
        datetime_str = datetime.strftime(session_datetime, '%Y%m%d%H%M%S')

        tracking_fp = list(tracking_dir.glob(f'{subject_name}*{datetime_str}*.mat'))

        if len(tracking_fp) != 1:
            raise FileNotFoundError(f'Unable to find tracking .mat - Found: {tracking_fp}')
        else:
            tracking_fp = tracking_fp[0]

        # ---- load .mat and extract whisker data ----
        trk_mat = spio.loadmat(tracking_fp, struct_as_record=False, squeeze_me=True)[tracking_fp.stem]

        frames = np.arange(max(trk_mat.fid) + 1)  # frame number with respect to tracking

        whisker_inds = np.unique(trk_mat.wid)
        whiskers = {wid: {} for wid in whisker_inds}
        for wid in whisker_inds:
            matched_wid = trk_mat.wid == wid
            matched_fid = trk_mat.fid[matched_wid]
            _, matched_frame_idx, _ = np.intersect1d(matched_fid, frames, return_indices=True)

            for var in ('follicle_x', 'follicle_y', 'angle'):
                d = np.full(len(frames), np.nan)
                d[matched_frame_idx] = getattr(trk_mat, var)[matched_wid]
                whiskers[wid][var] = d

        # ---- Time sync ----
        # TODO: any time synchronization here
        # ---- return ----
        # Return a list of dictionary
        # each member dict represents tracking data for one tracking device

        return [{'tracking_device': self.tracking_camera,
                 'tracking_timestamps': frames / self.fps,
                 'tracking_files': [tracking_fp.relative_to(self.root_data_dir)],
                 'WhiskerTracking': [{'whisker_idx': wid, **wdata} for wid, wdata in whiskers.items()]}]

    def load_ephys(self):
        pass
