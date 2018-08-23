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

line_no = 0  # the line number which is now analyzed on.

SCSI_BLOCK_SIZE_BYTE = gvar.gSCSI_LogicalBlockSize_Bytes
SECTOR_SIZE_BYTE = gvar.gLogicalSectorSize_Bytes

'''
The PID list, contains all the PID numbers that appear in
the log file. such as: ['pid a', 'pid b', ...]
'''
sgPID_list = []


'''
sgItems_counter_per_E2E is three-dimension nested dictionary.
in which, contains the quantity of request associated with certain
PID, operation and chunk size.
eg: sgItems_counter_per_E2E[pid][op][e2e_name][chunk] = 11332,
'''
sgItems_counter_per_E2E = melib.MultipleDimensionNestDict()


'''
sgLBA_list_of_PID_OP_chunk is a dictionary, in which contains the LAB
that associated with specific pid and operation.
eg:
{(pid, op, chunk):
    ['2314', '4587e',...], 
...
}
'''
sgLBA_list_of_PID_OP_chunk = dict()

''' {(pid, op, e2e_name, chunk, LAB): item_number}'''
sgIndex_of_LBA_in_DB = dict()

'''
sgBIO_Remap_info_DataBank is a multiple dimension nested dictionary.
{ 'pid a' : --------first level branch, indicates the pid number
    {'write/read': ----- second level branch, indicates the operation
        { Chunk: --------- third level branch, indicates the chunk size
            { seq: --------- fifth level branch, indicates the sequence number of this req
                {
                lpd: ddd, 
                len: 1313,
                time: 1234234.4
                },
                  
            }
        }
    }   
}
eg. 
[pid][op][chunk][seq]={lba: "ddd", len: "ddd"}
'''
sgBIO_Remap_info_DataBank = melib.MultipleDimensionNestDict()

'''
event property dictionary grouped by event, its topology, eg:
{'pid a':  ----> first level branch, indicates the PID associated with this item 
    { write/read: ----> chunk size
        {'e2e name':  ----> indicates this is a write or read
            {'chunk size':  ----> indicates the e2e name in the user configure list
                { seq 1: ----> indicates the sequence number of this pair e2e
                    { 0:
                        {'timestamp':'233424.4343', 'LBA':'ddd'/None },
                       1:
                        {'timestamp':'233424.4343', 'LBA':'ddd'/None}
                    },
                },
             ...
            },  
        ...
        },
     ...
    },
 ...
}
usage:
sgEvent_Property_DataBank_groupbyevent[pid][op][e2e_name][chunk][seq n][0/1][timestamp] = 4546565.545
sgEvent_Property_DataBank_groupbyevent[pid][op][e2e_name][chunk][seq n][0/1][LBA] = '12121'
'''
sgEvent_Property_DataBank_groupbyevent = melib.MultipleDimensionNestDict()

# [pid][op][chunk][req_seq][e2e_seq][e2e_name]=duration
sgE2E_Duration_DataBank = melib.MultipleDimensionNestDict()

'''
sgCurrent_info is the dictionary, in which contains the current
analyzing information of request that associated with specific PID.
eg:
[pid][len]=sss
[pid][op]=sss
[pid][req_lba]=sss
[pid][pre_event]=ss
'''
sgCurrent_info = melib.MultipleDimensionNestDict()

'''
sgE2E_e2e_distribution_by_pid_dic is one dimension dictionary,
its key is tuple which consists of (pid, op, len, e2e_seq, e2e_name)
its value is the list which contains the duration of e2e. [0.121, 0.254,...].
the items are split by PID/op/len
'''
sgE2E_e2e_distribution_by_pid_dic = {}

'''
sgE2E_e2e_distribution_by_chunk_dic is the similar with
above sgE2E_e2e_distribution_by_pid_dic, but it is split by op/len.

(op,len, e2e_seq, e2e_name):[a,b,c,......]
'''
sgE2E_e2e_distribution_by_chunk_dic = {}


'''
(op,len, e2e_name):[a,b,c,......]
'''
sgE2E_sw_distribution_dict = {}

'''
(op,len, e2e_name):[a,b,c,......]
'''
sgE2E_hw_distribution_dict = {}


class StatusClass:
    def __init__(self):
        self.theoretical_performance = {} #[(write/read, len)] = MB/s
        self.threadcounts = 0 # how many threads are there in this log?


sgE2E_Analyzer_Stat = StatusClass()


def update_current_pid_info_dict(pid, chunk, op, req_seq, event_seq, event, lba):
    if chunk is not None:
        sgCurrent_info[pid][gvar.gmenu_len] = chunk
    if op is not None:
        sgCurrent_info[pid][gvar.gmenu_op] = op
    if req_seq is not None:
        sgCurrent_info[pid][gvar.gmenu_req_seq] = req_seq
    if event_seq is not None:
        sgCurrent_info[pid][gvar.gmenu_event_seq] = event_seq
    if event is not None:
        sgCurrent_info[pid][gvar.gmenu_pre_event] = event
    if lba is not None:
        sgCurrent_info[pid][gvar.gmenu_lba] = lba

    if event == gvar.gReqEvent_start:
        ''' If this is the first event of request, we simply set
        its lba as 0, it will be changed when hits remap event.'''
        sgCurrent_info[pid][gvar.gmenu_lba] = '0'


