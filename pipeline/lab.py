import datajoint as dj
import numpy as np
from . import get_schema_name

schema = dj.schema(get_schema_name('lab'))


@schema
class Lab(dj.Manual):
    definition = """ # Lab
    lab : varchar(255)  #  lab conducting the study
    ---
    institution : varchar(255)  # Institution to which the lab belongs
    """

@schema
class Person(dj.Manual):
    definition = """
    username : varchar(24) 
    ----
    fullname : varchar(255)
    -> Lab
    """

@schema
class Rig(dj.Manual):
    definition = """
    rig             : varchar(24)
    ---
    -> Lab
    room            : varchar(20) # example 2w.342
    rig_description : varchar(1024) 
    """


# ---- Animal information ----

@schema
class AnimalStrain(dj.Lookup):
    definition = """
    animal_strain       : varchar(30)
    """
    contents = zip(['C57BL6', 'Ai14', 'Ai32', 'Ai35', 'Ai65D',
                    'Emx1_Cre', 'GAD2_Cre', 'vGLut2_Cre', 'Pv_Cre',
                    'Pv_CreERt2', 'Pv_CreN', 'TrpV1_Cre', 'Netrin_G1_Cre',
                    'FosTVA', 'Rphi_AP', 'Rphi_tomato', 'Rphi_GFP', 'ChodlPLAP'])


@schema
class AnimalSource(dj.Lookup):
    definition = """
    animal_source       : varchar(30)
    """
    contents = zip(['Jackson Labs', 'Allen Institute', 'Charles River', 'MMRRC', 'Taconic', 'Lab made', 'Other'])


@schema
class ModifiedGene(dj.Manual):
    definition = """
    gene_modification   : varchar(60)
    ---
    gene_modification_description = ''         : varchar(256)
    """


@schema
class Subject(dj.Manual):
    definition = """
    subject_id          : varchar(10)
    ---
    -> [nullable] Person        # person responsible for the animal
    cage_number         : int   # institution 7 digit animal ID
    date_of_birth       : date  # format: yyyy-mm-dd
    sex                 : enum('M','F','Unknown')
    -> [nullable] AnimalSource  # where was the animal ordered from
    """

    class Strain(dj.Part):
        definition = """
        # Subject strains
        -> master
        -> AnimalStrain
        """

    class GeneModification(dj.Part):
        definition = """
        # Subject gene modifications
        -> Subject
        -> ModifiedGene
        ---
        zygosity = 'Unknown' : enum('Het', 'Hom', 'Unknown')
        type = 'Unknown'     : enum('Knock-in', 'Transgene', 'Unknown')
        """


@schema
class CompleteGenotype(dj.Computed):
    # should be computed
    definition = """
    -> Subject
    ---
    complete_genotype : varchar(1000)
    """

    def make(self, key):
        pass


@schema
class WaterRestriction(dj.Manual):
    definition = """
    -> Subject
    ---
    water_restriction_number    : varchar(16)   # WR number
    cage_number                 : int
    wr_start_date               : date
    wr_start_weight             : Decimal(6,3)
    """


# ---- Virus information ----

@schema
class VirusSource(dj.Lookup):
    definition = """
    virus_source   : varchar(60)
    """
    contents = contents = zip(['Janelia', 'UPenn', 'Addgene', 'UNC', 'MIT', 'Duke', 'Lab made', 'Other'])


@schema
class Serotype(dj.Manual):
    definition = """
    serotype   : varchar(60)
    """


@schema
class Virus(dj.Manual):
    definition = """
    virus_id : int unsigned
    ---
    -> VirusSource 
    -> Serotype
    -> Person
    virus_name      : varchar(256)
    titer           : Decimal(20,1) # 
    order_date      : date
    remarks         : varchar(256)
    """

    class Notes(dj.Part):
        definition = """
        # Notes for virus
        -> Virus
        note_id     : int
        ---
        note        : varchar(256)
        """


"""
For nomenclature reference, here are some vectors/compounds used in the lab:
       'Dextran', 'CTb', 'AAV', 'AAV2', 'AAV2_1',
       'AAV2_5', 'AAV2_8', 'AAV8', 'AAV2_9', 'AAV9', 'AAV',
       'retroAAV', 'LV', 'FuGB2_LV', 'RG_LV', 'CANE_LV',
       'EnVA_SAD_dG_RV', 'RG_CVS_N2cdG_RV', 'CANE_RV', 'KainicAcid'
Nomenclature reference for constructs:
       'Alexa568', 'TMR', 'GFP', 'EGFP', 'mNeonG',
       'tdTomato', 'mCherry', 'RFP', 'Cre', 'Syn_Cre', 'CreC',
       'EF1a_mCherry_IRES_WGA_Cre', 'EF1a_Flex_ChR2',
       'Flex_TVAmCherry', 'Flex_TVA_RG_GFP'
"""

