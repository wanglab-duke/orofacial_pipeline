import sys

from . import behavior_ingest, tracking_ingest
from .session_ingest import load_all_sessions


populate_settings = {'reserve_jobs': True, 'suppress_errors': True, 'display_progress': True}


def ingest_all(subject_id):
    load_all_sessions(subject_id)

    behavior_ingest.BehaviorIngestion.populate(**populate_settings)
    tracking_ingest.TrackingIngestion.populate(**populate_settings)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Please specify "subject_id" to load')
        sys.exit(0)

    ingest_all(sys.argv[1])
