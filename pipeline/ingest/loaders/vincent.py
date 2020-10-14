import os
import pathlib
import json
from datetime import datetime
import scipy.io as spio
import numpy as np
import h5py
import ast
import re

from .jrclust import JRCLUST


"""
This module houses a LoaderClass for Vincent's data format
    Input: 
        + root_data_dir: root directory of the data for all subjects
        + config: configuration parameters (typically, dj.config) 
        
Any loader class must have the following interfaces:

    `load_sessions` function:   finds the recording sessions for a subject, within the 
                                root data directory and locates the session files  
        Input: 
            + subject_name: subject name (i.e. "subject_id" in lab.Subject)
        Output: A list of dictionary, each represents one session to be ingested, with the following keys:
            + subject_id: (str) subject id
            + session_date: (date) session's date 
            + session_time: (time) session's time 
            + session_basename: (str) the id to reference all session files 
            + username: experimenter's username associated with this session (i.e. "username" in lab.Person)
            + rig: the rig the session performed on (i.e. "rig" in lab.Rig)
            + (optional) sessions_notes: (str) any notes associated with the session. May be filed later, e.g., through a notebook.  
            + session_files: list of associated files (relative path with respect to the root data directory)
            
    `load_behavior` function:   loads data related to trial structure, TTLs and 
                                any data not originating from ephys or video tracking
        Input: 
            + session_dir
            + subject_name 
            + session_basename
        Output:
            -- any information going into **experiment.py** schemas, besides Session
            -- e.g.: 
            + task
            + photostims 
            + session_trials
            + photostim_trials
            + photostim_events
            + project
        
    `load_tracking` function:   loads data output from video tracking
        Input:
            + session_dir
            + subject_name 
            + session_basename
        Output:
            -- any information going into **tracking.py** schemas 
            + tracking_device
            -- tracking data, to insert in Tracking
            + tracking_timestamps
            -- for example, variables to return for WhiskerTracking
                + whisker_idx
                + angle 
                + curvature:
                + face_x  
                + face_y   
                + follicle_x
                + follicle_y 
                + tip_x    
                + tip_y
            + tracking_files 

    `load_ephys` function:  loads processed ephys data
        Input:
            + session_dir
            + subject_name 
            + session_basename
        Output:
            -- any information going into **ephys.py** schemas, e.g.
            + probe_comment
            + adapter  
            + sampling_rate
            + electrodes
            + recording_timerecording_time
            + headstage  
            + clustering_method
            + clustering_time
            + quality_control  
            + manual_curation  
            + clustering_note   
            + unit
            + unit_quality
            + unit_electrode
            + unit_posx
            + unit_posy
            + spike_times
            + spike_sites
            + spike_depths
            + unit_amp
            + unit_snr
            + waveform
            + ephys_files
"""