def adjust_pid_by_lba_op(pid, lba, op):
    line_no = gvar.gCurr_line
    match_num = 0
    match_pids = []
    ret_pid = None

    for (temp_pid, temp_op, temp_chunk) in sgLBA_list_of_PID_OP_chunk.keys():
        if lba in sgLBA_list_of_PID_OP_chunk[(temp_pid, temp_op, temp_chunk)]:
            if temp_op == op:
                match_num = match_num + 1
                match_pids.append(temp_pid)
                ret_pid = temp_pid
            else:
                melib.me_dbg("Operation type un-match! current %s, temp %s" %
                             (op, temp_op))

    if match_num == 0:
        '''There are some internal triggered requests, don't have VFS events.
            Currently, we temporarily return.
        '''
        # FIXME
        melib.me_warning("Line %d, PID %s, 0 match PID" %(line_no, pid))
        return None

    if match_num > 1:
        # FIXME
        melib.me_warning("Line %d " % line_no)
        melib.me_warning("---match %d times, %s using pid %s " % (match_num, match_pids, ret_pid))

    return ret_pid

'''
def is_event_exist_in_request_databank(pid, op, vfs_len, seq, event_str):
    if sgEvent_Property_DataBank_groupbyevent[pid][op][e][]
    for i in sgEvent_Property_DataBank_groupbyevent[pid][op][vfs_len][seq].keys():
        if event_str in sgEvent_Property_DataBank_groupbyevent[pid][op][vfs_len][seq][i].keys():
            return True
    return False
'''


def add_subtrahend_to_db(event_info_dict, e2e_name, record_index):
    pid = event_info_dict[gvar.gmenu_PID]
    op = event_info_dict[gvar.gmenu_op]
    chunk = event_info_dict[gvar.gmenu_len]
    event = event_info_dict[gvar.gmenu_events]
    timestamp = event_info_dict[gvar.gmenu_time]
    lba = event_info_dict[gvar.gmenu_lba]
    lines = gvar.gCurr_line

    if sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][record_index].get(0) is not None:
        melib.me_warning("Failed to add subtrahend, Line %d, since %s already exists in data bank. e2e %s,"
                         "recode index %s." % (lines, event, e2e_name, record_index))
    else:
        sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][record_index][0][gvar.gmenu_time] = timestamp
        sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][record_index][0][gvar.gmenu_lba] = lba

    sgIndex_of_LBA_in_DB[(pid, op, chunk, e2e_name, lba)] = record_index


def add_minuend_to_db(event_info_dict, e2e_name, item_seq):
    pid = event_info_dict[gvar.gmenu_PID]
    op = event_info_dict[gvar.gmenu_op]
    chunk = event_info_dict[gvar.gmenu_len]
    event = event_info_dict[gvar.gmenu_events]
    timestamp = event_info_dict[gvar.gmenu_time]
    lba = event_info_dict[gvar.gmenu_lba]
    lines = gvar.gCurr_line

    if sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][item_seq].get(1):
        melib.me_warning("Failed to add minuend, Line %d, since %s already exists in data bank. e2e %s"
                         " recode index %d." %
                         (lines, event, e2e_name, item_seq))

    else:
        sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][item_seq][1][gvar.gmenu_time] = timestamp
        sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][item_seq][1][gvar.gmenu_lba] = lba


def add_new_branch_into_tree(event_info_dict, e2e_match_dict):

    pid = event_info_dict[gvar.gmenu_PID]
    op = event_info_dict[gvar.gmenu_op]
    chunk = event_info_dict[gvar.gmenu_len]

    sgPID_list.append(pid)  # add this pid into pid list

    for i in e2e_match_dict.keys():
        # This is the first req associated with PID/op/e2e/chunk
        e2e_name = conf.gE2E_durations_trace[i]  # get the e2e name by its index
        item_seq = sgItems_counter_per_E2E[pid][op][chunk][e2e_name] = 1 # this is the first item of e2e recode.
        seq = e2e_match_dict[i]  # get its event index, 0/1
        if seq == 0:
            # here only adds first event, because so far it doesn't exist other event in this pid recode.
            add_subtrahend_to_db(event_info_dict, e2e_name, item_seq)
        #elif seq == 1:
        #   add_minuend_to_db(event_info_dict, e2e_name, item_seq)


