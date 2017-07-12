#! /usr/bin/env python2
############################################################
# Program is part of PySAR v1.0                            #
# Copyright(c) 2013, Heresh Fattahi                        #
# Author:  Heresh Fattahi                                  #
############################################################
# Yunjun, Dec 2015: Add support for coherence/wrapped, update display
# Yunjun, Jun 2016: Add plot_network(), plot_bperp_hist(),
#                   axis_adjust_date_length(), igram_pairs()


import sys
import os
import argparse

import h5py
import numpy as np
import matplotlib.pyplot as plt

import pysar._pysar_utilities as ut
import pysar._datetime as ptime
import pysar._network  as pnet
import pysar._readfile as readfile
from pysar._readfile import multi_group_hdf5_file, multi_dataset_hdf5_file, single_dataset_hdf5_file

  
######################################
BL_LIST='''
070106     0.0   0.03  0.0000000  0.00000000000 2155.2 /scratch/SLC/070106/
070709  2631.9   0.07  0.0000000  0.00000000000 2155.2 /scratch/SLC/070709/
070824  2787.3   0.07  0.0000000  0.00000000000 2155.2 /scratch/SLC/070824/
'''

DATE12_LIST='''
070709-100901
070709-101017
070824-071009
'''

EXAMPLE='''example:
  plot_network.py unwrapIfgram.h5
  plot_network.py unwrapIfgram.h5 --coherence coherence_spatialAverage.txt
  plot_network.py unwrapIfgram.h5 --coherence coherence.h5 --mask Mask.h5
  plot_network.py Modified_coherence.h5 --save
  plot_network.py Modified_coherence.h5 --nodisplay
  plot_network.py ifgram_list.txt              -b bl_list.txt
  plot_network.py unwrapIfgram_date12_list.txt -b bl_list.txt
'''


def cmdLineParse():
    parser = argparse.ArgumentParser(description='Display Network of Interferograms',\
                                     formatter_class=argparse.RawTextHelpFormatter,\
                                     epilog=EXAMPLE)
    
    parser.add_argument('file',\
                        help='file with network information, supporting:\n'+\
                             'HDF5 file: unwrapIfgram.h5, Modified_coherence.h5\n'+\
                             'Text file: list of date12, generated by selectPairs.py or plot_network.py, i.e.:'+DATE12_LIST)
    parser.add_argument('-b','--bl','--baseline', dest='bl_list_file', default='bl_list.txt',\
                        help='baseline list file, generated using createBaselineList.pl, i.e.:'+BL_LIST)
    
    # Display coherence
    coh_group = parser.add_argument_group('Display Coherence','Show coherence of each interferogram pair with color')
    coh_group.add_argument('--coherence', dest='coherence_file',\
                           help='display pairs in color based on input coherence\n'+\
                                'i.e. coherence_spatialAverage.txt (generated by spatial_average.py)\n'+\
                                '     coherence.h5')
    coh_group.add_argument('-m', dest='disp_min', type=float, default=0.2, help='minimum coherence to display')
    coh_group.add_argument('-M', dest='disp_max', type=float, default=1.0, help='maximum coherence to display')
    coh_group.add_argument('-c','--colormap', dest='colormap', default='RdBu',\
                           help='colormap for display, i.e. RdBu, jet, ...')
    coh_group.add_argument('--mask', dest='mask_file', help='mask file used to calculate the coherence')

    # Figure  Setting
    fig_group = parser.add_argument_group('Figure','Figure settings for display')
    fig_group.add_argument('--fontsize', type=int, default=12, help='font size in points')
    fig_group.add_argument('--lw','--linewidth', dest='linewidth', type=int, default=2, help='line width in points')
    fig_group.add_argument('--mc','--markercolor', dest='markercolor', default='orange', help='marker color')
    fig_group.add_argument('--ms','--markersize', dest='markersize', type=int, default=16, help='marker size in points')

    fig_group.add_argument('--dpi', dest='fig_dpi', type=int, default=150,\
                           help='DPI - dot per inch - for display/write')
    fig_group.add_argument('--figsize', dest='fig_size', type=float, nargs=2,\
                           help='figure size in inches - width and length')
    fig_group.add_argument('--figext', dest='fig_ext',\
                           default='.pdf', choices=['.emf','.eps','.pdf','.png','.ps','.raw','.rgba','.svg','.svgz'],\
                           help='File extension for figure output file\n\n')
    
    fig_group.add_argument('--list', dest='save_list', action='store_true', help='save pairs/date12 list into text file')
    fig_group.add_argument('--save', dest='save_fig', action='store_true', help='save the figure')
    fig_group.add_argument('--nodisplay', dest='disp_fig', action='store_false', help='save and do not display the figure')

    inps = parser.parse_args()
    if not inps.disp_fig:
        inps.save_fig = True
    
    return inps


