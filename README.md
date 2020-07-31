# orofacial_pipeline
Wang lab Datajoint pipeline for orofacial experiments

## configure `dj_local_conf.json`

Template for `dj_local_conf.json`

```json
{
    "database.host": "db_host",
    "database.user": "username",
    "database.password": "password",
    "database.port": 3306,
    "connection.init_function": null,
    "database.reconnect": true,
    "enable_python_native_blobs": true,
    "loglevel": "INFO",
    "safemode": true,
    "display.limit": 7,
    "display.width": 14,
    "display.show_tuple_count": true,
    "stores": {},
    "custom": {
        "database.prefix": "cosmo_",
        "data_root_dir": "D:/data",
        "session_loader_class": "VincentLoader",
        "username": "username",
        "rig": "rig1"
    }
}
```

The "custom" section of the config file contains specific information for data ingestion. 
By default, the `database.prefix` is ***cosmo_***, which specify the prefix for the main cosmo pipeline.

To setup a separate pipeline for development/testing (e.g. build ingestion), 
users can change `database.prefix` to `username_` with the username used to access the database 
(users have full admin permissions for schema with their username as prefix, think of this as your personal schema branch)