# Licensed under a 3-clause BSD style license - see LICENSE.rst
# -*- coding: utf-8 -*-
"""
desispec.io.quicksurvey
=======================

Code for loading quicksurvey outputs into a database.
"""
from __future__ import absolute_import, division, print_function
import os
import re
from glob import glob
from datetime import datetime, timedelta, tzinfo
import numpy as np
from astropy.io import fits
from sqlalchemy import (create_engine, text, Table, ForeignKey, Column,
                        Integer, String, Float, DateTime)
from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import sessionmaker, relationship, reconstructor
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
# from matplotlib.patches import Circle, Polygon, Wedge
# from matplotlib.collections import PatchCollection
from ..log import get_logger, DEBUG


class UTC(tzinfo):
    """Representation of UTC for time zones.
    """
    ZERO = timedelta(0)
    # HOUR = timedelta(hours=1)

    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO


utc = UTC()


Base = declarative_base()


class Truth(Base):
    """Representation of the truth table.
    """
    __tablename__ = 'truth'

    targetid = Column(Integer, primary_key=True)
    ra = Column(Float, nullable=False)
    dec = Column(Float, nullable=False)
    truez = Column(Float, nullable=False)
    truetype = Column(String, nullable=False)
    sourcetype = Column(String, nullable=False)
    brickname = Column(String, nullable=False)
    oiiflux = Column(Float, nullable=False)

    # frames = relationship('Frame', secondary=frame2brick,
    #                       back_populates='bricks')

    def __repr__(self):
        return ("<Truth(targetid={0.targetid:d}, " +
                "ra={0.ra:f}, dec={0.dec:f}, truez={0.truez:f}, " +
                "truetype='{0.truetype}', sourcetype='{0.sourcetype}', " +
                "brickname='{0.brickname}', " +
                "oiiflux={0.oiiflux:f})>").format(self)


class Target(Base):
    """Representation of the target table.
    """
    __tablename__ = 'target'

    targetid = Column(Integer, primary_key=True)
    ra = Column(Float, nullable=False)
    dec = Column(Float, nullable=False)
    desi_target = Column(Integer, nullable=False)
    bgs_target = Column(Integer, nullable=False)
    mws_target = Column(Integer, nullable=False)
    subpriority = Column(Float, nullable=False)
    obsconditions = Column(Integer, nullable=False)
    brickname = Column(String, nullable=False)
    decam_flux_u = Column(Float, nullable=False)
    decam_flux_g = Column(Float, nullable=False)
    decam_flux_r = Column(Float, nullable=False)
    decam_flux_i = Column(Float, nullable=False)
    decam_flux_z = Column(Float, nullable=False)
    decam_flux_Y = Column(Float, nullable=False)
    shapedev_r = Column(Float, nullable=False)
    shapeexp_r = Column(Float, nullable=False)
    depth_r = Column(Float, nullable=False)
    galdepth_r = Column(Float, nullable=False)

    def __repr__(self):
        return ("<Target(targetid={0.targetid:d}, " +
                "ra={0.ra:f}, dec={0.dec:f}, " +
                "desi_target={0.desi_target:d}, bgs_target={0.bgs_target}, " +
                "mws_target={0.mws_target:d}, " +
                "subpriority={0.subpriority:f}, " +
                "obsconditions={0.obsconditions:d}, " +
                "brickname='{0.brickname}', " +
                "decam_flux_u={0.decam_flux_u:f}, " +
                "decam_flux_g={0.decam_flux_g:f}, " +
                "decam_flux_r={0.decam_flux_r:f}, " +
                "decam_flux_i={0.decam_flux_i:f}, " +
                "decam_flux_z={0.decam_flux_z:f}, " +
                "decam_flux_Y={0.decam_flux_Y:f}, " +
                "shapedev_r={0.shapedev_r:f}, shapeexp_r={0.shapeexp_r:f}, "
                "depth_r={0.depth_r:f}, " +
                "galdepth_r={0.galdepth_r:f})>").format(self)


