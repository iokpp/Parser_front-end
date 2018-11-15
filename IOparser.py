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
import IO
import ptcl
import e2e
import re
import gvar
import e2e_req
import e2e_event
import wr
from lib import melib
from fs import ext4, vfs
from scsi import scsi
from block import block

VERSION = "0.0.1-20180901"
fields = ["None"]

gFileIn = None
gKeep_Files = 0  # used to control if delete the files created
gPIDs_Files_dic = {}


def parser_post_dis():
    if not gKeep_Files:
        for f in gPIDs_Files_dic.values():  # delete pid files
            melib.me_dbg("Del file created %s" % f)
            os.remove(f)


def parsing_one_line(line):
    """
    This function is to parse the input line, and
    build up sgPID_Req_Property_DataBank.
    :param
        lines: one line string of log file
    :return: if success, the parsed event dictionary; otherwise, False.
    """
    # find start line:
    global fields
    line_no = gvar.gCurr_line

    tmp_req_parser_property_dict = {}
    tmp_req_parser_property_dict = gvar.create_default_property_dict()

    if melib.is_skip_this_line(line):
        return False

    # scan comment lines
    if line.startswith("#"):
        if gvar.analyzer_header_of_file(line):
            fields = gvar.gFtrace_log_fields  # ["TASK-PID", "CPU", "TIMESTAMP", "FUNCTION"]
            melib.me_dbg("L%d %s" % (gvar.gCurr_line, line))
        return False  # go to next line

    melib.me_dbg("%d: %s" % (line_no, line[:-1]))
    line = re.sub(r'\s+', ' ', line)  # remove more whitespace, just keep one

    """
    For some special event log, the function-pid field is separated by space, 
    such as: "POSIX timer 0-2291". for this case, need to rebase its each part
    position.
    """
    gap = 0
    parts0 = line.split()
    if not melib.is_cpu_field_string(parts0[fields.index('CPU#')]):
        cpu_index = melib.where_is_cpu_field(parts0)
        if cpu_index is not None:
            if cpu_index > fields.index('CPU#'):
                gap = cpu_index - fields.index('CPU#')
            else:
                melib.me_error("CPU# field index is not consistent with Line %d" %
                               gvar.gCurr_line)
        else:
            melib.me_error("CPU# field doesn't exist in Line %d" %
                           gvar.gCurr_line)
            return False

    parts = line.strip().split(' ', fields.index("FUNCTION") + gap)  # split by space

    task_pid = parts[fields.index("TASK-PID") + gap]
    cur_pid = task_pid.rsplit(b'-')[-1]  # get PID
    tmp_req_parser_property_dict[gvar.gmenu_task] = task_pid.rsplit(b'-')[0]
    tmp_req_parser_property_dict[gvar.gmenu_PID] = task_pid  # cur_pid
    tmp_req_parser_property_dict[gvar.gmenu_OriginalPid] = task_pid

    timestamp = parts[fields.index("TIMESTAMP") + gap].split(b':')[0]  # get time stamp of this line
    tmp_req_parser_property_dict[gvar.gmenu_time] = timestamp
    functions = parts[fields.index('FUNCTION') + gap]
    melib.me_dbg("Line=%d--> PID: %s, timestamp: %s, functions: '%s'" % \
                 (gvar.gCurr_line, cur_pid, timestamp, functions))

    if functions.startswith("sys"):
        # VFS
        function_dict = vfs.vfs_functions2dict_parser(functions)
    elif functions.startswith("ext4"):
        # Ext4 layer
        function_dict = ext4.ext4_functions2dict_parser(functions)
    elif functions.startswith("block") or functions.startswith("blk"):
        # Block layer
        function_dict = block.blk_functions2dict_parser(functions)
    elif functions.startswith("scsi"):
        # SCSI
        function_dict = scsi.scsi_functions2dict_parser(functions)
    else:
        return False

    ''' add this event '''
    if function_dict is None:
        ''' Goto next line, since this event/function
        is not in the checked list.'''
        return False
    else:
        # merge two dictionaries into one
        tmp_req_parser_property_dict.update(function_dict)

    return tmp_req_parser_property_dict  # success, return the parsed dictionary.