class VincentLoader:

    tracking_camera = 'WT_Camera_Vincent 0'
    tracking_fps = 500
    default_task = 'hf wheel'
    default_task_protocol = 0

    def __init__(self, root_data_dir, config={}):
        self.config = config
        self.root_data_dir = pathlib.Path(root_data_dir)
        self.loader_name = self.__class__.__name__

    def load_sessions(self, subject_name):
        subj_dir = self.root_data_dir / subject_name
        if not subj_dir.exists():
            raise FileNotFoundError(f'{subj_dir} not found!')

        # find all sessions' json files, which contain the processed files for each session
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
        # return data entries for tables
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
        task = sessinfo.get('task', self.default_task) # if task not specified, set default (e.g, head-fixed wheel running)
        task_protocol = sessinfo.get('task_protocol', self.default_task_protocol) # same for task protocol

        # ---- get Photostim parameters (need to export notes first) ----
        photostim_params = sessinfo.get('photoStim')  #
        if photostim_params:
            if photostim_params['protocolNum'] == -1:
                photostim_params = None

        photostims = []
        photostim_locations = []
        if photostim_params:
            if not isinstance(photostim_params, list):
                photostim_params = [photostim_params.copy()]

            for psp in photostim_params:
                photostim = {'photo_stim': psp['protocolNum'],
                             'photostim_device': psp['stimDevice'],
                             'power': psp['stimPower'],
                             'pulse_duration': psp['pulseDur'],
                             'pulse_frequency': psp['stimFreq'],
                             'pulses_per_train': psp['trainLength'],
                             'waveform': psp.get('waveform', [])}
                photostims.append(photostim)
                if 'photostim_location' in psp:
                    stim_loc = psp['photostim_location']
                    stim_loc['skull_reference'] = stim_loc.pop('skullRef')
                    stim_loc['brain_area'] = stim_loc.pop('targetBrainArea')
                    if not bool(stim_loc['brain_area']):
                        stim_loc['brain_area'] = None
                    photostim_location = {'photo_stim': psp['protocolNum'], **stim_loc}
                    photostim_locations.append(photostim_location)

        # ---- load files with TTLs and trial data ----
        ephys_dir = session_dir / 'SpikeSorting' / session_basename # TODO: get TTLs from session directory, since some sessions do not have a spike sorting folder
        if not ephys_dir.exists():
            raise FileNotFoundError(f'{ephys_dir} not found!')
        ttl_file = os.path.join(ephys_dir, session_basename + '_TTLs.dat')
        if os.path.exists(ttl_file):
            with open(ttl_file, 'rb') as fid:
                # load .dat with numpy. Load into 2 columns: .reshape((-1, 2)); to transpose: .T
                ttl_ts = np.fromfile(fid, np.single)

        # ---- get trial info ----
        # (can be found in session's json file, or read from trial.csv. First solution is the most straightforward)
        try:
            photostim_mapper = {p['photo_stim']: p for p in photostims}
        except:
            photostim_mapper = None  #if no photostims present
        trial_structure = sessinfo.get('trials')
        if not isinstance(trial_structure, list):
            trial_structure = [trial_structure.copy()]

        session_trials, behavior_trials, photostim_trials, photostim_events = [], [], [], []

        if trial_structure:
            # get trial structure then apply structure to TTLs
            for tr in trial_structure:
                session_trials.append({'trial': tr['trialNum'], 'start_time': tr['start'], 'stop_time': tr['stop']})
                behavior_trials.append({'trial': tr['trialNum'], 'task': task, 'task_protocol': task_protocol})
                if tr['isphotostim']:
                    photostim_trials.append({'trial': tr['trialNum']})
                    # get photostim protocol
                    stim_protocol = tr.get('photo_stim', photostims[0]['photo_stim'])  # by default, assign first protocol number
                    # search through all photostim events
                    trial_ts = ttl_ts[(ttl_ts >= tr['start']) & (ttl_ts < tr['stop'])]  # ttl timestamps for this trial
                    photostim_event = [{'trial': tr['trialNum'],
                                        'photo_stim': photostim_mapper[stim_protocol]['photo_stim'], # assign the photostim protocol those photostim events correspond to
                                        'photostim_event_id': idx,
                                        'photostim_event_time': ts - tr['start'],
                                        'power': photostim_mapper[stim_protocol]['power']}
                                       for idx, ts in enumerate(trial_ts)]
                    photostim_events.extend(photostim_event)

        return [{'photostims': photostims,
                 'photostim_locations': photostim_locations,
                 'session_trials': session_trials,
                 'behavior_trials': behavior_trials,
                 'photostim_trials': photostim_trials,
                 'photostim_events': photostim_events}]

    def load_tracking(self, session_dir, subject_name, session_basename):
        # TODO: decide where wheel position data from rotary encoder goes.
        #  For now, this is considered tracking data, although it's not video based.

        # ---- identify the .mat file for tracking data ----
        tracking_dir = session_dir / 'WhiskerTracking'
        if not tracking_dir.exists():
            raise FileNotFoundError(f'{tracking_dir} not found!')
        # if the basename is defined by the session datetime, get files with something like this:
        # datetime_str = datetime.strftime(session_datetime, '%Y%m%d-%H%M%S')
        # tracking_fp = list(tracking_dir.glob(f'{subject_name}*{datetime_str}*.mat'))
        tracking_fp = list(tracking_dir.glob(f'{session_basename}*.mat'))

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

            for var in ('angle', 'curvature', 'follicle_x', 'follicle_y', 'face_x', 'face_y', 'tip_x', 'tip_y'):
                d = np.full(len(frames), np.nan)
                d[matched_frame_idx] = getattr(trk_mat, var)[matched_wid]
                whiskers[wid][var] = d

        # ---- Time sync ----
        # TODO: any time synchronization here
        # ---- return ----
        # Return a list of dictionary
        # each member dict represents tracking data for one tracking device

        return [{'tracking_device': self.tracking_camera,
                 'tracking_timestamps': frames / self.tracking_fps,
                 'tracking_files': [tracking_fp.relative_to(self.root_data_dir)],
                 'WhiskerTracking': [{'whisker_idx': wid, **wdata} for wid, wdata in whiskers.items()]}]

    def load_ephys(self, session_dir, subject_name, session_basename):
        spikesorting_dir = session_dir / 'SpikeSorting' / f'{session_basename}'
        if not spikesorting_dir.exists():
            raise FileNotFoundError(f'{spikesorting_dir} not found!')

        # Expect 3 files per probe: _res.mat; .json; .prb
        # As an example, only expect one probe per session
        jrclust_fp = list(spikesorting_dir.glob(f'{session_basename}*_res.mat'))
        sessioninfo_fp = list(session_dir.glob(f'{session_basename}*.json'))
        prb_adaptor_fp = list(spikesorting_dir.glob('*.prb'))

        if len(jrclust_fp) != 1:
            raise FileNotFoundError(f'Unable to find one JRCLUST file - Found: {jrclust_fp}')
        if len(sessioninfo_fp) != 1:
            raise FileNotFoundError(f'Unable to find one Recording Info file - Found: {sessioninfo_fp}')
        if len(prb_adaptor_fp) != 1:
            raise FileNotFoundError(f'Unable to find one Probe Adapter file - Found: {prb_adaptor_fp}')

        # read session info file
        rec_info = {}
        with open(sessioninfo_fp[0]) as f:
            sessinfo = json.load(f)
            rec_info['fs'] = sessinfo['samplingRate']
            rec_info['channel_num'] = sessinfo['numRecChan']
            rec_info['recording_time'] = datetime.strptime(sessinfo['date'], '%d-%b-%Y %H:%M:%S')
            rec_info['recording_system'] = sessinfo['sys']
            rec_info['chanList'] = sessinfo['chanList']

        # read probe file
        probe_params = {}
        with open(prb_adaptor_fp[0], mode='r') as f:
            for line in f.readlines():
                if line.startswith('%') or line.startswith('\n'):
                    continue
                split_vals = line.split('=')
                k = split_vals[0]
                v = split_vals[1]
                try:
                    v_str = re.match('\[.*\]', v.strip()).group()
                    probe_params[k.strip()] = ast.literal_eval(v_str.replace(' ', ','))
                except:
                    probe_params[k.strip()] = v.strip()

        channel_map = np.array(probe_params['channels'])

        # read JRCLUST results
        jrclust = JRCLUST(jrclust_fp[0])

        # probe type
        # probe_id = []  # probe id will be determine from probe_comment in ephys_ingest
        probe_comment = sessinfo['ephys']['probe']
        adapter = sessinfo['ephys']['adapter']
        headstage = rec_info['recording_system'] + '_' + adapter[adapter.find('OM') + 2:]

        probe_data = {'probe_comment': probe_comment,
                      'adapter': adapter,
                      'sampling_rate': rec_info['fs'],
                      'electrodes': rec_info['chanList'],
                      'recording_time': rec_info['recording_time'],
                      'headstage': headstage,
                      'clustering_method': jrclust.JRCLUST_version,
                      'clustering_time': jrclust.creation_time,
                      'quality_control': False,
                      'manual_curation': True,
                      'clustering_note': '',
                      'unit': jrclust.data['units'],
                      'unit_quality': jrclust.data['unit_notes'],
                      'unit_electrode': jrclust.data['vmax_unit_site'], # no need to use mapping, it's already remapped
                      'unit_posx': jrclust.data['unit_xpos'],
                      'unit_posy': jrclust.data['unit_ypos'],
                      'spike_times': jrclust.data['spikes'],
                      'spike_sites': jrclust.data['spike_sites'],
                      'spike_depths': jrclust.data['spike_depths'],
                      'unit_amp': jrclust.data['unit_amp'],
                      'unit_snr': jrclust.data['unit_snr'],
                      'waveform': jrclust.data['unit_wav'],  # (unit x channel x sample)
                      'ephys_files': [fp[0].relative_to(self.root_data_dir) for fp in (jrclust_fp, sessioninfo_fp, prb_adaptor_fp)]
                      }

        return [probe_data]  # return a list of dictionaries, one for the data from each probe
