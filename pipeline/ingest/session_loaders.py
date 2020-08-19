import pathlib
import numpy as np
import re
from datetime import datetime

"""
This module houses all loader classes for loading sessions' behavioral data
Any loader class must have the following interfaces:

    `load_sessions` function:
        Input: 
            + root_data_dir: root directory of the data for all subjects
            + subject_name: subject name (i.e. "subject_id" in lab.Subject
        Output: A list of dictionary, each represents one session to be ingested, with the following keys:
            + subject_id: (str) subject id
            + session_date: (date) session's date 
            + session_time: (time) session's time 
            + username: experimenter's username associated with this session (i.e. "username" in lab.Person)
            + rig: the rig the session performed on (i.e. "rig" in lab.Rig)
            + session_files: list of associated files (relative path with respect to the root data directory)

    `load_behavior` function:
        Input:
        Output:
            
"""


class VincentLoader:

    def __init__(self, root_data_dir, config={}):
        self.config = config
        self.root_data_dir = pathlib.Path(root_data_dir)
        self.loader_name = self.__class__.__name__

    def load_sessions(self, subject_name):
        subj_dir = self.root_data_dir / subject_name
        if not subj_dir.exists():
            raise FileNotFoundError(f'{subj_dir} not found!')

        # assuming the ".avi" file must exist - find all .avi - each represents one session
        all_sess_avi = list(subj_dir.rglob(f'{subject_name}_*.avi'))

        # ---- detail parsing of the avi filename for further information:
        for f in all_sess_avi:
            match = re.search('_(\d{8}-\d{6})_', f.name)
            # find datetime string in avi name - assuming format: %Y%m%d-%H%M%S
            sess_datetime = datetime.strptime(match.groups()[0], '%Y%m%d-%H%M%S')
            # find the basename of the other related files for this session
            date_dir = f.parent
            base_str = f.name[:match.span()[0]]
            # find all associated files
            session_files = [f.relative_to(self.root_data_dir) for f in date_dir.glob(f'{base_str}*')]

            yield {'subject_id': subject_name,
                   'session_date': sess_datetime.date(),
                   'session_time': sess_datetime.time(),
                   'session_files': session_files,
                   'username': self.config['custom']['username'],
                   'rig': self.config['custom']['rig']}

    def load_behavior(self):
        pass

    def load_tracking(self):
        pass

    def load_ephys(self):
        pass
