#!/usr/bin/python
# # !/usr/bin/env python
#
# Copyright 2018 (C) Micron Semiconductor Corp.,
# This program is free software; you can redistribute and/or
# modify it under the terms of the GUN General Public License
# as published by the Free Software Foundation.
#
# 2018-Jun-1:Initial version by Bean Huo beanhuo@micron.com
#

import sys
import os
import re
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab
from matplotlib.backends.backend_pdf import PdfPages
import json
import pprint
from lib import melib
import gvar
import conf
from fs import vfs
from fs import ext4
from block import block
from scsi import scsi

sgIO_output_dir = ''

SCSI_BLOCK_SIZE_BYTE = gvar.gSCSI_LogicalBlockSize_Bytes
SECTOR_SIZE_BYTE = gvar.gLogicalSectorSize_Bytes

'''
sgOpened_tasks_in_device_list, contains the count of opened
task in the device along with the time. eg: [1,2,546,...]
'''
sgOpened_tasks_in_device_list = []
sgLBA_list = []

'''
sgRead_chunk_dict, contains the chunk list 
along the time. eg: {1: 4K.,2: 512....}
'''
sgRead_chunk_dict = {}
sgWrite_chunk_dict = {}

'''
sgAccessed_chunk_per_op_dict, contains the chunk list 
along the time. eg:  [1,1,2,546,...]
'''
sgAccessed_chunk_dist = []


'''
sgPtcl_raw_data is three-dimension nested dictionary.
in which, contains:
sgPtcl_raw_data[protocol][recode index][chunk] = 11332,
sgPtcl_raw_data[protocol][recode index][lba] = 11332,
sgPtcl_raw_data[protocol][recode index][I/O] = read/write,
sgPtcl_raw_data[protocol][recode index][event] = dispatch/done,
'''
sgPtcl_raw_data = melib.MultipleDimensionNestDict()


'''
sgBlk_IO_remap_info is two-dimension nested dictionary.
in which, contains:
sgBlk_IO_remap_info[index][chunk] = 11332,
sgBlk_IO_remap_info[index][lba] = 11332,
sgBlk_IO_remap_info[index][I/O] = Read/Write,
sgBlk_IO_remap_info[index][PID] = 342,
'''
sgBlk_IO_remap_info = melib.MultipleDimensionNestDict()
'''
sgBlk_LBA_list_per_pid/op_dict is three-dimension nested dictionary.
in which, contains:
sgBlk_LBA_list_per_pid/op_dict [pid/op][index][chunk] = 11332,
sgBlk_LBA_list_per_pid/op_dict [pid/op][index][lba] = 11332,
sgBlk_LBA_list_per_pid/op_dict [pid/op][index][op/pid] = op/pid,
'''
sgBlk_LBA_list_per_pid_dict = melib.MultipleDimensionNestDict()
sgBlk_LBA_list_per_op_dict = melib.MultipleDimensionNestDict()

temp_opened_task_before_close_one = []


