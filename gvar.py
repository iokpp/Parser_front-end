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
gDefault_graph_max_items is used to specify the maximum items 
which are showed in the histogram and scatter graph.
"""
gDefault_graph_start_from_item = 0
gDefault_graph_max_items = 4096
gDefault_histogram_threshold = 1024
gSCSI_LogicalBlockSize_Bytes = 4096
gLogicalSectorSize_Bytes = 512
gSectorsPerBlock = gSCSI_LogicalBlockSize_Bytes / gLogicalSectorSize_Bytes

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

''' events defined for the e2e'''
gReqEvent_start = 'Enter_VFS'
gReqEvent_end = 'Exit_VFS'

gWrite_Req = "write"
gRead_Req = "read"

# for the inputted ftrace file, must at least contain these
# fields in the log
gFtrace_log_fields = [] #"TASK-PID", "||||", "CPU", "TIMESTAMP", "FUNCTION"

gBlk_Events_Write_OP_list = ['WS', 'W', 'FWFS', 'WFS']
gBlk_Events_Read_OP_list = ['RS', 'R', 'R', 'RM', 'RA', 'RSM']

gEvents_dict =\
    {'vfs': ['sys_write',
             'sys_read'
             ],
     'ext4': ['ext4_direct_IO_enter',
              'ext4_direct_IO_exit',
              'ext4_sync_file_enter',
              'ext4_sync_file_exit',
              'ext4_da_write_begin',
              'ext4_da_write_end',
              'ext4_writepages',
              'ext4_writepages_result',
              'ext4_es_lookup_extent_enter',
              'ext4_es_lookup_extent_exit'
              ],
     'block': ['block_bio_remap',
               'block_bio_queue',
               'block_getrq',
               'block_plug',
               'block_unplug',
               'block_rq_insert',
               'block_rq_issue',
               'block_rq_complete'
               ],
     'scsi': ['scsi_dispatch_cmd_start',
              'scsi_dispatch_cmd_done'
              ],
     'dev': ['none'],
     'irq': ['irq_handler_entry',
             'irq_handler_exit'
             ]
     }

gFuns_dict =\
    {'vfs': ['none'
             ],
     'ext4': ['ext4_file_write_iter',
              '__generic_file_write_iter',
              'generic_perform_write',
              'generic_file_read_iter'
              ],
     'block': ['none'
               ],
     'scsi': ['scsi_queue_rq',
              'scsi_dma_map',
              'scsi_dma_unmap'
              ],
     'dev': ['ufshcd_intr'],
     'irq': ['none']
     }

gE2E_events_funcs_filter_dict = {
        'vfs': [
                'sys_write(fd:',
                'sys_write',
                'sys_read(fd:',
                'sys_read'
               ],
        'ext4': [
                 'ext4_file_write_iter',
                 'ext4_sync_file_enter',
                 'ext4_writepages',
                 'ext4_da_write_pages',
                 'ext4_sync_file_exit',
                 'ext4_writepages_result',
                 'generic_file_read_iter',
                 'ext4_direct_IO_enter',
                 'ext4_direct_IO_exit'
                ],
        'block': [
                 'block_bio_remap',
                 'block_bio_queue',
                 'block_getrq',
                 'block_plug',
                 'block_unplug',
                 'block_rq_insert',
                 'block_rq_issue',
                 'block_rq_complete',
                 ],
        'scsi': [
                 'scsi_dispatch_cmd_start',
                 'scsi_dispatch_cmd_done',
                ],
        'others': [

            ],
}
'''
gE2E_calculator_list = [
                'Exit_VFS',
                 # --------Ext4-----------
                 'ext4_file_write_iter',
                 'ext4_sync_file_enter',
                 'ext4_sync_file_exit',
                 'ext4_direct_IO_enter',
                 'generic_file_read_iter',
                 'ext4_direct_IO_enter',
                 'ext4_direct_IO_exit'
                 # --------Block--------------
                 'block_bio_remap',
                 'block_bio_queue',
                 'block_getrq',
                 'block_plug',
                 'block_unplug',
                 'block_rq_insert',
                 'block_rq_issue',
                 'block_rq_complete',
                 # ---------SCSI------------
                 'scsi_dispatch_cmd_start',
                 'scsi_dispatch_cmd_done'
]
'''
gE2E_calculator_list = [
                'Exit_VFS',
                 #----------block-----------
                 'block_rq_issue',
                 # ---------SCSI------------
                 'scsi_dispatch_cmd_start',
                 'scsi_dispatch_cmd_done',
                 'block_rq_complete',

]

gE2E_HW_transfer_e2e_flags = [
                'scsi_dispatch_cmd_start-scsi_dispatch_cmd_done'

]

gWA_HW_transfer_completion_flags = [
                'scsi_dispatch_cmd_done'
]


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
