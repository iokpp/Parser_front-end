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
import e2e
import wa
import iokpp

VERSION = "0.0.1-20180601"

gFileIn = " "
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
                                    'e2e', 'out=', 'pending', 'wa'])
    except getopt.GetoptError:
            melib.usage()
            sys.exit(2)
    for opt_name, opt_value in opts:
        if opt_name in ('-h', '--help'):
            melib.usage()
            exit()
        if opt_name in ('-v', '--version'):
            print("%s: version %s" %
                  (os.path.basename(sys.argv[0]), VERSION))
            sys.exit(0)
        if opt_name in ('-i', '--input'):
            gFileIn = opt_value
            melib.me_dbg("Input file is %s" % gFileIn)
        if opt_name in ('-d', '--debug'):
            melib.DEBUG = True
        if opt_name in ('-k', '--keep'):
            gKeep_Files = True
        if opt_name in ('--split', 'split'):
            is_split = True
            gKeep_Files = True
        if opt_name in ('--e2e', 'e2e'):
            is_e2e = True
        if opt_name in ('--out', 'out'):
            gvar.gOutput_Dir_Default = opt_value
        if opt_name in ('--pending', 'pending'):
            gvar.gRunning_pending_mode = True
        if opt_name in ('--wa', 'wa'):
            is_wa = True
    """ mkdir the output folder """
    melib.mkdir(gvar.gOutput_Dir_Default)
    if not gFileIn:
        print("No Trace log specified. See help. (Use -h)")
        sys.exit(1)
    """ open the warning log file """
    try:
        melib.LogFD = open(gvar.gOutput_Dir_Default + "warning.log", "wt")
    except:
        print("Open/Create Warning.log failed.")
        melib.LogFD = 0

    """ open the log file """
    try:
        lines = open(gFileIn, "r").readlines()
    except:
        print("Problem opening file: %s" % gFileIn)
        sys.exit(1)

    if is_split:
        gPIDs_Files_dic = split.split_file_by_pid(lines)
        melib.me_dbg(gPIDs_Files_dic)

    if is_e2e or is_wa:
        iokpp.iokpp_main(lines, is_e2e, is_wa)


        '''
        try:
            e2e.e2e_main(lines, gPIDs_Files_dic)
        except melib.DefinedExcepton as e:
            print("Failed parsing the input file: %s" % gFileIn)
            print(e)
            sys.exit(1)
        finally:
            sys.exit(0)

        if is_wa:
        try:
            wa.wa_main(lines)
        except melib.DefinedExcepton as e:
            print("Failed doing WA for file %s" % gFileIn)
            print(e)
            sys.exit(1)
        '''
    if not gKeep_Files:
        parser_post_dis()
    if melib.LogFD:
        melib.LogFD.close()


if __name__ == "__main__":
    main()