def add_new_event_into_tree(property_dict, match_dict):
    pid = property_dict[gvar.gmenu_PID]
    chunk = property_dict[gvar.gmenu_len]
    op = property_dict[gvar.gmenu_op]
    lba = property_dict[gvar.gmenu_lba]

    for e2e_seq in match_dict.keys():
        e2e_name = conf.gE2E_durations_trace[e2e_seq]
        if chunk not in sgEvent_Property_DataBank_groupbyevent[pid][op].keys():
            add_new_branch_into_tree(property_dict, match_dict)
        elif e2e_name not in sgEvent_Property_DataBank_groupbyevent[pid][op][chunk].keys():
            add_new_branch_into_tree(property_dict, match_dict)
        else:
            subtra_or_minuend = match_dict[e2e_seq]
            if subtra_or_minuend == 0:
                sgItems_counter_per_E2E[pid][op][chunk][e2e_name] += 1
                record_index = sgItems_counter_per_E2E[pid][op][chunk][e2e_name]
                add_subtrahend_to_db(property_dict, e2e_name, record_index)
            elif subtra_or_minuend == 1:
                record_index = sgIndex_of_LBA_in_DB.get((pid, op, chunk, e2e_name, lba))
                if record_index is not None:
                    add_minuend_to_db(property_dict, e2e_name, record_index)
                else:
                    found_count = 0
                    first_found_record_index = None
                    last_found_record_index = None

                    if lba is None:
                        for lba_temp in sgLBA_list_of_PID_OP_chunk[(pid, op, chunk)]:
                            found_index = sgIndex_of_LBA_in_DB.get((pid, op, chunk, e2e_name, lba_temp))
                            if found_index is not None:
                                if sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][found_index].get(1) is None:
                                    if found_count == 0:
                                        first_found_record_index = found_index
                                    last_found_record_index = found_index
                                    found_count += 1

                        if found_count > 1:
                            melib.me_warning("Line %d, there are  %d relevant subtrahend items found for e2e %s."
                                           % (gvar.gCurr_line, found_count, e2e_name))

                    elif lba is not None:
                        first_found_record_index = sgIndex_of_LBA_in_DB.get((pid, op, chunk, e2e_name, None))

                    record_index = first_found_record_index  # use the first one we found FIXME

                    if record_index is None:
                        melib.me_error("Line %d cannot find its relevant subtrahend item for e2e %s." %
                                       (gvar.gCurr_line, e2e_name))
                    else:
                        add_minuend_to_db(property_dict, e2e_name, record_index)


def figure_out_e2e_match_dict(event_name):
    match_dic = {}
    for e2e in conf.gE2E_durations_trace:
        if event_name == e2e.split('-')[0]:
            match_dic[conf.gE2E_durations_trace.index(e2e)] = 0
        elif event_name == e2e.split('-')[1]:
            match_dic[conf.gE2E_durations_trace.index(e2e)] = 1
    return match_dic


def add_to_event_property_tree(property_dict):

    """
    Fill in the data bank according to property_dict, in which contains
    the event information by the form of dictionary.
    :param property_dict:
    :return: None
    """

    pid = property_dict[gvar.gmenu_PID]
    event = property_dict[gvar.gmenu_events]

    if gvar.gmenu_len in property_dict.keys() and property_dict[gvar.gmenu_len] is not None:
        ''' there is data length field in this event dictionary '''
        len_bytes = property_dict[gvar.gmenu_len]
    else:
        len_bytes = None
    if gvar.gmenu_op in property_dict.keys() and property_dict[gvar.gmenu_op] is not None:
        ''' there is operational type field in this event dictionary '''
        op = property_dict[gvar.gmenu_op]
    else:
        op = None
    # ---------------- change start --------------
    lba = property_dict.get(gvar.gmenu_lba)  # try to get its LBA
    if lba is not None:
        if event == 'block_bio_remap':
            sgLBA_list_of_PID_OP_chunk.setdefault((pid, op, len_bytes), []).append(lba)
            melib.me_dbg("Event: %s, sgLBA_list_of_PID_OP_chunk: %s !" %
                         (event, sgLBA_list_of_PID_OP_chunk))

        else:
            if (not sgLBA_list_of_PID_OP_chunk.get((pid, op, len_bytes))) or\
                    (lba not in sgLBA_list_of_PID_OP_chunk[(pid, op, len_bytes)]):
                adjust_pid = adjust_pid_by_lba_op(pid, lba, op)
                if adjust_pid is not None:
                    property_dict[gvar.gmenu_PID] = adjust_pid
                    pid = adjust_pid

    match_dict = figure_out_e2e_match_dict(event)
    ''' match_dict: {e2e index in the gE2E_durations_trace: 0/1}
    0--the first event, 1--the second event.'''
    if match_dict:
        '''
        if (lba is not None) and
                (lba not in sgLBA_list_of_PID_OP_chunk[(pid, op, len_bytes)]):
            adjust_pid = adjust_pid_by_lba_op(pid, lba, op)
            if adjust_pid is not None:
                property_dict[gvar.gmenu_PID] = adjust_pid
        '''
        if pid not in sgEvent_Property_DataBank_groupbyevent.keys():
            ''' This PID first time appears, create a new pid branch. '''
            add_new_branch_into_tree(property_dict, match_dict)
        elif pid in sgEvent_Property_DataBank_groupbyevent.keys():
            ''' This PID has been existing in the data bank. '''
            if op not in sgEvent_Property_DataBank_groupbyevent[pid].keys():
                add_new_branch_into_tree(property_dict, match_dict)
            else:
                add_new_event_into_tree(property_dict, match_dict)


