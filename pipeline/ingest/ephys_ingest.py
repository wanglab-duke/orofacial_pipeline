import datajoint as dj
import numpy as np
import logging
from itertools import repeat

from pipeline import lab, experiment, ephys
from pipeline import get_schema_name, dict_to_hash

from pipeline.ingest import session_ingest, get_loader

schema = dj.schema(get_schema_name('ingestion'))

loader = get_loader()

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


"""
For debugging purposes (to be removed)
from pipeline.ingest import ephys_ingest
from pipeline.ingest.loaders.vincent import VincentLoader
self = VincentLoader('D:/Vincent/', dj.config)
key= {'subject_id': 'vIRt47', 'session': 7}
"""


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
        all_ephys_data = loader.load_ephys(session_dir, key['subject_id'], session_basename)

        ephys_files = []

        for insertion_number, ephys_data in enumerate(all_ephys_data):
            ephys_files.append(ephys_data.pop('ephys_files'))

            if 'probe' in ephys_data:
                probe_key = (lab.Probe & {'probe': ephys_data['probe']}).fetch1()
            elif 'probe_comment' in ephys_data:
                probe_key = (lab.Probe & {'probe_comment': ephys_data['probe_comment']}).fetch1()

            # ---- ProbeInsertion ----
            # From: probe and the electrodes used for recording
            e_config_key = _gen_electrode_config(probe_key, ephys_data['electrodes'])

            insertion_key = {**key, 'insertion_number': insertion_number}
            ephys.ProbeInsertion.insert1({**insertion_key, **probe_key, **e_config_key})
            ephys.ProbeInsertion.RecordingSystemSetup.insert1({**insertion_key,
                                                               'sampling_rate': ephys_data['sampling_rate'],
                                                               'adapter': ephys_data['adapter'],
                                                               'headstage': ephys_data['headstage']})

            # ---- Clustering ----
            method = ephys_data['clustering_method']

            if method not in ('jrclust_v3', 'jrclust_v4'):
                raise NotImplementedError('Ephys ingestion for clustering method: {} not yet implemented'.format(method))

            clustering_key = {**insertion_key, 'clustering_method': method}
            ephys.Clustering.insert1({**clustering_key,
                                      'clustering_time': ephys_data['clustering_time'],
                                      'quality_control': ephys_data['quality_control'],
                                      'manual_curation': ephys_data['manual_curation'],
                                      'clustering_note': ephys_data['clustering_note']})

            # ---- Units ----
            units = ephys_data['unit']
            spikes = ephys_data['spike_times']
            spike_sites = ephys_data['spike_sites']
            spike_depths = ephys_data['spike_depths']

            # remove noise clusters
            if method in ('jrclust_v3', 'jrclust_v4'):
                units, spikes, spike_sites, spike_depths = (v[i] for v, i in zip(
                    (units, spikes, spike_sites, spike_depths), repeat((units > 0))))

            spikes = spikes / ephys_data['sampling_rate']  # convert spike times to seconds

            # build spike arrays
            unit_spikes = np.array([spikes[np.where(units == u)] for u in set(units)])
            unit_spike_sites = np.array([spike_sites[np.where(units == u)] for u in set(units)])
            unit_spike_depths = np.array([spike_depths[np.where(units == u)] for u in set(units)])

            # electrode
            chn2electrodes = {eid: (lab.ProbeType.Electrode & probe_key & {'electrode': eid}).fetch1('KEY')
                              for eid in ephys_data['electrodes']}

            unit_list = []
            waveform_list = []
            for i, u in enumerate(set(units)):
                if method in ('jrclust_v3', 'jrclust_v4'):
                    wf_chn_idx = 0

                unit_list.append({**clustering_key,
                                  'unit': u,
                                  **chn2electrodes[ephys_data['unit_electrode'][i]],
                                  'unit_quality': ephys_data['unit_quality'][i],
                                  'unit_posx': ephys_data['unit_posx'][i],
                                  'unit_posy': ephys_data['unit_posy'][i],
                                  'unit_amp': ephys_data['unit_amp'][i],
                                  'unit_snr': ephys_data['unit_snr'][i],
                                  'spike_times': unit_spikes[i],
                                  'spike_sites': unit_spike_sites[i],
                                  'spike_depths': unit_spike_depths[i]})
                waveform_list.append({**clustering_key,
                                      'unit': u,
                                      'waveform': ephys_data['waveform'][i][wf_chn_idx]})


        # insert into self
        self.insert1(key)
        self.EphysFile.insert([{**key, 'filepath': f.as_posix()} for f in ephys_files],
                              allow_direct_insert=True, ignore_extra_fields=True)
        log.info(f'Inserted ephys for: {key}')


# ====== HELPER FUNCTIONS ======


def _gen_electrode_config(probe_key, electrode_list):
    """
    Generate ElectrodeConfig for non-neuropixels probes
    Insert into ElectrodeConfig table if not yet existed
    Return the ElectrodeConfig key
    """
    q_electrodes = lab.ProbeType.Electrode & probe_key
    eg_members = [(q_electrodes & {'electrode': eid}).fetch1('KEY') for eid in electrode_list]

    # ---- compute hash for the electrode config (hash of dict of all ElectrodeConfig.Electrode) ----
    ec_hash = dict_to_hash({k['electrode']: k for k in eg_members})

    el_list = sorted([k['electrode'] for k in eg_members])
    el_jumps = [-1] + np.where(np.diff(el_list) > 1)[0].tolist() + [len(el_list) - 1]
    ec_name = '; '.join([f'{el_list[s + 1]}-{el_list[e]}' for s, e in zip(el_jumps[:-1], el_jumps[1:])])

    e_config = {**probe_key, 'electrode_config_name': ec_name}

    # ---- make new ElectrodeConfig if needed ----
    if not (lab.ElectrodeConfig & {'electrode_config_hash': ec_hash}):
        lab.ElectrodeConfig.insert1({**e_config, 'electrode_config_hash': ec_hash})
        lab.ElectrodeConfig.ElectrodeGroup.insert1({**e_config, 'electrode_group': 0})  # fixed electrode_group = 0
        lab.ElectrodeConfig.Electrode.insert({**e_config, **m} for m in eg_members)

    return e_config