def line_by_line_parser(original_file_lines, is_e2e, is_wa, is_IO):
    """
    To parse this line string and fill in the sgPID_Req_Property_DataBank and
    WA dateBank.
    :param original_file_lines: The original line string
    :param is_e2e: True or False
    :param is_wa: True or False
    :return: None
    """
    gvar.gCurr_line = 0

    for line_str in original_file_lines:
        # take one line from log
        gvar.gCurr_line += 1
        func_dict = parsing_one_line(line_str)
        if func_dict:
            # Parsing success
            if is_e2e:
                if gvar.gE2E_mode == gvar.gE2E_mode_group_by_request:
                    # Add this parsed result into e2e_req module data bank
                    try:
                        e2e_req.add_to_event_property_tree(func_dict)
                    except melib.DefinedExcepton as e:
                        melib.me_warning("Add item error!")
                        melib.me_warning(func_dict)
                        melib.me_warning(e)
                elif gvar.gE2E_mode == gvar.gE2E_mode_group_by_event:
                    # Add this parsed result into e2e_event module data bank
                    try:
                        e2e_event.add_to_event_property_tree(func_dict)
                    except melib.DefinedExcepton as e:
                        melib.me_warning("Add item error!")
                        melib.me_warning(func_dict)
                        melib.me_warning(e)
            if is_wa:
                try:
                    wr.add_to_wa_property_tree(func_dict)
                except melib.DefinedExcepton as e:
                    melib.me_warning("Add item error!")
                    melib.me_warning(func_dict)
                    melib.me_warning(e)
            if is_IO:
                try:
                    IO.add_to_IO_property_tree(func_dict)
                except melib.DefinedExcepton as e:
                    melib.me_warning("Add item error!")
                    melib.me_warning(func_dict)
                    melib.me_warning(e)
            if gvar.gPtcl_analyzer:
                try:
                    ptcl.add_to_ptcl_property_tree(func_dict)
                except melib.DefinedExcepton as e:
                    melib.me_warning("add to ptcl error!")
                    melib.me_warning(func_dict)
                    melib.me_warning(e)

            func_dict.clear()


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
                                    'e2e=', 'out=', 'pending', 'wa=', 'io', 'ptcl=', 'start=', 'end='])
    except getopt.GetoptError:
            melib.usage()
            sys.exit(2)

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
        if opt_name in ('--io', 'io'):
            gvar.gIO_analyzer = True
        if opt_name in ('--ptcl', 'ptcl'):

            if opt_value in gvar.gPtcl_analyzer_support_list:
                gvar.gPtcl_mode = opt_value
                gvar.gPtcl_analyzer = True
                print("Protocol option is %s" % opt_value)
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

    melib.mkdir(gvar.gOutput_Dir_Default)
    try:
        melib.LogFD = open(gvar.gOutput_Dir_Default + "/warning.log", "wt")
    except:
        print("Open/Create Warning.log failed.")
        melib.LogFD = 0
    '''
    if is_e2e:
        gvar.gOutput_dir_Raw_data = gvar.gOutput_Dir_Default + '/e2e/' +'raw_data/'
        gvar.gOutput_dir_e2e = gvar.gOutput_Dir_Default + '/e2e/' + gvar.gE2E_mode + '/'
        """ mkdir the output folder """
        melib.mkdir(gvar.gOutput_dir_e2e)
        melib.mkdir(gvar.gOutput_dir_Raw_data)
        """ open the warning log file """
    '''

    if is_split:
        gPIDs_Files_dic = split.split_file_by_pid(lines)
        print("Split into %d files." % len(gPIDs_Files_dic))
        print(gPIDs_Files_dic)

    line_by_line_parser(lines, is_e2e, is_wa, gvar.gIO_analyzer)
    if is_e2e:
        gvar.gOutput_dir_Raw_data = gvar.gOutput_Dir_Default + '/e2e/' +'raw_data/'
        gvar.gOutput_dir_e2e = gvar.gOutput_Dir_Default + '/e2e/' + gvar.gE2E_mode + '/'
        """ mkdir the output folder """
        melib.mkdir(gvar.gOutput_dir_e2e)
        melib.mkdir(gvar.gOutput_dir_Raw_data)
        """ open the warning log file """
        e2e.e2e_main(lines, is_e2e)
    elif is_wa:
        wr.wr_main()
    elif gvar.gIO_analyzer:
        IO.io_main(lines, opts)
    elif gvar.gPtcl_analyzer:
        ptcl.ptcl_main(lines, opts)

    if not gKeep_Files:
        parser_post_dis()
    if melib.LogFD:
        melib.LogFD.close()


if __name__ == "__main__":
    main()