def add_one_duration(pid, op, chunk,  e2e_name,index, duration):
        sgE2E_Duration_DataBank[pid][op][chunk][e2e_name][index] = duration


def e2e_interval_calculator(pid, op, chunk, e2e_name, index):
    pre_event = {}
    curr_event = {}
    duration_seq = 0
    one_e2e_recode_dict = sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name][index]
    minuend = one_e2e_recode_dict.get(1)
    subtrahend = one_e2e_recode_dict.get(0)

    if minuend and subtrahend:
        if minuend[gvar.gmenu_time] < subtrahend[gvar.gmenu_time]:
            melib.me_warning("{ %s: %s: %s: %d: %d } minuend time is smaller than subtrahend. fail to calculate." %
                             (pid, op, e2e_name, chunk, index))
        else:
            duration = round(float(minuend[gvar.gmenu_time]) - float(subtrahend[gvar.gmenu_time]), 6)
            add_one_duration(pid, op, chunk,  e2e_name, index, duration)
    else:
        melib.me_warning("{ %s: %s: %s: %d: %d } misses event. fail to calculate."%
                         (pid, op, e2e_name, chunk, index))
    return


def e2e_duration_calculator():
    """
    According to sgEvent_Property_DataBank_groupbyevent, analyze and
    calculate the e2e duration. finally fill in
    sgE2E_Duration_DataBank.
    :return:
    """
    for pid in sgEvent_Property_DataBank_groupbyevent.keys():
        for op in sgEvent_Property_DataBank_groupbyevent[pid].keys():
            for chunk in sgEvent_Property_DataBank_groupbyevent[pid][op].keys():
                for e2e_name in sgEvent_Property_DataBank_groupbyevent[pid][op][chunk].keys():
                    seqs = sorted(sgEvent_Property_DataBank_groupbyevent[pid][op][chunk][e2e_name].keys())
                    for i in seqs:
                        e2e_interval_calculator(pid, op, chunk,  e2e_name,i)
    return


def e2e_databank_resolver():

    for pid in sgE2E_Duration_DataBank.keys():
        for op in sgE2E_Duration_DataBank[pid].keys():
            for chunk in sgE2E_Duration_DataBank[pid][op].keys():
                for e2e_name in sgE2E_Duration_DataBank[pid][op][chunk].keys():

                    seq = conf.gE2E_durations_trace.index(e2e_name)

                    duration_list = \
                        list(sgE2E_Duration_DataBank[pid][op][chunk][e2e_name].values())

                    sgE2E_e2e_distribution_by_pid_dic[(pid, op, chunk, seq, e2e_name)] = duration_list

                    if (pid, op, chunk, seq, e2e_name) not in sgE2E_e2e_distribution_by_chunk_dic.keys():
                        sgE2E_e2e_distribution_by_chunk_dic[(op, chunk, seq, e2e_name)] = duration_list
                    else:
                        sgE2E_e2e_distribution_by_chunk_dic[(op, chunk, seq, e2e_name)].extend(duration_list)
    return


def e2e_histogram_pdf_show_by_pid():
    src_dict = sgE2E_e2e_distribution_by_pid_dic
    histogram_threshold = 200
    pid_op_len_seq_event_tuple_list = sorted(src_dict.keys())

    try:
        hist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_histogram_by_pid-groupbyevnt.pdf")
    except:
        melib.me_warning("Create hist_pdf file failed.")
        return
    for (pid, op, len_bytes, e2e_seq, e2e_event) in pid_op_len_seq_event_tuple_list:

        ln = len(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])

        if ln > histogram_threshold:
            list_data = src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)]

            if ln > gvar.gDefault_graph_max_items:
                x = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                                 gvar.gDefault_graph_max_items]]
                normed_x = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                                        gvar.gDefault_graph_max_items]]
                ln = gvar.gDefault_graph_max_items
            else:
                x = [i * 1000 for i in list_data]
                normed_x = [i * 1000 for i in list_data]

            plt.figure()
            p1 = plt.subplot(211)  # first row
            p2 = plt.subplot(212)  # second row

            #(n, bins, patches) =\
            p1.hist(x, ln, normed=False,
                    edgecolor='None', facecolor='red', alpha=0.75, label=e2e_event)
            (n, bins, patches) = p2.hist(normed_x, bins=np.arange(min(normed_x), max(normed_x), np.mean(normed_x)/10),
                                         normed=True, cumulative=True, edgecolor='None', facecolor='green', alpha=0.75)

            p1.set_ylabel('Items', fontsize=10)
            p1.set_xlabel('Duration (ms)', fontsize=10)

            p2.set_ylabel('Possibility', fontsize=10)
            p2.set_xlabel('Duration (ms)', fontsize=10)

            title = pid + '/' + op + '/' + str(len_bytes)  #'/' + e2e_event

            p1.set_title(title)
            #plt.text(0, 0.5,r'text test')
            p1.grid(True)

            p1.legend(fontsize=10, loc='best')

            #p1.subplots_adjust(left=0.15)
            plt.tight_layout()
            hist_pdf.savefig()
            plt.close()
    hist_pdf.close()


