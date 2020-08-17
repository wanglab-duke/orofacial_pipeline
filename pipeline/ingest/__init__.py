import datajoint as dj

from pipeline.ingest import session_loaders


# ============== SETUP the LOADER ==================

def get_loader():
    try:
        data_dir = dj.config['custom']['data_root_dir']
    except KeyError:
        raise KeyError('Unspecified data root directory! Please specify "data_root_dir" under dj.config["custom"]')

    try:
        session_loader_class = dj.config['custom']['session_loader_class']
    except KeyError:
        raise KeyError('Unspecified session loader method! Please specify "session_loader_method" under dj.config["custom"]')

    if session_loader_class in dir(session_loaders):
        # instantiate a loader class with "data_dir" and "config" (optional)
        loader_class = getattr(session_loaders, session_loader_class)
    else:
        raise RuntimeError(f'Unknown session loading function: {session_loader_class}')

    # instantiate a loader class with "data_dir" and "config" (optional)
    return loader_class(data_dir, dj.config)

