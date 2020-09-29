import numpy as np
import h5py
import re
import pathlib
from datetime import datetime


class JRCLUST:

    def __init__(self, filepath):
        self.filepath = pathlib.Path(filepath)
        with h5py.File(filepath, mode='r') as ef:
            if 'S_clu' in ef:
                self.JRCLUST_version = 'jrclust_v3'
            elif 'spikeClusters' in ef:
                self.JRCLUST_version = 'jrclust_v4'
            else:
                raise ValueError('Unknown JRClust version')

        self._data = None
        self.creation_time = datetime.fromtimestamp(self.filepath.stat().st_ctime)

    @property
    def data(self):
        if self._data is None:
            if self.JRCLUST_version == 'jrclust_v3':
                self._data = _load_jrclust_v3(self.filepath)
            elif self.JRCLUST_version == 'jrclust_v4':
                self._data = _load_jrclust_v4(self.filepath)
            else:
                raise ValueError('Unknown JRClust version')
        return self._data


def _load_jrclust_v3(fpath):
    ef = h5py.File(str(fpath), mode='r')  # ephys file

    # extract unit data

    hz = ef['P']['sRateHz'][0][0]                   # sampling rate

    spikes = ef['viTime_spk'][0]                    # spike times
    spike_sites = ef['viSite_spk'][0]               # spike electrode
    spike_depths = ef['mrPos_spk'][1]               # spike depths

    units = ef['S_clu']['viClu'][0]                 # spike:unit id
    unit_wav = ef['S_clu']['trWav_raw_clu']         # waveform (unit x channel x sample)

    unit_notes = ef['S_clu']['csNote_clu'][0]       # curation notes
    unit_notes = _decode_notes(ef, unit_notes)

    unit_xpos = ef['S_clu']['vrPosX_clu'][0]        # x position
    unit_ypos = ef['S_clu']['vrPosY_clu'][0]        # y position

    unit_amp = ef['S_clu']['vrVpp_uv_clu'][0]       # amplitude
    unit_snr = ef['S_clu']['vrSnr_clu'][0]          # signal to noise

    vmax_unit_site = ef['S_clu']['viSite_clu']      # max amplitude site
    vmax_unit_site = np.array(vmax_unit_site[:].flatten(), dtype=np.int64)

    data = {
        'method': 'jrclust_v3',
        'hz': hz,
        'spikes': spikes,
        'spike_sites': spike_sites,
        'spike_depths': spike_depths,
        'units': units,
        'unit_wav': unit_wav,
        'unit_notes': unit_notes,
        'unit_xpos': unit_xpos,
        'unit_ypos': unit_ypos,
        'unit_amp': unit_amp,
        'unit_snr': unit_snr,
        'vmax_unit_site': vmax_unit_site
    }

    return data


def _load_jrclust_v4(fpath):
    ef = h5py.File(str(fpath), mode='r')  # ephys file

    # extract unit data
    hz = None                                       # sampling rate  (N/A from jrclustv4)

    spikes = ef['spikeTimes'][0]                    # spikes times
    spike_sites = ef['spikeSites'][0]               # spike electrode
    spike_depths = ef['spikePositions'][0]           # spike depths

    units = ef['spikeClusters'][0]                  # spike:unit id
    unit_wav = ef['meanWfLocalRaw']                 # waveform

    unit_notes = ef['clusterNotes']                 # curation notes
    unit_notes = _decode_notes(ef, unit_notes[:].flatten())

    unit_xpos = ef['clusterCentroids'][0]           # x position
    unit_ypos = ef['clusterCentroids'][1]           # y position

    unit_amp = ef['unitVppRaw'][0]                  # amplitude
    unit_snr = ef['unitSNR'][0] if 'unitSNR' in ef else np.full_like(unit_amp, np.nan)  # signal to noise

    vmax_unit_site = ef['clusterSites']             # max amplitude site
    vmax_unit_site = np.array(vmax_unit_site[:].flatten(), dtype=np.int64)

    data = {
        'method': 'jrclust_v4',
        'hz': hz,
        'spikes': spikes,
        'spike_sites': spike_sites,
        'spike_depths': spike_depths,
        'units': units,
        'unit_wav': unit_wav,
        'unit_notes': unit_notes,
        'unit_xpos': unit_xpos,
        'unit_ypos': unit_ypos,
        'unit_amp': unit_amp,
        'unit_snr': unit_snr,
        'vmax_unit_site': vmax_unit_site
    }

    return data


def _decode_notes(fh, notes):
    '''
    dereference and decode unit notes, translate to local labels
    '''
    note_map = {'single': 'good', 'ok': 'ok', 'multi': 'multi',
                '\x00\x00': 'all'}  # 'all' is default / null label
    decoded_notes = []
    for n in notes:
        note_val = str().join(chr(c) for c in fh[n])
        match = [k for k in note_map if re.match(k, note_val)]
        decoded_notes.append(note_map[match[0]] if len(match) > 0 else 'all')

    return decoded_notes