def e2e_scattergram_pdf_show_by_pid():

    src_dict = sgE2E_e2e_distribution_by_pid_dic
    pre_pid = ''
    curr_pid = ''
    pre_len_bytes = 0
    curr_len_bytes = 0

    pre_op = ''

    axis_x = 0
    axis_y = 0
    label_line = ['r.', 'b.', 'y.', 'g.', 'm.', 'c:', 'r-', 'b-', 'y-', 'g-', 'm--', 'c--']
    pid_op_len_seq_event_tuple_list = sorted(src_dict.keys())
    try:
        dist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_scattergram_by_pid-groupbyevent.pdf")
    except:
        melib.me_warning("Create dist_pdf file failed.")
        return

    for (pid, op, len_bytes, e2e_seq, e2e_event) in pid_op_len_seq_event_tuple_list:
        curr_e2e_event = e2e_event
        if curr_pid is not pid or curr_len_bytes != len_bytes:
            curr_pid = pid

            if pre_pid is '':
                plt.figure()
            else:
                plt.axis([0, axis_x, 0, axis_y + 1])
                plt.ylabel('Millisecond', fontsize=10)
                plt.xlabel('T', fontsize=10)
                title = pre_pid + '/' + pre_op + '/' + str(pre_len_bytes) + ' Bytes'
                plt.title(title)
                plt.grid(False)
                plt.legend(fontsize=5)
                dist_pdf.savefig()
                plt.close()
                axis_y = axis_x = 0
                plt.figure()

            pre_pid = curr_pid
            curr_e2e_event = e2e_event
            curr_len_bytes = pre_len_bytes = len_bytes
            pre_op = op

        first_event = curr_e2e_event.split('-')[0]
        second_event = curr_e2e_event.split('-')[-1]
        ln = len(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mx = max(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mn = min(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mean = round(np.mean(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)]), 6)

        list_data = src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)]
        if ln > gvar.gDefault_graph_max_items:
            x = range(1, gvar.gDefault_graph_max_items + 1)
            y = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                             gvar.gDefault_graph_max_items]]
        else:
            x = range(1, ln+1)
            y = [i * 1000 for i in list_data]

        if axis_x < len(x):
            axis_x = len(x)
        if axis_y < max(y):
            axis_y = max(y)

        color = 'g-'
        if e2e_seq >= len(label_line):
            melib.me_warning("The event case over %d. no more color can apply to." % len(label_line))
            color = 'g-'
        else:
            color = label_line[e2e_seq]

        plt.plot(x, y, color, linewidth=1.0, label=str(e2e_seq) + e2e_event)

    plt.axis([0, axis_x, 0, axis_y + 1])
    plt.grid(False)
    plt.legend(fontsize=5)
    plt.ylabel('Millisecond',  fontsize=10)
    plt.xlabel('T',  fontsize=10)
    title = pre_pid + '/' + pre_op + '/' + str(pre_len_bytes) + ' ' + 'Bytes'
    plt.title(title)
    dist_pdf.savefig()
    plt.close()
    dist_pdf.close()


def e2e_histogram_pdf_show_by_op_len():
    """

    :return:
    """
    src_dict = sgE2E_e2e_distribution_by_chunk_dic
    histogram_threshold = gvar.gDefault_histogram_threshold
    op_len_seq_event_tuple_list = sorted(src_dict.keys())

    try:
        hist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_histogram_by_op_len.pdf")
    except:
        melib.me_warning("Create sgE2E_histogram_by_op_len file failed.")
        return
    for (op, len_bytes, e2e_seq, e2e_event) in op_len_seq_event_tuple_list:

        ln = len(src_dict[(op, len_bytes, e2e_seq, e2e_event)])

        if ln > histogram_threshold:
            list_data = src_dict[(op, len_bytes, e2e_seq, e2e_event)]

            if ln > gvar.gDefault_graph_max_items:
                x = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                                 gvar.gDefault_graph_max_items]]
                normed_x = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                                        gvar.gDefault_graph_max_items]]
                ln = gvar.gDefault_graph_max_items
            else:
                x = [i * 1000 for i in list_data]
                normed_x = [i * 1000 for i in list_data]

            plt.figure()
            p1 = plt.subplot(211)  # first row
            p2 = plt.subplot(212)  # second row

            #(n, bins, patches) =\
            p1.hist(x, ln, normed=False,
                    edgecolor='None', facecolor='red', alpha=0.75, label=e2e_event)

            (n, bins, patches) = p2.hist(normed_x, bins=np.arange(min(normed_x), max(normed_x), np.mean(normed_x)/10),
                                         normed=True, cumulative=True, edgecolor='None', facecolor='green', alpha=0.75)


            p1.set_ylabel('Items', fontsize=10)
            p1.set_xlabel('Duration (ms)', fontsize=10)

            p2.set_ylabel('Possibility', fontsize=10)
            p2.set_xlabel('Duration (ms)', fontsize=10)

            title = op + '/' + str(len_bytes)  #'/' + e2e_event

            p1.set_title(title)
            #plt.text(0, 0.5,r'text test')
            p1.grid(True)

            p1.legend(fontsize=10, loc='best')

            #p1.subplots_adjust(left=0.15)
            plt.tick_params(top='off', right='off')
            plt.tight_layout()
            hist_pdf.savefig()
            plt.close()
    hist_pdf.close()