# ---- Brain region/location information ----


@schema
class SkullReference(dj.Lookup):
    definition = """
    skull_reference   : varchar(60)
    """
    contents = zip(['Bregma', 'Lambda'])

    
@schema
class BrainArea(dj.Lookup):
    definition = """
    brain_area: varchar(32)
    ---
    description = null : varchar (4000) # name of the brain area (lab terms, not necessarily in AIBS)
    """
    contents = [('vIRt', 'vibrissa-related intermediate reticular formation'),
                ('preBotC', 'pre-Boetzinger complex'),
                ('PrV', 'principal trigeminal nucleus'),
                ('SpVi', 'spinal trigeminal nucleus pars interpolaris'),
                ('SC', 'superior colliculus'),]
    
    
@schema
class Hemisphere(dj.Lookup):
    definition = """
    hemisphere: varchar(32)
    """
    contents = zip(['left', 'right', 'both'])


# ---- Surgery information ----


@schema
class Surgery(dj.Manual):
    definition = """
    -> Subject
    surgery_id          : int      # surgery number
    ---
    -> Person
    start_time          : datetime # start time
    end_time            : datetime # end time
    surgery_description : varchar(256)
    """

    class VirusInjection(dj.Part):
        definition = """
        # Virus injections
        -> master
        injection_id : int
        ---
        -> Virus
        -> SkullReference
        ap_location     : Decimal(8,3) # um from ref anterior is positive
        ml_location     : Decimal(8,3) # um from ref right is positive 
        dv_location     : Decimal(8,3) # um from dura dorsal is positive 
        volume          : Decimal(10,3) # in nl
        dilution        : Decimal (10, 2) # 1 to how much
        description     : varchar(256)
        """

    class Procedure(dj.Part):
        definition = """
        # Other things you did to the animal
        -> master
        procedure_id : int
        ---
        -> SkullReference
        ap_location=null     : Decimal(8,3) # um from ref anterior is positive
        ml_location=null     : Decimal(8,3) # um from ref right is positive
        dv_location=null     : Decimal(8,3) # um from dura dorsal is positive 
        surgery_procedure_description     : varchar(1000)
        """


@schema
class SurgeryLocation(dj.Manual):
    definition = """
    -> Surgery.Procedure
    ---
    -> Hemisphere
    -> BrainArea 
    """

# ---- Probe information ----


