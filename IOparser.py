#!/usr/bin/python
# # !/usr/bin/env python
#
# Copyright (C) Micron Semiconductor Corp., 2018
# This program is free software; you can redistribute and/or
# modify it under the terms of the GUN General Public License
# as published by the Free Software Foundation.
#
#
# 2018-Jun-1:Initial version by Bean Huo beanhuo@micron.com
#


import sys
import os
import getopt
from lib import melib
import gvar
import split
import ptcl
import e2e

VERSION = "0.0.1-20180901"

gFileIn = None
gKeep_Files = 0  # used to control if delete the files created
gPIDs_Files_dic = {}


def parser_post_dis():
    if not gKeep_Files:
        for f in gPIDs_Files_dic.values():  # delete pid files
            melib.me_dbg("Del file created %s" % f)
            os.remove(f)


def main():
    global gFileIn
    global gKeep_Files
    global gPIDs_Files_dic

    is_split = False
    is_e2e = False
    is_wa = False

    try:
        opts, args = getopt.getopt(sys.argv[1:], '-h-i:-v-d-k',
                                   ['split', 'keep', 'debug', 'help', 'version', 'input=',
                                    'e2e=', 'out=', 'pending', 'wa=','protocol=', 'start=', 'end='])
    except getopt.GetoptError:
            melib.usage()
            sys.exit(2)
    print(opts)
    for opt_name, opt_value in opts:
        if opt_name in ('-h', '--help'):
            print("\n%s version: %s" % (os.path.basename(sys.argv[0]), VERSION))
            melib.usage()
            exit()
        if opt_name in ('-v', '--version'):
            print("%s: version %s" %
                  (os.path.basename(sys.argv[0]), VERSION))
            sys.exit(0)
        if opt_name in ('-d', '--debug'):
            melib.DEBUG = True
        if opt_name in ('-k', '--keep'):
            gKeep_Files = True
        if opt_name in ('--out', 'out'):
            gvar.gOutput_Dir_Default = opt_value
            melib.mkdir(gvar.gOutput_Dir_Default)
        if opt_name in ('--pending', 'pending'):
            gvar.gRunning_pending_mode = True
        if opt_name in ('-i', '--input'):
            gFileIn = opt_value
            melib.me_dbg("Input file is %s" % gFileIn)
        if opt_name in ('--split', 'split'):
            is_split = True
            gKeep_Files = True
        if opt_name in ('--protocol', 'protocol'):
            if opt_value in gvar.gProtocol_analyzer_support_list:
                gvar.gProtocol_mode = opt_value
                gvar.gProtocol_analyzer = True
            else:
                print("Unknown the protocol %s." % opt_value)
                exit(1)
        if opt_name in ('--e2e', 'e2e'):
            is_e2e = True
            e2e_mode = opt_value
            if e2e_mode == gvar.gE2E_mode_group_by_event or \
                    e2e_mode == gvar.gE2E_mode_group_by_request:
                print("E2E mode is %s." % e2e_mode)
                gvar.gE2E_mode = e2e_mode
            else:
                print("E2E will use default mode %s." % gvar.gE2E_mode)
        if opt_name in ('--start', 'start'):
            start_index = opt_value
            if str.isdigit(start_index):
                gvar.gDefault_graph_window_start_from_item = int(start_index)
                print("Change start index from %d." % gvar.gDefault_graph_window_start_from_item)
            else:
                print("Error: The specified start index is not an valid integer.")
                exit(1)
        if opt_name in ('end', '--end'):
            end_index = opt_value
            if str.isdigit(end_index):
                gvar.gDefault_graph_window_end_at_item = int(end_index)
                print("Change index end at %d." % gvar.gDefault_graph_window_end_at_item)
            else:
                print("Error: The specified end index is not an valid integer.")
                exit(1)

        if opt_name in ('--wa', 'wa'):
            is_wa = True
            wa_mode = opt_value
            if wa_mode == gvar.gWA_RA_mode_by_pid or \
                    wa_mode == gvar.gWA_RA_mode_by_task:
                print("WA/RA mode is %s." % wa_mode)
                gvar.gWA_RA_mode = wa_mode
            else:
                print("WA/RA will use default mode %s." % gvar.gWA_RA_mode)

    if gvar.gDefault_graph_window_end_at_item < gvar.gDefault_graph_window_start_from_item:
        print("Error: The specified start index is bigger than end index.")
        exit(1)

    if not gFileIn:
        print("No input log specified. See help. (Use -h)")
        sys.exit(1)
    else:
        """ open the log file """
        try:
            lines = open(gFileIn, "r").readlines()
        except:
            print("Problem opening file: %s" % gFileIn)
            sys.exit(1)

    if is_e2e is True:
        gvar.gOutput_dir_Raw_data = gvar.gOutput_Dir_Default + '/e2e/' +'raw_data/'
        gvar.gOutput_dir_e2e = gvar.gOutput_Dir_Default + '/e2e/' + gvar.gE2E_mode + '/'
        """ mkdir the output folder """
        melib.mkdir(gvar.gOutput_dir_e2e)
        melib.mkdir(gvar.gOutput_dir_Raw_data)
        """ open the warning log file """
        try:
            melib.LogFD = open(gvar.gOutput_dir_e2e + "/warning.log", "wt")
        except:
            print("Open/Create Warning.log failed.")
            melib.LogFD = 0

    if is_split:
        gPIDs_Files_dic = split.split_file_by_pid(lines)
        print("Split into %d files." % len(gPIDs_Files_dic))
        print(gPIDs_Files_dic)
    if is_e2e or is_wa:
        e2e.e2e_main(lines, is_e2e, is_wa)
    if gvar.gProtocol_analyzer is True:
        ptcl.ptcl_main(lines, opts)

    if not gKeep_Files:
        parser_post_dis()
    if melib.LogFD:
        melib.LogFD.close()


if __name__ == "__main__":
    main()
