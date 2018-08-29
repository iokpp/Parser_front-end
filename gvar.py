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
from lib import melib

gOutput_Dir_Default = "./out/"
gCurr_line = 0
"""
gRunning_pending_mode is used to specify the running mode of tool. 
if True, it is running until entering exit command. if false. the
tool will exit immediately after finishing certain analyzing item
specified in the command options.
"""
gRunning_pending_mode = False

"""
gDefault_graph_window_end_at_item is used to specify the maximum items 
which are showed in the histogram and scatter graph.
"""
gDefault_graph_window_start_from_item = 0
gDefault_graph_window_end_at_item = 4096
gDefault_histogram_threshold = 1024

gSCSI_LogicalBlockSize_Bytes = 4096  # the default logical block size in SCSI layer
gLogicalSectorSize_Bytes = 512       # the default logical sector size in block layer
gSectorsPerBlock = gSCSI_LogicalBlockSize_Bytes / gLogicalSectorSize_Bytes  # how many sectors per block

gmenu_task = 'Task'
gmenu_PID = 'PID'
gmenu_OriginalPid = 'OrigPID'
gmenu_func = 'Function'
gmenu_len = 'Len_bytes'
gmenu_events = 'Event_Str'
gmenu_pre_event = 'Pre_event_str'
gmenu_op = 'Op_W_R'
gmenu_time = 'Timestamp'
gmenu_lba = 'LBA'  # BY 512 BYTES
gmenu_sectors = 'Sectors'
gmenu_blocks = 'Blocks'
gmenu_req_seq = 'Request_sequence'
gmenu_event_seq = 'Event_sequence'
gmenu_reqs_unplug = 'plug_reqs_unplug'

gMax = 'MAX'
gMin = 'MIN'
gMean = 'MEAN'
gAmount = 'AMOUNT'
gTotal = 'TOTAL'

''' Defined the string flags '''
gReqEvent_start = 'Enter_VFS'
gReqEvent_end = 'Exit_VFS'
gWrite_Req = "write"
gRead_Req = "read"

# for the inputted ftrace file, must at least contain these
# fields in the log
gFtrace_log_fields = [] #"TASK-PID", "||||", "CPU", "TIMESTAMP", "FUNCTION"

gBlk_Events_Write_OP_list = ['WS', 'W', 'FWFS', 'WFS']
gBlk_Events_Read_OP_list = ['RS', 'R', 'R', 'RM', 'RA', 'RSM']

gE2E_mode_group_by_event = 'event'
gE2E_mode_group_by_request = 'request'
gE2E_mode = gE2E_mode_group_by_event  # default mode

gWA_RA_mode_by_pid = 'pid'
gWA_RA_mode_by_task = 'task'
gWA_RA_mode = gWA_RA_mode_by_task

def analyzer_header_of_file(line):

    global gFtrace_log_fields

    # scan comment lines for the field key
    if line.startswith("#"):
        # check tracer used in the log
        if line.find("tracer:") != -1:
            tracer = line.split()[-1]
            print("The trace log file is using %s tracer" % tracer)

        # check this line is a field line or not ?
        # also check if this log contains the required fields
        if line.find("FUNCTION") != -1 and line.find("TIMESTAMP") != -1:
            # fields = line[1:].split()
            fields = line.strip('# ').split()  # firstly remove the front and trailing '#' and whitespace, then split
            melib.me_dbg("Fields=%s" % fields)
            if "TASK-PID" not in fields:
                print("Error: trace log is missing TASK-PID field.")
                sys.exit(2)
            if "CPU#" not in fields:
                print("Error: trace log is missing CPU# field.")
                sys.exit(2)
            if "TIMESTAMP" not in fields:
                print("Error: trace log is missing TIMESTAMP field.")
                sys.exit(2)
            if "FUNCTION" not in fields:
                print("Error: trace log is missing FUNCTION field.")
                sys.exit(2)
            gFtrace_log_fields = fields
            return 1  # go to next line
    return 0


def create_default_property_dict():
    ret_dict = {}
    ret_dict[gmenu_PID] = None
    ret_dict[gmenu_lba] = None
    ret_dict[gmenu_op] = None
    ret_dict[gmenu_len] = None
    return ret_dict
