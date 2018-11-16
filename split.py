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
import re
import gvar
import conf
from lib import melib
from fs import ext4
from block import block
from scsi import scsi

sgSCSI_BLOCK_SIZE_BYTE = gvar.gSCSI_LogicalBlockSize_Bytes
sgBLOCK_SECTOR_SIZE_BYTE = gvar.gLogicalSectorSize_Bytes


sgKey_Line = "#           TASK-PID   CPU#  ||||    TIMESTAMP  FUNCTION"
sgTracer = " "
sgPIDs_Files_dict = {}
sgTags_File_dict = {}

'''
pid to logical address dictionary.
{(pid, op): ['2314', 'dad'], ...}
'''
sgPID_To_ReqAddresses_dict = dict()


def save_one_line2pidfile(pid, line):
    global sgPIDs_Files_dict

    if pid in sgPIDs_Files_dict.keys():  # add one line
        fd = sgPIDs_Files_dict[pid]
        with open(fd, 'a+') as f:
            f.write(line)
    else:  # Create new one
        #file = os.getcwd() + "/"+pid+".dat"
        file = gvar.gOutput_Dir_Default+"/" + pid + ".dat"
        sgPIDs_Files_dict[pid] = file
        with open(file, 'wt') as f:
            f.write(sgKey_Line)
            f.write('\n')
            f.write(line)


# split lines into several file according to their PID associated with
# by default, each line consists of:
# TASK-PID  CPU#  TIMESTAMP FUNCTION
#
# Here's a sample line:
# TASK-PID   CPU#  ||||    TIMESTAMP  FUNCTION
#   | |       |   ||||       |         |
# iozone-4066  [001] ...1  2911.060662: generic_file_read_iter <-new_sync_read
# iozone-4066  [001] ...1  2911.060694: blk_start_plug <-__do_page_cache_readahead


def split_file_by_pid(lines):

    global sgKey_Line
    global sgPIDs_Files_dict
    global sgTracer

    fields = []
    # find start line:
    line_no = 0
    for line in lines:
        line_no += 1
        origin_line = line

        if melib.is_skip_this_line(line):
            continue

        # scan comment lines for the field key
        if line.startswith("#"):
            if gvar.analyzer_header_of_file(line):
                fields = gvar.gFtrace_log_fields
                print(gvar.gFtrace_log_fields)
            continue

        melib.me_dbg("%d: %s" % (line_no, line[:-1]))

        line = re.sub(r'\s+', ' ', line)  # remove more whitespace, just keep one
        parts = line.split()
        if fields:
            if "TASK-PID" in fields:
                """
                For some specail event log, the function-pid field is separated by space, 
                such as: "POSIX timer 0-2291". for this case, need to rebase its each part
                position.
                """
                gap = 0
                if not melib.is_cpu_field_string(parts[fields.index('CPU#')]):
                    cpu_index = melib.where_is_cpu_field(parts)
                    if cpu_index is not None:
                        if cpu_index > fields.index('CPU#'):
                            gap = cpu_index - fields.index('CPU#')
                        else:
                            melib.me_error("CPU# field index is not consistent with Line %d" %
                                           line_no)
                    else:
                        melib.me_error("CPU# field doesn't exist in Line %d" %
                                       line_no)
                        continue

                task_pid = parts[gap + 0]
                cur_pid = task_pid.split("-")[-1]  # get PID
                func = parts[fields.index('FUNCTION') + gap].split(':')[0]  # get function name
                spec_func = 0

                func_str = line.strip().split(' ', fields.index("FUNCTION")+gap)[-1]  # split by space until "FUNCTION"

                if func in conf.gEvents_dict['block']:  # sgBlock_Key_Trace_Events_list:  # filter Block events
                    event_dict = block.blk_functions2dict_parser(func_str)
                    if event_dict[gvar.gmenu_func] != 'block_unplug' and event_dict[gvar.gmenu_func] != 'block_plug':
                        spec_func = 1
                elif func in conf.gEvents_dict['scsi']:  # sgSCSI_Key_Trace_Events_list:  # filter SCSI events
                    event_dict = scsi.scsi_functions2dict_parser(func_str)
                    spec_func = 1

                if spec_func == 1:
                    if "block_bio_remap" == event_dict[gvar.gmenu_func]:  # figure out the LBA of the request
                        sgPID_To_ReqAddresses_dict.setdefault((cur_pid, event_dict[gvar.gmenu_op]),
                                                              []).append(event_dict[gvar.gmenu_lba])
                        #if sgPID_To_ReqAddresses_dict[cur_pid][event_dict[gmenu_op]] is None:
                        #   sgPID_To_ReqAddresses_dict[cur_pid][event_dict[gmenu_op]] = [event_dict['address']]
                        #else:
                        #    addr_list = sgPID_To_ReqAddresses_dict[cur_pid][event_dict[gmenu_op]]
                        #    addr_list.append(event_dict['address'])
                    else:
                        pid_self = 0
                        if (cur_pid, event_dict[gvar.gmenu_op]) in sgPID_To_ReqAddresses_dict.keys():
                            if event_dict[gvar.gmenu_lba] in sgPID_To_ReqAddresses_dict[(cur_pid, event_dict[gvar.gmenu_op])]:
                                # first check itself
                                pid_self = 1
                        if pid_self != 1:
                            match_num = 0
                            match_pids = []
                            for (temp_pid, temp_op) in sgPID_To_ReqAddresses_dict.keys():
                                if (temp_pid, temp_op) != (cur_pid, event_dict[gvar.gmenu_op]):
                                    # we don't check cur_pid since we checked before
                                    if event_dict[gvar.gmenu_lba] in sgPID_To_ReqAddresses_dict[(temp_pid, temp_op)]:
                                        if event_dict[gvar.gmenu_op] is temp_op:
                                            match_num = match_num + 1
                                            match_pids.append(temp_pid)
                                            cur_pid = temp_pid
                                        else:
                                            melib.me_dbg("Operation type un-match! current %s, temp %s" %
                                                         (event_dict[gvar.gmenu_op], temp_op))
                            if match_num == 0:
                                melib.me_warning("Line: %d, address: %s 0 match PID" %
                                                 (line_no, event_dict[gvar.gmenu_op]))
                            if match_num > 1:
                                melib.me_warning("line %d: address %s " %
                                                 (line_no, event_dict[gvar.gmenu_op]))
                                melib.me_warning("---match pids %s, using pid %d " %
                                                 (match_num, cur_pid))
                save_one_line2pidfile(cur_pid, origin_line)  # write this line into relevant PID file
            else:
                print("Error: trace log is missing CPU field.")
                sys.exit(2)

    return sgPIDs_Files_dict
