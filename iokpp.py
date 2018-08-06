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

import re
import gvar
import e2e
import wa
from lib import melib
from fs import ext4, vfs
from scsi import scsi
from block import block


fields = ["None"]


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
    elif functions.startswith("scsi") or functions.startswith("ufs"):
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


def line_by_line_parser(original_file_lines, is_e2e, is_wa):
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
        ''' take one line from log '''
        gvar.gCurr_line += 1
        func_dict = parsing_one_line(line_str)
        if func_dict:
            ''' Parsing success'''
            if is_e2e:
                try:
                    e2e.add_to_pid_req_property_tree(func_dict)
                except melib.DefinedExcepton as e:
                    melib.me_warning("Add item error!")
                    melib.me_warning(func_dict)
                    melib.me_warning(e)

            if is_wa:
                try:
                    wa.add_to_wa_property_tree(func_dict)
                except melib.DefinedExcepton as e:
                    melib.me_warning("Add item error!")
                    melib.me_warning(func_dict)
                    melib.me_warning(e)

            func_dict.clear()


def iokpp_main(original_file_lines, is_e2e, is_wa):
    line_by_line_parser(original_file_lines, is_e2e, is_wa)
    if is_e2e:
        e2e.e2e_main()
    if is_wa:
        wa.wa_main()