@schema
class ProbeType(dj.Lookup):
    definition = """
    probe_type: varchar(32)  # e.g. neuropixels_1.0 
    """

    class Electrode(dj.Part):
        definition = """
        -> master
        electrode: int       # electrode index, starts at 1
        ---
        shank: int           # shank index, starts at 1, advance left to right
        shank_col: int       # column index, starts at 1, advance left to right
        shank_row: int       # row index, starts at 1, advance tip to tail
        x_coord=NULL: float  # (um) x coordinate of the electrode within the probe, (0, 0) is the bottom left corner of the probe
        y_coord=NULL: float  # (um) y coordinate of the electrode within the probe, (0, 0) is the bottom left corner of the probe
        z_coord=0: float     # (um) z coordinate of the electrode within the probe, (0, 0) is the bottom left corner of the probe
        """

    @property
    def contents(self):
        return zip(['silicon_probe', 'tetrode_array', 'single electrode',
                    'EMG', 'EEG',
                    'neuropixels 1.0 - 3A', 'neuropixels 1.0 - 3B',
                    'neuropixels 2.0 - SS', 'neuropixels 2.0 - MS'])

    @staticmethod
    def create_neuropixels_probe(probe_type='neuropixels 1.0 - 3A'):
        """
        Create `ProbeType` and `Electrode` for neuropixels probe 1.0 (3A and 3B), 2.0 (SS and MS)
        For electrode location, the (0, 0) is the bottom left corner of the probe (ignore the tip portion)
        Electrode numbering is 1-indexing
        """

        def build_electrodes(site_count, col_spacing, row_spacing, white_spacing, col_count=2,
                             shank_count=1, shank_spacing=250):
            """
            :param site_count: site count per shank
            :param col_spacing: (um) horrizontal spacing between sites
            :param row_spacing: (um) vertical spacing between columns
            :param white_spacing: (um) offset spacing
            :param col_count: number of column per shank
            :param shank_count: number of shank
            :param shank_spacing: spacing between shanks
            :return:
            """
            row_count = int(site_count / col_count)
            x_coords = np.tile([0, 0 + col_spacing], row_count)
            x_white_spaces = np.tile([white_spacing, white_spacing, 0, 0], int(row_count / 2))

            x_coords = x_coords + x_white_spaces
            y_coords = np.repeat(np.arange(row_count) * row_spacing, 2)

            shank_cols = np.tile([0, 1], row_count)
            shank_rows = np.repeat(range(row_count), 2)

            npx_electrodes = []
            for shank_no in range(shank_count):
                npx_electrodes.extend([{'electrode': (site_count * shank_no) + e_id + 1,  # electrode number is 1-based index
                                        'shank': shank_no + 1,  # shank number is 1-based index
                                        'shank_col': c_id + 1,  # column number is 1-based index
                                        'shank_row': r_id + 1,  # row number is 1-based index
                                        'x_coord': x + (shank_no * shank_spacing),
                                        'y_coord': y,
                                        'z_coord': 0} for e_id, (c_id, r_id, x, y) in enumerate(
                    zip(shank_cols, shank_rows, x_coords, y_coords))])

            return npx_electrodes

        # ---- 1.0 3A ----
        if probe_type == 'neuropixels 1.0 - 3A':
            electrodes = build_electrodes(site_count=960, col_spacing=32, row_spacing=20,
                                          white_spacing=16, col_count=2)

            probe_type = {'probe_type': 'neuropixels 1.0 - 3A'}
            with ProbeType.connection.transaction:
                ProbeType.insert1(probe_type, skip_duplicates=True)
                ProbeType.Electrode.insert([{**probe_type, **e} for e in electrodes], skip_duplicates=True)

        # ---- 1.0 3B ----
        if probe_type == 'neuropixels 1.0 - 3B':
            electrodes = build_electrodes(site_count=960, col_spacing=32, row_spacing=20,
                                          white_spacing=16, col_count=2)

            probe_type = {'probe_type': 'neuropixels 1.0 - 3B'}
            with ProbeType.connection.transaction:
                ProbeType.insert1(probe_type, skip_duplicates=True)
                ProbeType.Electrode.insert([{**probe_type, **e} for e in electrodes], skip_duplicates=True)

        # ---- 2.0 Single shank ----
        if probe_type == 'neuropixels 2.0 - SS':
            electrodes = build_electrodes(site_count=1280, col_spacing=32, row_spacing=15,
                                          white_spacing=0, col_count=2,
                                          shank_count=1, shank_spacing=250)

            probe_type = {'probe_type': 'neuropixels 2.0 - SS'}
            with ProbeType.connection.transaction:
                ProbeType.insert1(probe_type, skip_duplicates=True)
                ProbeType.Electrode.insert([{**probe_type, **e} for e in electrodes], skip_duplicates=True)

        # ---- 2.0 Multi shank ----
        if probe_type == 'neuropixels 2.0 - MS':
            electrodes = build_electrodes(site_count=1280, col_spacing=32, row_spacing=15,
                                          white_spacing=0, col_count=2,
                                          shank_count=4, shank_spacing=250)

            probe_type = {'probe_type': 'neuropixels 2.0 - MS'}
            with ProbeType.connection.transaction:
                ProbeType.insert1(probe_type, skip_duplicates=True)
                ProbeType.Electrode.insert([{**probe_type, **e} for e in electrodes], skip_duplicates=True)


@schema
class Probe(dj.Lookup):
    definition = """  # represents a physical probe
    probe: varchar(32)  # unique identifier for this model of probe (e.g. part number)
    ---
    -> ProbeType
    probe_comment='' :  varchar(1000)
    """


@schema
class Adapter(dj.Lookup):
    definition = """
    adapter: varchar(100) # unique identifier for this model of probe adapter (e.g. part number)
    ---
    desc: varchar(1000)
    desc_image=null: longblob #Adapter specs, including connector mapping
    """


@schema
class Headstage(dj.Lookup):
    definition = """
    headstage: varchar(100) # unique identifier for this model of headstage (e.g. part number)
    ---
    desc: varchar(1000)
    desc_image=null: longblob #Headstage specs, including connector mapping
    """


@schema
class ElectrodeConfig(dj.Lookup):
    definition = """
    -> ProbeType
    electrode_config_name: varchar(64)  # user friendly name
    ---
    electrode_config_hash: varchar(36)  # hash of the group and group_member (ensure uniqueness)
    unique index (electrode_config_hash)
    """

    class ElectrodeGroup(dj.Part):
        definition = """
        # grouping of electrodes to be clustered together (e.g. a neuropixel electrode config - 384/960)
        -> master
        electrode_group: int  # electrode group
        """

    class Electrode(dj.Part):
        definition = """
        -> master.ElectrodeGroup
        -> ProbeType.Electrode
        ---
        is_used: bool  # is this channel used for spatial average (ref channels are by default not used)
        """