def load_file(filepath, session, tcls, expand=None):
    """Load a FITS file into the database, assuming that FITS column names map
    to database column names with no surprises.

    Parameters
    ----------
    filepath : :class:`str`
        Full path to the FITS file.
    session : :class:`sqlalchemy.orm.session.Session`
        Database connection.
    tcls
        The table to load, represented by its class.
    expand : :class:`dict`, optional
        If set, map FITS column names to one or more alternative column names.
    """
    with fits.open(filepath) as hdulist:
        data = hdulist[1].data
    data_list = [data[col].tolist() for col in data.names]
    data_names = [col.lower() for col in data.names]
    if expand is not None:
        for col in expand:
            if isinstance(expand[col], str):
                #
                # Just rename a column.
                #
                data_names[data.names.index(col)] = expand[col]
            else:
                #
                # Assume this is an expansion of an array-valued column
                # into individual columns.
                #
                i = data.names.index(col)
                del data_names[i]
                del data_list[i]
                for j, n in enumerate(expand[col]):
                    data_names.insert(i + j, n)
                    data_list.insert(i + j, data[col][:, j].tolist())
    session.add_all([tcls(**b) for b in [dict(zip(data_names, row))
                                         for row in zip(*data_list)]])
    session.commit()
    return


def main():
    """Entry point for command-line script.

    Returns
    -------
    :class:`int`
        An integer suitable for passing to :func:`sys.exit`.
    """
    #
    # command-line arguments
    #
    from argparse import ArgumentParser
    from pkg_resources import resource_filename
    prsr = ArgumentParser(description=("Load quicksurvey simulation into a " +
                                       "database."))
    # prsr.add_argument('-a', '--area', action='store_true', dest='fixarea',
    #                   help=('If area is not specified in the brick file, ' +
    #                         'recompute it.'))
    # prsr.add_argument('-b', '--bricks', action='store', dest='brickfile',
    #                   default='bricks-0.50-2.fits', metavar='FILE',
    #                   help='Read brick data from FILE.')
    prsr.add_argument('-c', '--clobber', action='store_true', dest='clobber',
                      help='Delete any existing file(s) before loading.')
    # prsr.add_argument('-d', '--data', action='store', dest='datapath',
    #                   default=os.path.join(os.environ['DESI_SPECTRO_SIM'],
    #                                        os.environ['SPECPROD']),
    #                   metavar='DIR', help='Load the data in DIR.')
    prsr.add_argument('-f', '--filename', action='store', dest='dbfile',
                      default='quicksurvey.db', metavar='FILE',
                      help="Store data in FILE.")
    # prsr.add_argument('-p', '--pass', action='store', dest='obs_pass',
    #                   default=0, type=int, metavar='PASS',
    #                   help="Only simulate frames associated with PASS.")
    # prsr.add_argument('-s', '--simulate', action='store_true', dest='simulate',
    #                   help="Run a simulation using DESI tiles.")
    # prsr.add_argument('-t', '--tiles', action='store', dest='tilefile',
    #                   default='desi-tiles.fits', metavar='FILE',
    #                   help='Read tile data from FILE.')
    prsr.add_argument('-v', '--verbose', action='store_true', dest='verbose',
                      help='Print extra information.')
    prsr.add_argument('datapath', metavar='DIR', help='Load the data in DIR.')
    options = prsr.parse_args()
    #
    # Logging
    #
    if options.verbose:
        log = get_logger(DEBUG)
    else:
        log = get_logger()
    #
    # Create the file.
    #
    db_file = os.path.join(options.datapath, options.dbfile)
    if options.clobber and os.path.exists(db_file):
        log.info("Removing file: {0}.".format(db_file))
        os.remove(db_file)
    engine = create_engine('sqlite:///'+db_file, echo=options.verbose)
    log.info("Begin creating schema.")
    Base.metadata.create_all(engine)
    log.info("Finished creating schema.")
    Session = sessionmaker()
    Session.configure(bind=engine)
    session = Session()
    try:
        q = session.query(Truth).one()
    except MultipleResultsFound:
        log.info("Truth table already loaded.")
    except NoResultFound:
        truth_file = os.path.join(options.datapath, 'input', 'dark',
                                  'truth.fits')
        log.info("Loading truth from {0}.".format(truth_file))
        load_file(truth_file, session, Truth)
        log.info("Finished loading truth.")
    try:
        q = session.query(Target).one()
    except MultipleResultsFound:
        log.info("Target table already loaded.")
    except NoResultFound:
        expand_decam = {'DECAM_FLUX': ('decam_flux_u', 'decam_flux_g',
                                       'decam_flux_r', 'decam_flux_i',
                                       'decam_flux_z', 'decam_flux_Y')}
        target_file = os.path.join(options.datapath, 'input', 'dark',
                                   'target.fits')
        log.info("Loading target from {0}.".format(target_file))
        load_file(target_file, session, Target, expand=expand_decam)
        log.info("Finished loading target.")
    return 0
