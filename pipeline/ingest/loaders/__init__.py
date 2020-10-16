import pandas as pd


# ================ INCLUDE ALL AVAILABLE LOADERS ================

from .vincent import VincentLoader
from .wenxi import WenxiLoader


# ================ OTHER HELPER METHODS ================

def load_table_from_struct(table_structure, colnames) -> pd.DataFrame():
    # get prepared data structure
    data = table_structure.data

    # create dict out of original table
    table_dict = {}
    for col_idx, colname in enumerate(colnames):
        table_dict[colname] = data[col_idx]

    return pd.DataFrame(table_dict)