##########################  Main Function  ##############################
def main(argv):
    inps = cmdLineParse()
    if not inps.disp_fig:
        plt.switch_backend('Agg')
    #print '\n******************** Plot Network **********************'

    ##### 1. Read Info
    # Read dateList and bperpList
    ext = os.path.splitext(inps.file)[1]
    if ext in ['.h5']:
        atr = readfile.read_attribute(inps.file)
        k = atr['FILE_TYPE']
        print 'reading date and perpendicular baseline from '+k+' file: '+os.path.basename(inps.file)
        if not k in multi_group_hdf5_file:
            raise ValueError('only the following file type are supported:\n'+str(multi_group_hdf5_file))
        pbase_list = ut.perp_baseline_ifgram2timeseries(inps.file)[0]
        date8_list = ptime.ifgram_date_list(inps.file)
    else:
        print 'reading date and perpendicular baseline from baseline list file: '+inps.bl_list_file
        date8_list, pbase_list = pnet.read_baseline_file(inps.bl_list_file)[0:2]
    print 'number of acquisitions  : '+str(len(date8_list))

    # Read Pairs Info
    print 'reading pairs info from file: '+inps.file
    date12_list = pnet.get_date12_list(inps.file)
    print 'number of interferograms: '+str(len(date12_list))

    # Read drop_ifgram 
    date8_list_drop = []
    date12_list_drop = []
    if ext in ['.h5','.he5']:
        h5 = h5py.File(inps.file, 'r')
        ifgram_list_all = sorted(h5[k].keys())
        ifgram_list_keep = ut.check_drop_ifgram(h5, atr, ifgram_list_all)
        date12_list_keep = ptime.list_ifgram2date12(ifgram_list_keep)
        # Get date12_list_drop
        date12_list_drop = sorted(list(set(date12_list) - set(date12_list_keep)))
        print 'number of interferograms marked as dropped: '+str(len(date12_list_drop))

        # Get date_list_drop
        m_dates = [i.split('-')[0] for i in date12_list_keep]
        s_dates = [i.split('-')[1] for i in date12_list_keep]
        date8_list_keep = ptime.yyyymmdd(sorted(list(set(m_dates + s_dates))))
        date8_list_drop = sorted(list(set(date8_list) - set(date8_list_keep)))
        print 'number of acquisitions marked as dropped: '+str(len(date8_list_drop))

    # Read Coherence List
    inps.coherence_list = None
    if inps.coherence_file and os.path.isfile(inps.coherence_file):
        ext = os.path.splitext(inps.coherence_file)[1]
        if ext in ['.h5']:
            listFile = os.path.splitext(inps.coherence_file)[0]+'_spatialAverage.txt'
            if os.path.isfile(listFile):
                print 'reading coherence value from existed '+listFile
                fcoh = np.loadtxt(listFile, dtype=str)
                inps.coherence_list  = [float(i) for i in fcoh[:,1]]
                inps.coh_date12_list = [i        for i in fcoh[:,0]]
            else:
                print 'calculating average coherence value from '+inps.coherence_file
                if inps.mask_file:
                    mask = readfile.read(inps.mask_file)[0]
                else:
                    mask = None
                inps.coherence_list  = ut.spatial_average(inps.coherence_file, mask, saveList=True)
                inps.coh_date12_list = pnet.get_date12_list(inps.coherence_file)
        else:
            print 'reading coherence value from '+inps.coherence_file
            fcoh = np.loadtxt(inps.coherence_file, dtype=str)
            inps.coherence_list  = [float(i) for i in fcoh[:,1]]
            inps.coh_date12_list = [i        for i in fcoh[:,0]]

        # Check length of coherence file and input file
        if not set(inps.coh_date12_list) == set(date12_list):
            print 'WARNING: input coherence list has different pairs/date12 from input file'
            print 'turn off the color plotting of interferograms based on coherence'
            inps.coherence_list = None

    #inps.coh_thres = 0.7
    ##### 2. Plot
    # Fig 1 - Baseline History
    fig = plt.figure()
    ax = fig.add_subplot(111)
    ax = pnet.plot_perp_baseline_hist(ax, date8_list, pbase_list, vars(inps), date8_list_drop)

    figName = 'BperpHistory'+inps.fig_ext
    if inps.save_fig:
        fig.savefig(figName,bbox_inches='tight')
        print 'save figure to '+figName

    # Fig 2 - Coherence Matrix
    if inps.coherence_list:
        figName = 'CoherenceMatrix'+inps.fig_ext
        if inps.fig_size:
            fig = plt.figure(figsize=inps.fig_size)
        else:
            fig = plt.figure()
        ax = fig.add_subplot(111)
        ax = pnet.plot_coherence_matrix(ax, date12_list, inps.coherence_list)

        if inps.save_fig:
            fig.savefig(figName, bbox_inches='tight')
            print 'save figure to '+figName

    # Fig 3 - Min/Max Coherence History
    if inps.coherence_list:
        figName = 'CoherenceHistory'+inps.fig_ext
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax = pnet.plot_coherence_history(ax, date12_list, inps.coherence_list)

        if inps.save_fig:
            fig.savefig(figName, bbox_inches='tight')
            print 'save figure to '+figName

    # Fig 4 - Interferogram Network
    if inps.fig_size:
        fig = plt.figure(figsize=inps.fig_size)
    else:
        fig = plt.figure()
    ax = fig.add_subplot(111)
    ax = pnet.plot_network(ax, date12_list, date8_list, pbase_list, vars(inps), date12_list_drop)

    figName = 'Network'+inps.fig_ext
    if inps.save_fig:
        fig.savefig(figName,bbox_inches='tight')
        print 'save figure to '+figName

    if inps.save_list:
        txtFile = os.path.splitext(inps.file)[0]+'_date12_list.txt'
        np.savetxt(txtFile, date12_list, fmt='%s')
        print 'save pairs/date12 info to file: '+txtFile


    if inps.disp_fig:
        plt.show() 

############################################################
if __name__ == '__main__':
    main(sys.argv[1:])



