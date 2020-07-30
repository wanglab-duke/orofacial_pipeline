import logging
import hashlib

from functools import partial
from inspect import getmembers
from itertools import repeat
import numpy as np
import datajoint as dj
import scipy.stats as sc_stats

from . import (lab, experiment, ephys)
[lab, experiment, ephys]  # NOQA

from . import get_schema_name, dict_to_hash
from .util import _get_units_hemisphere

schema = dj.schema(get_schema_name('psth'))
log = logging.getLogger(__name__)


@schema
class TrialCondition(dj.Lookup):
    '''
    TrialCondition: Manually curated condition queries.

    Used to define sets of trials which can then be keyed on for downstream
    computations.
    '''

    definition = """
    trial_condition_name:       varchar(128)     # user-friendly name of condition
    ---
    trial_condition_hash:       varchar(32)     # trial condition hash - hash of func and arg
    unique index (trial_condition_hash)
    trial_condition_func:       varchar(36)     # trial retrieval function
    trial_condition_arg:        longblob        # trial retrieval arguments
    """

    @classmethod
    def get_trials(cls, trial_condition_name):
        return cls.get_func({'trial_condition_name': trial_condition_name})()

    @classmethod
    def get_cond_name_from_keywords(cls, keywords):
        matched_cond_names = []
        for cond_name in cls.fetch('trial_condition_name'):
            match = True
            tmp_cond = cond_name
            for k in keywords:
                if k in tmp_cond:
                    tmp_cond = tmp_cond.replace(k, '')
                else:
                    match = False
                    break
            if match:
                matched_cond_names.append(cond_name)
        return sorted(matched_cond_names)

    @classmethod
    def get_func(cls, key):
        self = cls()

        func, args = (self & key).fetch1(
            'trial_condition_func', 'trial_condition_arg')

        return partial(dict(getmembers(cls))[func], **args)

    @classmethod
    def _get_trials_exclude_stim(cls, **kwargs):
        # Note: inclusion (attr) is AND - exclusion (_attr) is OR
        log.debug('_get_trials_exclude_stim: {}'.format(kwargs))

        restr, _restr = {}, {}
        for k, v in kwargs.items():
            if k.startswith('_'):
                _restr[k[1:]] = v
            else:
                restr[k] = v

        stim_attrs = set((experiment.Photostim * experiment.PhotostimBrainRegion
                          * experiment.PhotostimEvent).heading.names) - set(experiment.Session.heading.names)
        behav_attrs = set(experiment.BehaviorTrial.heading.names)

        _stim_key = {k: v for k, v in _restr.items() if k in stim_attrs}
        _behav_key = {k: v for k, v in _restr.items() if k in behav_attrs}

        stim_key = {k: v for k, v in restr.items() if k in stim_attrs}
        behav_key = {k: v for k, v in restr.items() if k in behav_attrs}

        return (((experiment.BehaviorTrial & behav_key) - [{k: v} for k, v in _behav_key.items()]) -
                ((experiment.PhotostimEvent * experiment.PhotostimBrainRegion * experiment.Photostim & stim_key)
                 - [{k: v} for k, v in _stim_key.items()]).proj())

    @classmethod
    def _get_trials_include_stim(cls, **kwargs):
        # Note: inclusion (attr) is AND - exclusion (_attr) is OR
        log.debug('_get_trials_include_stim: {}'.format(kwargs))

        restr, _restr = {}, {}
        for k, v in kwargs.items():
            if k.startswith('_'):
                _restr[k[1:]] = v
            else:
                restr[k] = v

        stim_attrs = set((experiment.Photostim * experiment.PhotostimBrainRegion
                          * experiment.PhotostimEvent).heading.names) - set(experiment.Session.heading.names)
        behav_attrs = set(experiment.BehaviorTrial.heading.names)

        _stim_key = {k: v for k, v in _restr.items() if k in stim_attrs}
        _behav_key = {k: v for k, v in _restr.items() if k in behav_attrs}

        stim_key = {k: v for k, v in restr.items() if k in stim_attrs}
        behav_key = {k: v for k, v in restr.items() if k in behav_attrs}

        return (((experiment.BehaviorTrial & behav_key) - [{k: v} for k, v in _behav_key.items()]) &
                ((experiment.PhotostimEvent * experiment.PhotostimBrainRegion * experiment.Photostim & stim_key)
                 - [{k: v} for k, v in _stim_key.items()]).proj())