# ---- Others ----

@schema
class PhotostimDevice(dj.Lookup):
    definition = """
    photostim_device  : varchar(20)
    ---
    excitation_wavelength :  decimal(5,1)  # (nm) 
    photostim_device_description : varchar(255)
    """
    contents =[
       ('OptoEngine473', 473, 'DPSS Laser (Opto Engine MBL-FF-473)'),
       ('OptoEngine470', 470, 'DPSS Laser (Opto Engine MDL-III-470)'),
       ('OptoEngine561_150', 561, 'DPSS Laser (Opto Engine MGL-FN-561-150mW)'),
       ('OptoEngine561_100', 561, 'DPSS Laser (Opto Engine MGL-FN-561-100mW)'),
       ('Cobolt473', 473, 'Diode Laser (Cobolt 06-MLD 473)'),
       ('Cobolt633', 633, 'Diode Laser (Cobolt 06-MLD 633)'),
       ('Doric465', 465, 'LED (Doric CLED 465)'),
       ('Doric595', 595, 'LED (Doric CLED 595)')]

@schema
class FiberPhotometryDevice(dj.Lookup):
    definition = """
    fiberphotometry_device  : varchar(20)
    ---
    excitation_wavelength_1 :  decimal(5,1)  # (nm) 
    excitation_wavelength_2 :  decimal(5,1)  # (nm) 
    isosbestic_wavelength : decimal(5,1)  # (nm) 
    photostim_device_description : varchar(255)
    """
    contents = [('FP3001', 560, 470, 415, 'Neurophotometrics FP3001'),
                ('R801', 560, 470, 410, 'RWD R801')]

@schema
class DataAcquisitionDevice(dj.Lookup):
    definition = """
    data_acquisition_device  : varchar(20)
    ---
    device_type  : varchar(30)
    adc = null : decimal(5,3)  # μV per bit resolution analog to digital conversion. ADC may occur on headstage for digital ephys systems 
    device_description : varchar(255)
    """
    contents =[
       ('CereplexDirect', 'Data acquisition system', 0.25, 'Blackrock Microsystems Cereplex Direct'),
       ('Neuropixels', 'Data acquisition system', 9.765, 'Neuropixels Control System with PXIe interface'), #See https://www.neuropixels.org/control-system
       ('Intan', 'Data acquisition system', 0.195, 'Intan RHD2000 series Recording Controller'), #See http://www.intantech.com/files/Intan_RHD2000_series_datasheet.pdf p.6
       ('OpenEphys', 'Data acquisition system', 0.195, 'Open Ephys acquisition board'),
       ('LJT4_HV', 'DAQ device', 4882.8, 'LabJack T4 high voltage analog inputs'),
       ('LJT4_LV', 'DAQ device', 610.35, 'LabJack T4 low voltage analog inputs'),
       ('NI_USB_6212', 'DAQ device', 5.2, '16-bit NIDAQ low voltage input setting'),
       ('Mega2560', 'Arduino microcontroller', None, 'Arduino Mega 2560 Rev3'),
       ('Uno', 'Arduino microcontroller', None, 'Arduino Uno')]

@schema
class AnalogAmps(dj.Lookup):
    definition = """
    analog_amplifier  : varchar(20)
    ---
    device_type  : varchar(30)
    device_description : varchar(255)
    """
    contents =[
       ('AMS1800', 'Differential amplifier', 'A-M Systems Model 1800'),
       ('DAM80', 'Differential amplifier', 'WPI DAM80'),
       ('LJTIA', 'Differential amplifier', 'LabJack LJTick-InAmp')] #https://labjack.com/accessories/ljtick-inamp

@schema
class Whisker(dj.Lookup):
    definition = """
    whisker: varchar(32)
    """
    contents = zip(['Alpha', 'A1', 'A2', 'A3', 'A4',
                    'Beta', 'B1', 'B2', 'B3', 'B4',
                    'Gamma', 'C1', 'C2', 'C3', 'C4', 'C5', 'C6',
                    'Delta', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6'])


@schema
class ExperimentObject(dj.Lookup):
    definition = """
    object: varchar(24) 
    """
    contents = zip(['wall_90', 'wall_45', 'pole', 'texture panel', 'von Frey', 'heat stim', 'cold stim', 'cuetip'])
