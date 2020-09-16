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

        # ---- get Photostim parameters (need to export notes first) ----
        photostim_params = sessinfo.get('photoStim')  #
        if photostim_params:
            if not isinstance(photostim_params, list):
                photostim_params_copy = photostim_params.copy()
                photostim_params = [photostim_params_copy]

            photostims = []  
            for psp in photostim_params:
                photostim = {'photo_stim': psp['protocolNum'],
                             'photostim_device': psp['stimDevice'],
                             'power': psp['stimPower'],
                             'pulse_duration': psp['pulseDur'],
                             'pulse_frequency': psp['stimFreq'],
                             'pulses_per_train': psp['trainLength'],
                             'waveform': psp.get('waveform', []),
                             **psp.get('photostim_location', {})}  # TODO: get photostim_location from FO implant info
                photostims.append(photostim)

        # ---- load files with TTLs and trial data ----
        ephys_dir = session_dir / 'SpikeSorting' / session_basename
        if not ephys_dir.exists():
            raise FileNotFoundError(f'{ephys_dir} not found!')
        ttl_file = os.path.join(ephys_dir, session_basename + '_TTLs.dat')
        with open(ttl_file, 'rb') as fid:
            ttl_ts = np.fromfile(fid, np.single)
        # load .dat with numpy. Load into 2 columns: .reshape((-1, 2)); to transpose: .T

        # ---- get trial info ----
        # (can be found in session's json file, or read from trial.csv. Frst solution is the most straightforward)
        power = photostims[0]['power']  # TODO: hardcoded using "power" from the 1st photostim protocol in the list, verify this
        trial_structure = sessinfo.get('trials')
        if trial_structure:
            # get trial structure then apply structure to TTLs
            session_trials = []
            photostim_trials = []
            photostim_events = []
            ttl_id = np.arange(len(ttl_ts))
            photostim_power_array = np.tile(power, len(ttl_ts))
            for tr in trial_structure:
                trials = {'trial': tr['trialNum'],
                          'start_time': tr['start'],
                          'stop_time': tr['stop']}
                if tr['isphotostim']:
                    photostim_trial = {'trial': tr['trialNum']}
                    ttl_idx = (ttl_ts >= tr['start']) & (ttl_ts < tr['stop'])
                    photostim_event = {'trial': photostim_trial,
                                       'photostim_event_id': ttl_id[ttl_idx],
                                       'photostim_event_time': ttl_ts[ttl_idx]-tr['start'],
                                       'photostim_power': photostim_power_array[ttl_idx]}
                session_trials.append(trials)
                photostim_trials.append(photostim_trial)
                photostim_events.append(photostim_event)

        if subject_name.find('vIRt'):
            project = 'vIRt'
        else:
            project = []

        return [{'task': task,
                 'photostims': photostims,
                 'session_trials': session_trials,
                 'photostim_trials': photostim_trials,
                 'photostim_events': photostim_events,
                 'project': project}]

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

    def load_ephys(self, session_dir, subject_name, session_basename):
        analysis_dir = session_dir / 'Analysis' / f'{subject_name}_{session_basename}'
        if not analysis_dir.exists():
            raise FileNotFoundError(f'{analysis_dir} not found!')

        # Expect 3 files per probe: .spikes.mat; recInfo.mat; .prb
        # As an example, only expect one probe per session
        jrclust_fp = list(analysis_dir.glob('*.spikes.mat'))
        recinfo_fp = list(analysis_dir.glob('*recInfo.mat'))
        prb_adaptor_fp = list(analysis_dir.glob('*.prb'))

        if len(jrclust_fp) != 1:
            raise FileNotFoundError(f'Unable to find one JRCLUST file - Found: {jrclust_fp}')
        if len(recinfo_fp) != 1:
            raise FileNotFoundError(f'Unable to find one Recording Info file - Found: {recinfo_fp}')
        if len(prb_adaptor_fp) != 1:
            raise FileNotFoundError(f'Unable to find one Probe Adapter file - Found: {prb_adaptor_fp}')

        # read recInfo file
        recInfo = {}
        with h5py.File(str(recinfo_fp[0]), mode='r') as f:  # ephys file
            info = f['recInfo']
            recInfo['fs'] = info['samplingRate'][0][0]
            recInfo['channel_num'] = info['numRecChan'][0][0]

            rec_date = str().join(chr(c) for c in info['date'])
            recInfo['recording_time'] = datetime.strptime(rec_date, '%d_%b_%Y_%H_%M_%S')
            recInfo['recording_system'] = str().join(chr(c) for c in info['sys'])

        # read adapter file
        adapter = {}
        with open(prb_adaptor_fp[0], mode='r') as f:
            for line in f.readlines():
                if line.startswith('%') or line.startswith('\n'):
                    continue
                split_vals = line.split('=')
                k = split_vals[0]
                v = split_vals[1]
                try:
                    v_str = re.match('\[.*\]', v.strip()).group()
                    adapter[k.strip()] = ast.literal_eval(v_str.replace(' ', ','))
                except:
                    adapter[k.strip()] = v.strip()

        channel_map = np.array(adapter['channels'])

        # read JRCLUST results
        jrclust = JRCLUST(jrclust_fp[0])

        # probe type
        probe_type, _, adapter_type = prb_adaptor_fp[0].stem.split('_')

        probe_data = {'probe_type': probe_type,
                      'sampling_rate': recInfo['fs'],
                      'channel_num': recInfo['channel_num'],
                      'recording_time': recInfo['recording_time'],
                      'recording_system': recInfo['recording_system'],
                      'clustering_method': jrclust.JRCLUST_version,
                      'unit': jrclust.data['units'],
                      'unit_quality': jrclust.data['unit_notes'],
                      'electrode': channel_map[jrclust.data['vmax_unit_site']-1],
                      'unit_posx': jrclust.data['unit_xpos'],
                      'unit_posy': jrclust.data['unit_ypos'],
                      'spike_times': jrclust.data['spikes'],
                      'spike_sites': jrclust.data['spike_sites'],
                      'spike_depths': jrclust.data['spike_depths'],
                      'unit_amp': jrclust.data['unit_amp'],
                      'unit_snr': jrclust.data['unit_snr'],
                      'waveform': jrclust.data['unit_wav'],  # (unit x channel x sample)
                      'ephys_files': [fp.relative_to(self.root_data_dir) for fp in (jrclust_fp, recinfo_fp, prb_adaptor_fp)]
                      }

        return [probe_data]  # return a list of dictionary, one for data from one probe