def add_to_IO_property_tree(func_dict):
    global sgOpened_tasks_in_device_list
    global temp_opened_task_before_close_one

    op = func_dict.get(gvar.gmenu_op)
    bytes = func_dict.get(gvar.gmenu_len)
    lba = func_dict.get(gvar.gmenu_lba)
    event = func_dict.get(gvar.gmenu_events)
    pid = func_dict.get(gvar.gmenu_PID)

    # fill in the block layer LBA distribution data structure
    if event == 'block_bio_remap':
        remap_seq = 1
        lba_pid_index = 1
        lba_op_index = 1
        if sgBlk_IO_remap_info:
            remap_seq = list(sgBlk_IO_remap_info.keys())[-1]
            remap_seq = remap_seq + 1
        sgBlk_IO_remap_info[remap_seq][gvar.gmenu_len] = bytes
        sgBlk_IO_remap_info[remap_seq][gvar.gmenu_lba] = lba
        sgBlk_IO_remap_info[remap_seq][gvar.gmenu_op] = op
        sgBlk_IO_remap_info[remap_seq][gvar.gmenu_PID] = pid

        if op in sgBlk_LBA_list_per_op_dict.keys():
            lba_op_index = list(sgBlk_LBA_list_per_op_dict[op].keys())[-1]
            lba_op_index = lba_op_index + 1
        sgBlk_LBA_list_per_op_dict[op][lba_op_index][gvar.gmenu_len] = bytes
        sgBlk_LBA_list_per_op_dict[op][lba_op_index][gvar.gmenu_lba] = lba
        sgBlk_LBA_list_per_op_dict[op][lba_op_index][gvar.gmenu_PID] = pid

        if pid in sgBlk_LBA_list_per_pid_dict.keys():
            lba_pid_index = list(sgBlk_LBA_list_per_pid_dict[pid].keys())[-1]
            lba_pid_index = lba_pid_index + 1
        sgBlk_LBA_list_per_pid_dict[pid][lba_pid_index][gvar.gmenu_len] = bytes
        sgBlk_LBA_list_per_pid_dict[pid][lba_pid_index][gvar.gmenu_lba] = lba
        sgBlk_LBA_list_per_pid_dict[pid][lba_pid_index][gvar.gmenu_op] = op

    # fill in the opened task amount list
    if event in conf.gIO_event_trace_points['open']:
        sgLBA_list.append(lba)

        # Fill in the access chunk size list
        access_amount = len(sgLBA_list)
        if op == gvar.gWrite_Req:
            sgWrite_chunk_dict.setdefault(access_amount, bytes)
        elif op == gvar.gRead_Req:
            sgRead_chunk_dict.setdefault(access_amount, bytes)
        sgAccessed_chunk_dist.append(bytes)

        if temp_opened_task_before_close_one:
            pre_num = temp_opened_task_before_close_one[-1]
            pre_num += 1
            temp_opened_task_before_close_one.append(pre_num)
        else:
            if sgOpened_tasks_in_device_list:
                pre_num = sgOpened_tasks_in_device_list[-1]
                pre_num += 1
                temp_opened_task_before_close_one.append(pre_num)
            else:
                temp_opened_task_before_close_one.append(1)
    elif event in conf.gIO_event_trace_points['close']:
        if lba in sgLBA_list:
            # Note: in order to compatible with half-baked log.
            sgOpened_tasks_in_device_list = sgOpened_tasks_in_device_list + temp_opened_task_before_close_one
            temp_opened_task_before_close_one = []
            if sgOpened_tasks_in_device_list:
                pre_num = sgOpened_tasks_in_device_list[-1]
                pre_num -= 1
                sgOpened_tasks_in_device_list.append(pre_num)
    '''
    # fill in the protocol layer infor data structure
    if func_dict[gvar.gmenu_events] in conf.gPtcl_trace_points[gvar.gProtocol_mode]:
        index = 1
        if sgPtcl_raw_data:
            index = list(sgPtcl_raw_data[gvar.gProtocol_mode].keys())[-1]
            index = index + 1
        sgPtcl_raw_data[gvar.gProtocol_mode][index][gvar.gmenu_len] = bytes
        sgPtcl_raw_data[gvar.gProtocol_mode][index][gvar.gmenu_lba] = lba
        sgPtcl_raw_data[gvar.gProtocol_mode][index][gvar.gmenu_op] = op
        sgPtcl_raw_data[gvar.gProtocol_mode][index][gvar.gmenu_events] = event
    '''


def checkup_lba_continuous(infor_dict):
    record_index = 1
    max_record = max(infor_dict.keys())
    ret_list = []
    while record_index < max_record:
        lba = infor_dict[record_index][gvar.gmenu_lba]
        data_len = infor_dict[record_index][gvar.gmenu_len] / \
                   gvar.gLogicalSectorSize_Bytes  # convert byte length to sector length

        next_lba = infor_dict[record_index + 1][gvar.gmenu_lba]

        if int(lba) + data_len == int(next_lba):
            ret_list.append(1)
        else:
            ret_list.append(0)
        record_index += 1
    return ret_list


