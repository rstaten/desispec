"""
desispec.io.frame
=================

I/O routines for Frame objects
"""
import os.path

import numpy as np
import scipy,scipy.sparse
from astropy.io import fits

from desiutil.depend import add_dependencies

from desispec.frame import Frame
from desispec.io import findfile
from desispec.io.util import fitsheader, native_endian, makepath
from desispec.log import get_logger

log = get_logger()

def write_frame(outfile, frame, header=None, fibermap=None):
    """Write a frame fits file and returns path to file written.

    Args:
        outfile: full path to output file, or tuple (night, expid, channel)
        frame:  desispec.frame.Frame object with wave, flux, ivar...

    Optional:
        header: astropy.io.fits.Header or dict to override frame.header
        fibermap: table to store as FIBERMAP HDU

    Returns:
        full filepath of output file that was written

    Note:
        to create a Frame object to pass into write_frame,
        frame = Frame(wave, flux, ivar, resolution_data)
    """
    outfile = makepath(outfile, 'frame')

    if header is not None:
        hdr = fitsheader(header)
    else:
        hdr = fitsheader(frame.meta)
        
    add_dependencies(hdr)

    hdus = fits.HDUList()
    x = fits.PrimaryHDU(frame.flux.astype('f4'), header=hdr)
    x.header['EXTNAME'] = 'FLUX'
    hdus.append(x)

    hdus.append( fits.ImageHDU(frame.ivar.astype('f4'), name='IVAR') )
    hdus.append( fits.CompImageHDU(frame.mask, name='MASK') )
    hdus.append( fits.ImageHDU(frame.wave.astype('f4'), name='WAVELENGTH') )
    hdus.append( fits.ImageHDU(frame.resolution_data.astype('f4'), name='RESOLUTION' ) )
    
    if fibermap is not None:
        hdus.append( fits.BinTableHDU(np.asarray(fibermap), name='FIBERMAP' ) )
    elif frame.fibermap is not None:
        hdus.append( fits.BinTableHDU(np.asarray(frame.fibermap), name='FIBERMAP' ) )
    elif frame.spectrograph is not None:
        x.header['FIBERMIN'] = 500*frame.spectrograph  # Hard-coded (as in desispec.frame)
    else:
        log.error("You are likely writing a frame without sufficient fiber info")

    if frame.chi2pix is not None:
        hdus.append( fits.ImageHDU(frame.chi2pix.astype('f4'), name='CHI2PIX' ) )

    hdus.writeto(outfile+'.tmp', clobber=True, checksum=True)
    os.rename(outfile+'.tmp', outfile)

    return outfile

def read_frame(filename, nspec=None):
    """Reads a frame fits file and returns its data.

    Args:
        filename: path to a file, or (night, expid, camera) tuple where
            night = string YEARMMDD
            expid = integer exposure ID
            camera = b0, r1, .. z9

    Returns:
        desispec.Frame object with attributes wave, flux, ivar, etc.
    """
    #- check if filename is (night, expid, camera) tuple instead
    if not isinstance(filename, (str, unicode)):
        night, expid, camera = filename
        filename = findfile('frame', night, expid, camera)

    if not os.path.isfile(filename) :
        raise IOError("cannot open"+filename)

    fx = fits.open(filename, uint=True, memmap=False)
    hdr = fx[0].header
    flux = native_endian(fx['FLUX'].data.astype('f8'))
    ivar = native_endian(fx['IVAR'].data.astype('f8'))
    wave = native_endian(fx['WAVELENGTH'].data.astype('f8'))
    if 'MASK' in fx:
        mask = native_endian(fx['MASK'].data)
    else:
        mask = None   #- let the Frame object create the default mask
        
    resolution_data = native_endian(fx['RESOLUTION'].data.astype('f8'))
    
    if 'FIBERMAP' in fx:
        fibermap = fx['FIBERMAP'].data
    else:
        fibermap = None
        
    if 'CHI2PIX' in fx:
        chi2pix = native_endian(fx['CHI2PIX'].data.astype('f8'))
    else:
        chi2pix = None

    fx.close()

    if nspec is not None:
        flux = flux[0:nspec]
        ivar = ivar[0:nspec]
        resolution_data = resolution_data[0:nspec]
        if chi2pix is not None:
            chi2pix = chi2pix[0:nspec]
        if mask is not None:
            mask = mask[0:nspec]

    # return flux,ivar,wave,resolution_data, hdr
    return Frame(wave, flux, ivar, mask, resolution_data, meta=hdr, fibermap=fibermap, chi2pix=chi2pix)