def e2e_scattergram_pdf_show_by_op_len():

    src_dict = sgE2E_e2e_distribution_by_chunk_dic
    pre_pid = ''
    curr_pid = ''
    pdf_ok = True
    pre_len_bytes = 0
    curr_len_bytes = 0
    pre_e2e_seq = 0
    curr_e2e_seq = 0
    pre_e2e_event = ''
    curr_e2e_event = ''
    pre_op = ''
    curr_op = ''
    axis_x = 0
    axis_y = 0
    label_line = ['r.', 'b.', 'y.', 'g.', 'm.', 'c:', 'r-', 'b-', 'y-', 'g-', 'm--', 'c--']
    op_len_seq_event_tuple_list = sorted(src_dict.keys())
    try:
        dist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_scattergram_by_op_len.pdf")
    except:
        melib.me_warning("Create sgE2E_scattergram_by_op_len file failed.")
        return

    for (op, len_bytes, e2e_seq, e2e_event) in op_len_seq_event_tuple_list:
        curr_e2e_event = e2e_event
        if curr_op is not op or curr_len_bytes != len_bytes:
            curr_op = op

            if pre_op is '':
                plt.figure()
            else:
                plt.axis([0, axis_x, 0, axis_y + 1])
                plt.ylabel('Millisecond', fontsize=10)
                plt.xlabel('T', fontsize=10)
                title = pre_op + '/' + str(pre_len_bytes) + ' Bytes'
                plt.title(title)
                plt.grid(False)
                plt.legend(fontsize=5)
                dist_pdf.savefig()
                plt.close()
                axis_y = axis_x = 0
                plt.figure()

            curr_e2e_event = pre_e2e_event = e2e_event
            curr_e2e_seq = pre_e2e_seq = e2e_seq
            curr_len_bytes = pre_len_bytes = len_bytes
            curr_op = pre_op = op

        first_event = curr_e2e_event.split('-')[0]
        second_event = curr_e2e_event.split('-')[-1]
        ln = len(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mx = max(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mn = min(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mean = round(np.mean(src_dict[(op, len_bytes, e2e_seq, e2e_event)]), 6)

        list_data = src_dict[(op, len_bytes, e2e_seq, e2e_event)]

        if ln > gvar.gDefault_graph_max_items:
            x = range(1, gvar.gDefault_graph_max_items + 1)
            y = [i * 1000 for i in list_data[gvar.gDefault_graph_start_from_item:
                                             gvar.gDefault_graph_max_items]]
        else:
            x = range(1, ln+1)
            y = [i * 1000 for i in list_data]

        if axis_x < len(x):
            axis_x = len(x)
        if axis_y < max(y):
            axis_y = max(y)

        color = 'g-'
        if e2e_seq >= len(label_line):
            melib.me_warning("The event case over %d. no more color can apply to." % len(label_line))
            color = 'g-'
        else:
            color = label_line[e2e_seq]

        plt.plot(x, y, color, linewidth=1.0, label=str(e2e_seq) + e2e_event)

    plt.axis([0, axis_x, 0, axis_y + 1])
    plt.grid(False)
    plt.legend(fontsize=5)
    plt.ylabel('Millisecond',  fontsize=10)
    plt.xlabel('T',  fontsize=10)
    title = pre_op + '/' + str(pre_len_bytes) + ' ' + 'Bytes'
    plt.title(title)
    dist_pdf.savefig()
    plt.close()
    dist_pdf.close()


def e2e_stat_analyzer_by_pid():

    src_dict = sgE2E_e2e_distribution_by_pid_dic

    curr_pid = ''
    pdf_ok = True
    curr_op = ''
    curr_len_bytes = 0
    curr_e2e_seq = 0
    curr_e2e_event = ''

    pid_op_len_seq_event_tuple_list = sorted(src_dict.keys())

    fd = open(gvar.gOutput_Dir_Default+"Report_by_pid-groupbyevent.log", 'w')
    bak_stdout = sys.stdout
    sys.stdout = fd
    for (pid, op, chunk, seq, e2e_name) in pid_op_len_seq_event_tuple_list:
        curr_e2e_event = e2e_name
        if curr_pid is not pid or curr_len_bytes != chunk:
            curr_pid = pid
            curr_len_bytes = chunk
            print("          ")
            print("  -----------------------------------------------------------")
            print("  Task-PID: %s. Chunk Size : %s bytes[%s]" % (pid, chunk, op))
        first_event = curr_e2e_event.split('-')[0]
        second_event = curr_e2e_event.split('-')[-1]
        ln = len(src_dict[(pid, op, chunk, seq, e2e_name)])
        mx = max(src_dict[(pid, op, chunk, seq, e2e_name)])
        mn = min(src_dict[(pid, op, chunk, seq, e2e_name)])
        mean = round(np.mean(src_dict[(pid, op, chunk, seq, e2e_name)]), 6)
        median = round(np.median(src_dict[(pid, op, chunk, seq, e2e_name)]), 6)
        print("    %d: %s<---->%s" % (seq, first_event, second_event))
        print("          |--%d cases"% ln)
        print("          |--Mean:[%f s], Median:[%f s], Max:[%f s], Min:[%f s]" % (mean, median, mx, mn))
        if first_event == gvar.gReqEvent_start and second_event == gvar.gReqEvent_end:
            print("          |-- I/O speed:[%0.3f MB/s (mean)], [%0.3f MB/s (median)]" %
                    (
                        round((1/float(mean) * float(chunk))/1024/1024, 3),
                        round((1/float(median) * float(chunk)) / 1024 / 1024, 3)
                    )
                  )
    sys.stdout = bak_stdout
    fd.close()


def e2e_stat_analyzer_by_op_len():

    src_dict = sgE2E_e2e_distribution_by_chunk_dic
    curr_op = ''
    curr_len_bytes = 0
    curr_e2e_seq = 0
    curr_e2e_event = ''

    op_len_seq_event_tuple_list = sorted(src_dict.keys())

    fd = open(gvar.gOutput_Dir_Default+"Report_by_op_len.log", 'w')
    bak_stdout = sys.stdout
    sys.stdout = fd
    for (op, len_bytes, e2e_seq, e2e_event) in op_len_seq_event_tuple_list:
        curr_e2e_event = e2e_event
        if curr_op is not op or curr_len_bytes != len_bytes:
            curr_op = op
            curr_len_bytes = len_bytes
            print("          ")
            print("  -----------------------------------------------------------")
            print("  Chunk Size : %s bytes[%s]" % (len_bytes, op))
        first_event = curr_e2e_event.split('-')[0]
        second_event = curr_e2e_event.split('-')[-1]
        ln = len(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mx = max(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mn = min(src_dict[(op, len_bytes, e2e_seq, e2e_event)])
        mean = round(np.mean(src_dict[(op, len_bytes, e2e_seq, e2e_event)]), 6)
        median = round(np.median(src_dict[(op, len_bytes, e2e_seq, e2e_event)]), 6)
        print("    %d: %s<---->%s" % (e2e_seq, first_event, second_event))
        print("          |--%d cases"% ln)
        print("          |--Mean:[%f s], Median:[%f s], Max:[%f s], Min:[%f s]" % (mean, median, mx, mn))
        if first_event == gvar.gReqEvent_start and second_event == gvar.gReqEvent_end:
            print("          |-- I/O speed:[%0.3f MB/s (mean)], [%0.3f MB/s (median)]" %
                    (
                        round((1 / float(mean) * float(len_bytes)) / 1024 / 1024, 3),
                        round((1 / float(median) * float(len_bytes)) / 1024 / 1024, 3)
                    )
                  )
    sys.stdout = bak_stdout
    fd.close()


def e2e_duration_bar_scatter_pdf_show():

    if not sgE2E_e2e_distribution_by_pid_dic:
        return

    src_dict = sgE2E_e2e_distribution_by_pid_dic

    pre_pid = ''
    pre_op = ''
    pre_len_bytes = 0
    e2e_list = []
    e2e_duration_list = []
    e2e_record_quantities_dict = {}
    max_events = 10
    min_items_required = 10
    pid_op_len_seq_event_tuple_list = sorted(src_dict.keys())

    try:
        pdf = PdfPages(gvar.gOutput_Dir_Default+"e2e_duration_bar_scatter_per_pid.pdf")
    except:
        melib.me_warning("Create e2e_duration_bar_scatter_per_pid file failed.")
        return

    for (curr_pid, curr_op, curr_chunk, curr_seq, curr_e2e_name) in pid_op_len_seq_event_tuple_list:
        title = curr_pid + '/' + curr_op + '/' + str(curr_chunk)
        if len(src_dict[(curr_pid, curr_op, curr_chunk, curr_seq, curr_e2e_name)]) < min_items_required:
            melib.me_warning("The e2e %s only has %d records, cannot add into e2e_duration_bar_scatter_per_pid" %
                             (title, len(src_dict[(curr_pid, curr_op, curr_chunk, curr_seq, curr_e2e_name)])))
            continue
        if pre_pid is not curr_pid or pre_len_bytes != curr_chunk:
            if e2e_list and e2e_duration_list:
                title = pre_pid + '/' + pre_op + '/' + str(pre_len_bytes)
                if len(e2e_list) < max_events:
                    # draw the bar chart
                    x_pos = np.arange(len(e2e_list))
                    plt.figure()
                    plt.bar(x_pos, e2e_duration_list, 0.35, align='center', alpha=0.5, color="green", yerr=0.000001)
                    plt.xticks(x_pos-0.5, e2e_list, fontsize=5, rotation=10)
                    plt.ylabel('ms')
                    plt.title(title)
                    for a, b in zip(x_pos, e2e_duration_list):
                        plt.text(a, b+0.001, '%.3fms\n%d items' % (b, e2e_record_quantities_dict[b]),
                                 ha='center', va='bottom', fontsize=5, color='red')
                    pdf.savefig()
                else:
                    melib.me_error("There are %d e2e events, over the maximum limited number %d. failed to draw %s." %
                                   (len(e2e_list), max_events, title))
                e2e_list = []
                e2e_duration_list = []
                e2e_record_quantities_dict.clear()

            pre_pid = curr_pid
            pre_len_bytes = curr_chunk
            pre_op = curr_op

        e2e_list.append(curr_e2e_name)
        mean = round(np.mean(src_dict[(curr_pid, curr_op, curr_chunk, curr_seq, curr_e2e_name)]), 6)
        mean = 1000 * mean  # transfer ns to ms
        #median = round(np.median(src_dict[(pid, op, chunk, seq, e2e_name)]), 6)
        e2e_duration_list.append(mean)
        e2e_record_quantities_dict[mean] = len(src_dict[(curr_pid, curr_op, curr_chunk, curr_seq, curr_e2e_name)])

    if e2e_list and e2e_duration_list:
        title = pre_pid + '/' + pre_op + '/' + str(pre_len_bytes)
        if len(e2e_list) < max_events:
            # draw the bar chart
            x_pos = np.arange(len(e2e_list))
            plt.figure()
            plt.bar(x_pos, e2e_duration_list, 0.35, align='center', alpha=0.5, color="green", yerr=0.000001)
            plt.xticks(x_pos-0.5, e2e_list, fontsize=5, rotation=10)
            plt.ylabel('ms')
            plt.title(title)
            for a, b in zip(x_pos, e2e_duration_list):
                plt.text(a, b + 0.001, '%.3fms\n%d items' % (b, e2e_record_quantities_dict[b]),
                         ha='center', va='bottom', fontsize=5, color='red')
            pdf.savefig()
        else:
            melib.me_error("There are %d e2e events, over the maximum limited number %d. failed to draw %s."%
                           (len(e2e_list), max_events, title))

    pdf.close()


def e2e_event_main():

    if sgEvent_Property_DataBank_groupbyevent:
        melib.me_pprint_dict_file(gvar.gOutput_Dir_Default + "00-sgEvent_Property_DataBank_groupbyevent.log",
                                  sgEvent_Property_DataBank_groupbyevent)

        """  Step 1 """
        print("Step 1: Calculating E2E duration raw data ......")
        e2e_duration_calculator()  # fill in sgE2E_Duration_DataBank.

        if sgE2E_Duration_DataBank:

            melib.me_pprint_dict_file(gvar.gOutput_Dir_Default + "01-sgE2E_Duration_DataBank_groupbyevent.log",
                                      sgE2E_Duration_DataBank)
            #melib.me_pprint_dict_scream(sgE2E_Duration_DataBank)
            #melib.me_pickle_save_obj("./01-pickle-sgE2E_Duration_DataBank.log",
            #                         sgE2E_Duration_DataBank)

            """ Step 2 """
            print("Step 2: databank resolving ......")
            e2e_databank_resolver()  # to resolve the databank and fill in several key dictionaries.

            if sgE2E_e2e_distribution_by_pid_dic:  # analyze and generate the result file by pid
                #melib.me_pprint_dict_scream(sgE2E_e2e_distribution_by_pid_dic)
                melib.me_pprint_dict_file(gvar.gOutput_Dir_Default +
                                           "./02-sgE2E_e2e_distribution_by_pid_dic-groupbyevent.log",
                                           sgE2E_e2e_distribution_by_pid_dic)

                """ Step 3 """
                print("Step 3-1: analyzing I/O status by pid ......")
                e2e_stat_analyzer_by_pid()

                print("Step 3-2: outputting scattergram pdf by pid ......")
                e2e_scattergram_pdf_show_by_pid()

                print("Step 3-3: outputting histogram pdf by pid ......")
                e2e_histogram_pdf_show_by_pid()

            if sgE2E_e2e_distribution_by_chunk_dic:  # analyze and generate the result file by op+len
                melib.me_pprint_dict_file(gvar.gOutput_Dir_Default +
                                          "./02-sgE2E_e2e_distribution_by_chunk_dic-groupbyevent.log",
                                          sgE2E_e2e_distribution_by_chunk_dic)

                """ Step 4 """
                print("Step 4-1: analyzing I/O status by op_len ......")
                e2e_stat_analyzer_by_op_len()
                print("Step 4-2: outputting scattergram pdf by op_len ......")
                e2e_scattergram_pdf_show_by_op_len()
                print("Step 4-3: outputting histogram pdf by op_len ......")
                e2e_histogram_pdf_show_by_op_len()
        """ Step 5 """
        print("Step 5: Creating e2e_duration_bar_scatter_per_pid.pdf  ....")
        e2e_duration_bar_scatter_pdf_show()

    else:
        melib.me_warning("sgEvent_Property_DataBank_groupbyevent is empty.")
        raise melib.DefinedExcepton("Parsing failure")
    return 1