def lba_continuity_analyzer():
    lba_succession_trend_list = []
    lba_succession_trend_per_pid = {}
    lba_succession_trend_per_op = {}

    lba_succession_trend_list = checkup_lba_continuous(sgBlk_IO_remap_info)
    for pid in sgBlk_LBA_list_per_pid_dict.keys():
        lba_succession_trend_per_pid.setdefault(pid, checkup_lba_continuous(sgBlk_LBA_list_per_pid_dict[pid]))
    for op in sgBlk_LBA_list_per_op_dict.keys():
        lba_succession_trend_per_op.setdefault(op, checkup_lba_continuous(sgBlk_LBA_list_per_op_dict[op]))

    #melib.me_pprint_dict_scream(lba_succession_trend_per_pid)
    #melib.me_pprint_dict_scream(lba_succession_trend_per_op)
    #print(lba_succession_trend_list)


def display_one_chart_on_pdf(pdf_file, data_list, title, x_name, y_name):
    if not isinstance(data_list, list):
        melib.me_error("The inputted source data is not a list, so failed to create chart.")

    ln = len(data_list)
    if ln > gvar.gDefault_graph_window_end_at_item:
        x = range(1, gvar.gDefault_graph_window_end_at_item + 1)
        y = data_list[gvar.gDefault_graph_window_start_from_item:
                                         gvar.gDefault_graph_window_end_at_item]
    else:
        x = range(1, ln + 1)
        y = data_list

    plt.figure()
    plt.axis([0, len(x), 0, max(y) + 1])
    plt.ylabel(y_name, fontsize=10)
    plt.xlabel(x_name, fontsize=10)
    plt.title(title)
    plt.plot(x, y, color='r', linewidth=1.0,  linestyle='--', label='opened task amount')
    plt.grid(False)
    plt.legend(fontsize=5)
    pdf_file.savefig()
    plt.close()



def io_main(original_lines, opts):

    global sgIO_output_dir
    sgIO_output_dir = gvar.gOutput_Dir_Default + '/io-stat/'
    melib.mkdir(sgIO_output_dir)

    # LBA succession
    if sgBlk_IO_remap_info:
        melib.me_pprint_dict_file(sgIO_output_dir + '00-Blk-io-remap-Raw-Data.log',
                                  sgBlk_IO_remap_info)
        if sgLBA_list:
            melib.me_pprint_dict_file(sgIO_output_dir + '01-Accessed-LBA-List.log',
                                      sgLBA_list)
        #lba_continuity_analyzer()

    # Opened task count
    if sgOpened_tasks_in_device_list:
        melib.me_pprint_dict_file(sgIO_output_dir + '02-Opened_tasks_in_device_list.log',
                                  sgOpened_tasks_in_device_list)
        try:
            pdf = PdfPages(sgIO_output_dir + str(gvar.gDefault_graph_window_start_from_item) + '-' +
                           str(gvar.gDefault_graph_window_end_at_item) + '-Opened_tasks_in_device_chart.pdf')
            display_one_chart_on_pdf(pdf, sgOpened_tasks_in_device_list, 'Opened_tasks_in_device', 'T', 'Amount')
            pdf.close()
        except:
            melib.me_error("Create pdf failed for the Opened_tasks_in_device_chart.")
            #return

    # Access chunk size
    if sgAccessed_chunk_dist:
        melib.me_pprint_dict_file(sgIO_output_dir + '03-Accessed_chunk_op-independent_list_.log',
                                  sgAccessed_chunk_dist)
        if sgRead_chunk_dict:
            melib.me_pprint_dict_file(sgIO_output_dir + '03-Read_chunk_list.log',
                                      sgRead_chunk_dict)
        if sgWrite_chunk_dict:
            melib.me_pprint_dict_file(sgIO_output_dir + '03-Write_chunk_list_.log',
                                      sgWrite_chunk_dict)



    '''   
    if sgPtcl_raw_data:
        melib.me_pprint_dict_file(sgIO_output_dir + '00-protocol-' + gvar.gProtocol_mode + '-Raw-Data.log',
                                  sgPtcl_raw_data)
        # melib.me_pprint_dict_scream(sgE2E_Duration_DataBank)
        # melib.me_pickle_save_obj("./01-pickle-sgE2E_Duration_DataBank.log",
        #                         sgE2E_Duration_DataBank)
    '''