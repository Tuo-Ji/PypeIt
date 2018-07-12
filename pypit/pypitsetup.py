#  Class for organizing PYPIT setup
from __future__ import absolute_import, division, print_function

import inspect
import numpy as np

#from importlib import reload

from astropy.table import hstack, Table

from pypit import msgs
from pypit import ardebug as debugger
from pypit import arload
from pypit import arparse
from pypit.core import arsort
from pypit.core import arsetup

class PypitSetup(object):
    """Class to handle setup

    Parameters
    ----------
    settings_argflag : dict
      Somewhat of a kludge until settings is Refactored
    settings_spect : dict
      Somewhat of a kludge until settings is Refactored
    fitstbl : Table
      Contains FITS header info and (may) contain file type info
      May be generated by this class

    Attributes
    ----------
    setup_dict : dict
    steps : list
    ftypes : list
      frame types;  grabbed from arsort.ftype_list
    """
    def __init__(self, spectrograph, reduce_par, fitstbl=None):

        # Other parameters
        self.spectrograph = spectrograph
        self.reduce_par = reduce_par
        self.fitstbl = fitstbl

        # Outputs
        self.setup_dict = {}

        # Attributes
        self.ftypes = arsort.ftype_list
        self.steps = []

    @property
    def nfiles(self):
        if self.fitstbl is None:
            return 0
        else:
            return len(self.fitstbl)

    def build_fitstbl(self, file_list):
        """

        Parameters
        ----------
        file_list : list
          List of file names for generating fitstbl

        Returns
        -------
        fitstbl : Table

        """
        self.fitstbl = arload.load_headers(file_list, self.spectrograph, self.reduce_par)
        self.fitstbl.sort('time')
        # Step
        self.steps.append(inspect.stack()[0][3])
        return self.fitstbl

    def build_group_dict(self):
        """
        Builds a group dict and writes to disk
          This may be Deprecated (if the .sorted files are deemed too unintersting)

        Returns
        -------
        group_dict : dict
          Dict describing the various setups
        """
        #
        all_sci_idx = np.where(self.fitstbl['science'])[0]
        all_sci_ID = self.fitstbl['sci_ID'][self.fitstbl['science']]
        self.group_dict = arsetup.build_group_dict(self.fitstbl, self.setupIDs, all_sci_idx, all_sci_ID)

        # Write .sorted file
        if len(self.group_dict) > 0:
            if len(self.settings_argflag['run']['redname']) == 0: # Stop gap
                group_file = 'tmp.sorted'
            else:
                group_file = self.settings_argflag['run']['redname'].replace('.pypit', '.sorted')
            arsetup.write_sorted(group_file, self.fitstbl, self.group_dict, self.setup_dict)
            msgs.info("Wrote group dict to {:s}".format(group_file))
        else:
            msgs.warn("No group dict entries and therefore no .sorted file")
        # Step
        self.steps.append(inspect.stack()[0][3])
        # Return
        return self.group_dict


    def build_setup_dict(self):
        """
        Generate the setup_dict
          Mainly a Wrapper to new_instr_setup

        Returns
        -------
        setup_dict :

        """

        # Setup?
        if self.settings_argflag['run']['setup']:
            skip_cset = True
        else:
            skip_cset = False


        # Run with masters?
        if self.settings_argflag['reduce']['masters']['force']:
            # Check that setup was input
            if len(self.settings_argflag['reduce']['masters']['setup']) == 0:
                msgs.error("You need to specify the following parameter in your PYPIT file:"+msgs.newline()+"reduce masters setup")
            # Generate a dummy setup_dict
            self.setup_dict = arsetup.dummy_setup_dict(self.fitstbl,
                    self.settings_argflag['reduce']['masters']['setup'])
            # Step
            self.steps.append(inspect.stack()[0][3])
            # Return
            return self.setup_dict

        # Run through the setups to fill setup_dict
        self.setupIDs = []
        all_sci_ID = self.fitstbl['sci_ID'].data[self.fitstbl['science']]
        for sc in all_sci_ID:
            for kk in range(self.settings_spect['mosaic']['ndet']):
                det = kk+1
                try:
                    cname = self.settings_argflag['setup']['name']
                except KeyError:
                    cname = None
                # Amplifiers
                dnum = arparse.get_dnum(det)
                namp = self.settings_spect[dnum]["numamplifiers"]
                # Run
                setupID = arsetup.instr_setup(sc, det, self.fitstbl, self.setup_dict, namp,
                                                  skip_cset=skip_cset, config_name=cname)
                # Only save the first detector for run setup
                if kk == 0:
                    self.setupIDs.append(setupID)
        # Step
        self.steps.append(inspect.stack()[0][3])
        return self.setup_dict

    def match_ABBA(self):
        """
          Matches science frames to their partner A/B frame
          Mainly a wrapper to arsort.match_ABBA()

        Returns
        -------
        self.fitstbl -- Updated with 'AB_frame' column

        """
        self.fitstbl = arsort.match_ABBA(self.fitstbl)

        # Step
        self.steps.append(inspect.stack()[0][3])
        return self.fitstbl

    def match_to_science(self):
        """
          Matches calibration frames to the Science
          Mainly a wrapper to arsort.match_to_science()

        Returns
        -------
        self.fitstbl -- Updated with 'sci_ID' and 'failures' columns

        """
        self.fitstbl = arsort.match_to_science(self.fitstbl,
                                         self.settings_spect,
                                         self.settings_argflag)
        # Step
        self.steps.append(inspect.stack()[0][3])
        return self.fitstbl

    def type_data(self, flag_unknown=False):
        """
          Perform image typing on the full set of input files
          Mainly a wrapper to arsort.type_data()

        The table (filetypes) returned is horizontally stacked
          onto the fitstbl.

        Returns
        -------
        self.filetypes

        """
        # Allow for input file types from the PYPIT file
        if len(arparse.ftdict) > 0:  # This is ugly!
            ftdict = arparse.ftdict
        else:
            ftdict = None
        self.filetypes = arsort.type_data(self.fitstbl, self.settings_spect,
                                     self.settings_argflag,
                                     ftdict=ftdict, flag_unknown=flag_unknown)
        # hstack me -- Might over-write self.fitstbl here
        msgs.info("Adding file type information to the fitstbl")
        self.fitstbl = hstack([self.fitstbl, self.filetypes])

        # Step
        self.steps.append(inspect.stack()[0][3])
        # Return
        return self.filetypes

    def load_fitstbl(self, fits_file):
        """
          Load the fitstbl from disk (a binary FITS table)

        Parameters
        ----------
        fits_file : str

        Returns
        -------
        self.fitstbl

        """
        self.fitstbl = Table.read(fits_file)
        msgs.info("Loaded fitstbl from {:s}".format(fits_file))
        return self.fitstbl

    def write_fitstbl(self, outfile=None, overwrite=True):
        """
        Write fitstbl to FITS

        Parameters
        ----------
        outfile : str
        overwrite : bool (optional)
        """
        if outfile is None:
            outfile = self.settings_argflag['run']['redname'].replace('.pypit', '.fits')
        self.fitstbl.write(outfile, overwrite=overwrite)

    def run(self, file_list=None):
        """ Main driver for file typing and sorting

          Code flow:
            1. Build the fitstbl from an input file_list (optional)
            2. Type the files (bias, arc, etc.)
            3. Match calibration files to the science files
            4. Generate the setup_dict
               -- Write group info to disk
               -- Write calib info to disk (if main run)

        Parameters
        ----------
        file_list : list (optional)
          Used to generate fitstbl

        Returns
        -------
        fitstbl : Table
        setup_dict : Table
        """
        # Build fitstbl
        if self.fitstbl is None:
            _ = self.build_fitstbl(file_list)

        # File typing
        if self.settings_argflag['run']['calcheck'] or self.settings_argflag['run']['setup']:
            bad_to_unknown = True
        else:
            bad_to_unknown = False
        _ = self.type_data(flag_unknown=bad_to_unknown)

        # Write?
        if self.settings_argflag['output']['sorted'] is not None:
            _ = arsort.write_lst(self.fitstbl, self.settings_spect, self.settings_argflag)

        # Match calibs to science
        _ = self.match_to_science()

        # Setup dict
        _ = self.build_setup_dict()

        # .sorted Table (on pypit_setup only)
        if self.settings_argflag['run']['setup']:  # Collate all matching files
            _ = self.build_group_dict()

        # Write calib file (not in setup mode) or setup file (in setup mode)
        if not self.settings_argflag['run']['setup']:
            if len(self.settings_argflag['run']['redname']) == 0: # Stop gap
                calib_file = 'tmp.calib'
            else:
                calib_file = self.settings_argflag['run']['redname'].replace('.pypit', '.calib')
            arsetup.write_calib(calib_file, self.setup_dict)
        else:
            if len(self.settings_argflag['run']['redname']) == 0: # Stop gap
                setup_file = 'tmp.setups'
            else:
                setup_file = self.settings_argflag['run']['redname'].replace('.pypit', '.setups')
            arsetup.write_setup(self.setup_dict, setup_file=setup_file)

        # Finish (depends on PYPIT run mode)
        if self.settings_argflag['run']['calcheck']:
            msgs.info("Inspect the .calib file: {:s}".format(calib_file))
            msgs.info("*********************************************************")
            msgs.info("Calibration check complete and successful!")
            msgs.info("Set 'run calcheck False' to continue with data reduction")
            msgs.info("*********************************************************")
            # Instrument specific (might push into a separate file)
            if self.settings_argflag['run']['spectrograph'] in ['keck_lris_blue']:
                if self.settings.argflag['reduce']['flatfield']['useframe'] in ['pixelflat']:
                    msgs.warn("We recommend a slitless flat for your instrument.")
            return 'calcheck', None, None
        elif self.settings_argflag['run']['setup']:
            for idx in np.where(self.fitstbl['failures'])[0]:
                msgs.warn("No Arc found: Skipping object {:s} with file {:s}".format(
                    self.fitstbl['target'][idx],self.fitstbl['filename'][idx]))
            msgs.info("Setup is complete.")
            msgs.info("Inspect the .setups file")
            return 'setup', None, None
        else:
            return 'run', self.fitstbl, self.setup_dict

    def __repr__(self):
        # Generate sets string
        txt = '<{:s}: nfiles={:d}>'.format(self.__class__.__name__,
                                           self.nfiles)
        return txt