@schema
class UnitPsth(dj.Computed):
    definition = """
    -> TrialCondition
    -> ephys.Unit
    ---
    unit_psth=NULL: longblob
    """
    psth_params = {'xmin': -3, 'xmax': 3, 'binsize': 0.04}

    @property
    def key_source(self):
        """
        For those conditions that include stim, process those with PhotostimBrainRegion already computed only
        Only units not of type "all"
        """
        nostim = (ephys.Unit * (TrialCondition & 'trial_condition_func = "_get_trials_exclude_stim"')
                  & 'unit_quality != "all"')
        stim = ((ephys.Unit & (experiment.Session & experiment.PhotostimBrainRegion))
                * (TrialCondition & 'trial_condition_func = "_get_trials_include_stim"') & 'unit_quality != "all"')
        return nostim.proj() + stim.proj()

    def make(self, key):
        log.debug('UnitPsth.make(): key: {}'.format(key))

        # expand TrialCondition to trials,
        trials = TrialCondition.get_trials(key['trial_condition_name'])

        # fetch related spike times
        q = (ephys.Unit.TrialSpikes & key & trials.proj())
        spikes = q.fetch('spike_times')

        if len(spikes) == 0:
            log.warning('no spikes found for key {} - null psth'.format(key))
            self.insert1(key)
            return

        # compute psth & store
        unit_psth = self.compute_psth(spikes)

        self.insert1({**key, 'unit_psth': unit_psth})

    @staticmethod
    def compute_psth(session_unit_spikes):
        spikes = np.concatenate(session_unit_spikes)

        xmin, xmax, bins = UnitPsth.psth_params.values()
        psth, edges = np.histogram(spikes, bins=np.arange(xmin, xmax, bins))
        psth = psth / len(session_unit_spikes) / bins

        return np.array([psth, edges[1:]])

    @classmethod
    def get_plotting_data(cls, unit_key, condition_key):
        """
        Retrieve / build data needed for a Unit PSTH Plot based on the given
        unit condition and included / excluded condition (sub-)variables.
        Returns a dictionary of the form:
          {
             'trials': ephys.Unit.TrialSpikes.trials,
             'spikes': ephys.Unit.TrialSpikes.spikes,
             'psth': UnitPsth.unit_psth,
             'raster': Spike * Trial raster [np.array, np.array]
          }
        """
        # from sys import exit as sys_exit  # NOQA
        # from code import interact
        # from collections import ChainMap
        # interact('unitpsth make', local=dict(ChainMap(locals(), globals())))

        trials = TrialCondition.get_func(condition_key)()

        unit_psth = (UnitPsth & {**condition_key, **unit_key}).fetch1('unit_psth')
        if unit_psth is None:
            raise Exception('No spikes found for this unit and trial-condition')

        spikes, trials = (ephys.Unit.TrialSpikes & trials & unit_key).fetch(
            'spike_times', 'trial', order_by='trial asc')

        raster = [np.concatenate(spikes),
                  np.concatenate([[t] * len(s)
                                  for s, t in zip(spikes, trials)])]

        return dict(trials=trials, spikes=spikes, psth=unit_psth, raster=raster)


def compute_unit_psth(unit_key, trial_keys, per_trial=False):
    """
    Compute unit-level psth for the specified unit and trial-set - return (time,)
    If per_trial == True, compute trial-level psth - return ((trial x time), time_vec)
    :param unit_key: key of a single unit to compute the PSTH for
    :param trial_keys: list of all the trial keys to compute the PSTH over
    """
    q = (ephys.Unit.TrialSpikes & unit_key & trial_keys)
    if not q:
        return None

    xmin, xmax, bin_size = UnitPsth.psth_params.values()
    binning = np.arange(xmin, xmax, bin_size)

    spikes = q.fetch('spike_times')

    if per_trial:
        trial_psth = np.vstack(np.histogram(spike, bins=binning)[0] / bin_size for spike in spikes)
        return trial_psth, binning[1:]
    else:
        spikes = np.concatenate(spikes)
        psth, edges = np.histogram(spikes, bins=binning)
        psth = psth / len(q) / bin_size
        return psth, edges[1:]

