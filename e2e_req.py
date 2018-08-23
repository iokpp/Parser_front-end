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
sgRequest_counter_per_pid_op is three-dimension nested dictionary.
in which, contains the quantity of request associated with certain
PID, operation and chunk size.
eg: sgRequest_counter_per_pid_op[pid][op][chunk] = 11332,
'''
sgRequest_counter_per_pid_op = melib.MultipleDimensionNestDict()


'''
sgLBA_list_of_PID_OP is a dictionary, in which contains the LAB
that associated with specific pid and operation.
eg:
{(pid, op):
    ['2314', '4587e',...], 
...
}
'''
sgLBA_list_of_PID_OP = dict()


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
request event property dictionary grouped by request, its topology, eg:
{'pid a':  ----> first level branch, indicates the PID associated with this item 
    { write/read: ----> chunk size
        {'chunk size':  ----> indicates this is a write or read
            {'req_seq 1':  ----> indicates the numerical order of this request 
                {event_seq 1: ----> indicates the sequence number of this event
                    { event-name':
                        {'timestamp':'233424.4343', 'chunk':'1024'/None, ...
                        }
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
sgEvent_Property_DataBank_groupbyrequest[pid][op][chunk][req_seq][event_seq][event_name][timestamp] = 4546565.545
sgEvent_Property_DataBank_groupbyrequest[pid][op][chunk][req_seq][event_seq][event_name][len_bytes] = 545
'''
sgEvent_Property_DataBank_groupbyrequest = melib.MultipleDimensionNestDict()

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

    for (temp_pid, temp_op) in sgLBA_list_of_PID_OP.keys():
        if lba in sgLBA_list_of_PID_OP[(temp_pid, temp_op)]:
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
        melib.me_warning("---match pids %s:%s using pid %d " % (match_num, match_pids, ret_pid))

    return ret_pid


def is_event_exist_in_request_databank(pid, op, vfs_len, seq, event_str):
    for i in sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][seq].keys():
        if event_str in sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][seq][i].keys():
            return True
    return False


def add_to_db(pid, original_pid,  op, vfs_len, req_seq, event_seq, event, timestamp, lba, bytes):

    line_no = gvar.gCurr_line
    if (not is_event_exist_in_request_databank(pid, op, vfs_len, req_seq, event)):
        sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq][event_seq][event][gvar.gmenu_time] = timestamp
        sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq][event_seq][event][gvar.gmenu_len] = bytes
        sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq][event_seq][event][gvar.gmenu_lba] = lba
        if pid == original_pid:
            ''' if this event appears in the other PID log, we don't want to
            change current PID info.'''
            update_current_pid_info_dict(pid, vfs_len, op, req_seq, event_seq, event, lba)
    else:
        melib.me_warning("Failed to add Line %d, since %s already exists in data bank. req_seq %d." %
                         (line_no, event, req_seq))


def add_leaf(dic):

    line_no = gvar.gCurr_line
    lba = None
    op = dic[gvar.gmenu_op]
    pid = dic[gvar.gmenu_PID]
    orig_pid = dic[gvar.gmenu_OriginalPid]
    len_bytes = dic[gvar.gmenu_len]
    timestamp = dic[gvar.gmenu_time]
    event_name = dic[gvar.gmenu_events]

    if gvar.gmenu_lba in dic.keys():
        lba = dic[gvar.gmenu_lba]

    vfs_len = sgCurrent_info[pid][gvar.gmenu_len]  # get data length which passed from VFS
    #seq = sgRequest_counter_per_pid_op[pid][op][vfs_len]  # get what sequence of this request
    req_seq = sgCurrent_info[pid][gvar.gmenu_req_seq]

    #pre_event = sgCurrent_info[pid][gvar.gmenu_pre_event]  # get the previous event of this request
    #event_seq = sgCurrent_info[pid][gvar.gmenu_event_seq]  #int(pre_event.split('-')[0])

    #event_seq += 1

    pre_op = sgCurrent_info[pid][gvar.gmenu_op]
    if pre_op != op:
        # if there is event which op is not the same VFS's, currently we just return. FIXME
        return

    if len_bytes is None:
        melib.me_dbg("Line %d, event %s, no data_len assigned!" % (line_no, event_name))
    elif vfs_len != len_bytes:
        #the sub-event data length is not consistent with the VFS, we now just return FIXME
        melib.me_warning("Line %d data_len %d is not consistent with VFS assigned %d."% \
                         (line_no, len_bytes, vfs_len))
        return
      # melib.me_pprint_dict_scream(sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len])

    # check if this event already exists in its request event list FIXME.
    if is_event_exist_in_request_databank(pid, op, vfs_len, req_seq, event_name):
        max_seq = sgRequest_counter_per_pid_op[pid][op][vfs_len]

        if (req_seq != max_seq) and \
                (not is_event_exist_in_request_databank(pid, op,vfs_len, max_seq, event_name)):
            req_seq = max_seq
            #event_seq = sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq].keys()[-1]
            #event_seq += 1
        else:
            if lba and lba == sgCurrent_info[pid][gvar.gmenu_lba]:
                melib.me_warning("Failed to add Line %d, since %s already exists in databank. "
                                 "seq %d. max_seq %d." %
                                 (line_no, event_name, req_seq, max_seq))
                return

    found_num = 0

    if lba and event_name != 'block_bio_remap':
        if lba != sgCurrent_info[pid][gvar.gmenu_lba]:
            """ The lba of new event adding is not the current request lba,
            this is possible in case of hardware completion interruption. """

            if len_bytes:
                for temp_len in sgBIO_Remap_info_DataBank[pid][op].keys():
                    if temp_len == len_bytes:
                        for temp_req_seq in sgBIO_Remap_info_DataBank[pid][op][temp_len].keys():
                            if sgBIO_Remap_info_DataBank[pid][op][temp_len][temp_req_seq][gvar.gmenu_lba] == lba:
                                if timestamp > sgBIO_Remap_info_DataBank[pid][op][vfs_len][temp_req_seq][gvar.gmenu_time]:
                                    req_seq = temp_req_seq
                                    vfs_len = temp_len
                                    found_num += 1
            if found_num == 0:
                melib.me_warning("Line %d, the lba of %s  does not exist in sgCurrent_info." %
                                 (line_no, event_name))
                return
            """ rebase the event sequence number """
            #event_seq = sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq].keys()[-1]
            #event_seq += 1
            #event = str(event_seq) + '-' + bak_event
    event_seq = sgEvent_Property_DataBank_groupbyrequest[pid][op][vfs_len][req_seq].keys()[-1]
    event_seq += 1

    if event_name == 'block_bio_remap':
        sgBIO_Remap_info_DataBank[pid][op][vfs_len][req_seq][gvar.gmenu_lba] = lba
        sgBIO_Remap_info_DataBank[pid][op][vfs_len][req_seq][gvar.gmenu_time] = timestamp
        sgBIO_Remap_info_DataBank[pid][op][vfs_len][req_seq][gvar.gmenu_len] = len_bytes

    add_to_db(pid, orig_pid, op, vfs_len, req_seq, event_seq, event_name, timestamp, lba, len_bytes)


def add_one_new_pid_branch(dict):

    pid = dict[gvar.gmenu_PID]
    op = dict[gvar.gmenu_op]
    chunk = dict[gvar.gmenu_len]
    event = dict[gvar.gmenu_events]
    timestamp = dict[gvar.gmenu_time]
    #orig_pid = dict[gvar.gmenu_OriginalPid]
    sgPID_list.append(pid)  # add this pid into pid list
    #bak_event = event
    #event = '1-'+event
    seq = sgRequest_counter_per_pid_op[pid][op][chunk] = 1  # this is the first req associated with PID
    '''
    sgEvent_Property_DataBank_groupbyrequest[pid][op][chunk][1][1][bak_event][gvar.gmenu_time] = timestamp
    sgEvent_Property_DataBank_groupbyrequest[pid][op][chunk][1][1][bak_event][gvar.gmenu_len] = chunk
    sgEvent_Property_DataBank_groupbyrequest[pid][op][chunk][1][1][bak_event][gvar.gmenu_lba] = None
    '''
    add_to_db(pid, pid, op, chunk, seq, seq, event, timestamp, None, chunk)
    #update_current_pid_info_dict(pid, chunk, op, seq, seq, event, '0')


def add_block_leaf(property_dict):
    """
    Add this block layer event into the data bank.
    :param property_dict:
    :return: None
    """
    line_no = gvar.gCurr_line
    blk_dic = property_dict.copy()
    pid = blk_dic[gvar.gmenu_PID]
    event = blk_dic[gvar.gmenu_events]

    if gvar.gmenu_lba in blk_dic.keys() and blk_dic[gvar.gmenu_lba] is not None:
        lba = blk_dic[gvar.gmenu_lba]
    else:
        lba = None

    if gvar.gmenu_op not in blk_dic.keys() or blk_dic[gvar.gmenu_op] is None:
        # This event hasn't assigned the operation type (write/read).
        melib.me_dbg("line: %d, pid %s No operation type assigned!" %
                     (line_no, pid))
        blk_dic[gvar.gmenu_op] = sgCurrent_info[pid][gvar.gmenu_op]
        op = blk_dic[gvar.gmenu_op]
    else:
        op = blk_dic[gvar.gmenu_op]

    if event == "block_bio_remap":
        sgLBA_list_of_PID_OP.setdefault((pid, op), []).append(lba)
        melib.me_dbg("Event: %s, sgLBA_list_of_PID_OP: %s !" %
                     (event, sgLBA_list_of_PID_OP))
    else:
        if lba is not None:
            if ((pid, op) in sgLBA_list_of_PID_OP.keys() and lba not in sgLBA_list_of_PID_OP[(pid, op)]) or \
                    ((pid, op) not in sgLBA_list_of_PID_OP.keys()):

                ''' If current lba is not in this pid lab dictionary, we should look for
                whether this event associated with lab belongs to other pid.
                '''
                ret = adjust_pid_by_lba_op(pid, lba, op)  # try to find out a right PID
                if ret is None:
                    # cannot find a pid associated with this request, currently
                    # we just don't add this event into data bank. FIXME
                    print("We cannot find a pid associated with this line %d event %s" %
                          (line_no, property_dict[gvar.gmenu_events]))  # melib.me_dbg
                    return
                else:
                    blk_dic[gvar.gmenu_PID] = ret
    add_leaf(blk_dic)


def add_scsi_leaf(property_dict):
    line_no = gvar.gCurr_line
    scsi_dic = property_dict.copy()
    pid = scsi_dic[gvar.gmenu_PID]

    if gvar.gmenu_op in scsi_dic.keys() and scsi_dic[gvar.gmenu_op] is not None:
        op = scsi_dic[gvar.gmenu_op]
    else:
        op = None
    if gvar.gmenu_lba in scsi_dic.keys() and scsi_dic[gvar.gmenu_lba] is not None:
        lba = scsi_dic[gvar.gmenu_lba]
    else:
        lba = None
    if lba is not None:
        if ((pid, op) in sgLBA_list_of_PID_OP.keys() and lba not in sgLBA_list_of_PID_OP[(pid, op)]) or\
                ((pid, op) not in sgLBA_list_of_PID_OP.keys()):
            ''' If current lba is not in this dictionary, we should check if
             this event belongs to other pid.
            '''
            ret = adjust_pid_by_lba_op(pid, lba, op)
            if ret is None:
                # cannot find a pid associated with this request, currently
                # we just don't add this event into data bank. FIXME
                print("We cannot find a pid associated with this line %d event %s" %
                             (line_no, property_dict[gvar.gmenu_events]))  # melib.me_dbg
                return
            else:
                scsi_dic[gvar.gmenu_PID] = ret

    add_leaf(scsi_dic)


def add_others_leaf(property_dict):

    temp_dic = property_dict.copy()
    pid = temp_dic[gvar.gmenu_PID]

    if temp_dic[gvar.gmenu_op] is None:
        # This event hasn't assigned the direction of request.
        melib.me_dbg("No operation type assigned!")
        temp_dic[gvar.gmenu_op] = sgCurrent_info[pid][gvar.gmenu_op]
    #    else:
    #        op = temp_dic[gvar.gmenu_op]

    add_leaf(temp_dic)


def add_one_new_leaf(property_dict):

    func = property_dict.get(gvar.gmenu_func)

    if func is None:
        ''' If there is no function name, we explicitly reject adding.'''
        return

    if func in conf.gE2E_events_funcs_filter_dict['block']:
        add_block_leaf(property_dict)
        return
    elif func in conf.gE2E_events_funcs_filter_dict['scsi']:
        add_scsi_leaf(property_dict)
        return
    else:
        for key in conf.gE2E_events_funcs_filter_dict.keys():
            if key != 'block' and key != 'scsi':
                if func in conf.gE2E_events_funcs_filter_dict[key]:
                    add_others_leaf(property_dict)
                    return


def add_new_req_into_tree(property_dict):
    pid = property_dict[gvar.gmenu_PID]
    orig_pid = property_dict[gvar.gmenu_OriginalPid]
    len_bytes = property_dict[gvar.gmenu_len]
    op = property_dict[gvar.gmenu_op]
    event = property_dict[gvar.gmenu_events]
    timestamp = property_dict[gvar.gmenu_time]

    sgRequest_counter_per_pid_op[pid][op][len_bytes] += 1
    #seq = sgRequest_counter_per_pid_op[pid][op][len_bytes]
    req_seq = sgRequest_counter_per_pid_op[pid][op][len_bytes]
    #bak_event = event
    #event = '1-'+event  # this is the first event of request.
    '''
    sgEvent_Property_DataBank_groupbyrequest[pid][op][len_bytes][req_seq][1][bak_event][gvar.gmenu_time] = timestamp
    sgEvent_Property_DataBank_groupbyrequest[pid][op][len_bytes][req_seq][1][bak_event][gvar.gmenu_len] = len_bytes
    sgEvent_Property_DataBank_groupbyrequest[pid][op][len_bytes][req_seq][1][bak_event][gvar.gmenu_lba] = None
    '''
    add_to_db(pid, orig_pid, op, len_bytes, req_seq, 1, event, timestamp, None, len_bytes)
    #update_current_pid_info_dict(pid, len_bytes, op, req_seq, 1, event, '0')


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

    if event is gvar.gReqEvent_start:
        # This is a new request.
        if pid not in sgPID_list and \
                        pid not in sgEvent_Property_DataBank_groupbyrequest.keys():
            ''' This PID first time appears, create a new pid branch. '''
            add_one_new_pid_branch(property_dict)
        elif pid in sgPID_list and \
                pid in sgEvent_Property_DataBank_groupbyrequest.keys():
            ''' This PID has been existing in the data bank. '''
            if op in sgEvent_Property_DataBank_groupbyrequest[pid].keys() and \
                    len_bytes not in sgEvent_Property_DataBank_groupbyrequest[pid][op].keys():
                add_one_new_pid_branch(property_dict)
            elif op not in sgEvent_Property_DataBank_groupbyrequest[pid].keys():
                add_one_new_pid_branch(property_dict)
            else:
                add_new_req_into_tree(property_dict)
        else:
            melib.me_warning(
                "sgPID_list and sgEvent_Property_DataBank_groupbyrequest.keys not consistent.")
            melib.me_warning(sgPID_list)
            melib.me_warning(sgEvent_Property_DataBank_groupbyrequest.keys())
    elif event is not gvar.gReqEvent_start:
        ''' This is not the first event of request. '''
        if pid in sgEvent_Property_DataBank_groupbyrequest.keys():
            add_one_new_leaf(property_dict)
        else:
            ''' If the PID doesn't exist in the data bank, then check if its LBA could
            be associated with one request in the data bank.'''
            lba = property_dict.get(gvar.gmenu_lba)
            if lba is not None and \
                    pid is not None \
                    and op is not None:
                ''' Specified PID doesn't exist in the data bank,
                but LBA, PID and OP are all not None, try to find
                out its real PID. '''
                adjust_pid = adjust_pid_by_lba_op(pid, lba, op)
                if adjust_pid is not None:
                    property_dict[gvar.gmenu_PID] = adjust_pid
                    add_one_new_leaf(property_dict)


def add_one_duration(pid, op, len_bytes, req_seq, pre_event_dict, curr_event_dict, E2E_seq):
        pre_event = list(pre_event_dict)[0]
        curr_event = list(curr_event_dict)[0]
        pre_time = pre_event_dict[pre_event][gvar.gmenu_time]
        curr_time = curr_event_dict[curr_event][gvar.gmenu_time]

        dur = round(float(curr_time) - float(pre_time), 6)
        e2e = pre_event + '-' + curr_event
        sgE2E_Duration_DataBank[pid][op][len_bytes][req_seq][E2E_seq][e2e] = dur


def interval_calculating(pid, op, len_bytes, req_seq):
    pre_event = {}
    curr_event = {}
    duration_seq = 0
    one_req_dict = sgEvent_Property_DataBank_groupbyrequest[pid][op][len_bytes][req_seq]
    req_seq_list = sorted(one_req_dict.keys())

    for i in req_seq_list:
        event = list(one_req_dict[i])[0]
        if event in conf.gE2E_trace_points_in_one_request:
            duration_seq += 1
            if pre_event == {}:
                pre_event = one_req_dict[1]
                curr_event = one_req_dict[i]
                add_one_duration(pid, op, len_bytes, req_seq, pre_event, curr_event, duration_seq)
                pre_event = curr_event
            else:
                curr_event = one_req_dict[i]
                add_one_duration(pid, op, len_bytes, req_seq, pre_event, curr_event, duration_seq)
                pre_event = curr_event
        if event == gvar.gReqEvent_end:  # calculate total duration
            curr_event = one_req_dict[i]
            if list(one_req_dict[1])[0] == gvar.gReqEvent_start:
                add_one_duration(pid, op, len_bytes, req_seq, one_req_dict[1], curr_event, 0)

    return


def e2e_duration_calculator():
    """
    According to sgEvent_Property_DataBank_groupbyrequest, analyze and
    calculate the e2e duration. finally fill in
    sgE2E_Duration_DataBank.
    :return:
    """
    for pid in sgEvent_Property_DataBank_groupbyrequest.keys():
        for op in sgEvent_Property_DataBank_groupbyrequest[pid].keys():
            for len_bytes in sgEvent_Property_DataBank_groupbyrequest[pid][op].keys():
                seqs = sorted(sgEvent_Property_DataBank_groupbyrequest[pid][op][len_bytes].keys())
                for i in seqs:
                    interval_calculating(pid, op, len_bytes, i)
    return


def e2e_databank_resolver(option):
    curr_total = 0
    software_cost = 0
    curr_hw_cost = 0
    for pid in sgE2E_Duration_DataBank.keys():
        for op in sgE2E_Duration_DataBank[pid].keys():
            for len_bytes in sgE2E_Duration_DataBank[pid][op].keys():

                for req_seq in sgE2E_Duration_DataBank[pid][op][len_bytes].keys():
                    curr_total = curr_hw_cost = 0
                    for e2e_seq in sgE2E_Duration_DataBank[pid][op][len_bytes][req_seq].keys():

                        e2e_event =\
                            list(sgE2E_Duration_DataBank[pid][op][len_bytes][req_seq][e2e_seq])[0]
                        e2e_duration =\
                            sgE2E_Duration_DataBank[pid][op][len_bytes][req_seq][e2e_seq][e2e_event]

                        if e2e_event == gvar.gReqEvent_start + '-' + gvar.gReqEvent_end:
                            curr_total = e2e_duration
                        if e2e_event in conf.gE2E_HW_transfer_duration_define:
                            curr_hw_cost = e2e_duration

                        if curr_total and curr_hw_cost:
                            sgE2E_hw_distribution_dict.setdefault((op, len_bytes), []).append(curr_hw_cost)

                            '''
                            if not sgE2E_hw_distribution_dict:
                                sgE2E_hw_distribution_dict[(op, len_bytes)] = [curr_hw_cost]
                            elif (op, len_bytes) not in sgE2E_hw_distribution_dict.keys():
                                sgE2E_hw_distribution_dict[(op, len_bytes)] = [curr_hw_cost]
                            elif (op, len_bytes) in sgE2E_hw_distribution_dict.keys():
                                sgE2E_hw_distribution_dict[(op, len_bytes)].append(curr_hw_cost)
                            '''
                            software_cost = curr_total - curr_hw_cost
                            sgE2E_sw_distribution_dict.setdefault((op, len_bytes), []).append(software_cost)
                            '''
                            if not sgE2E_sw_distribution_dict:
                                sgE2E_sw_distribution_dict[(op, len_bytes)] = [software_cost]
                            elif (op, len_bytes) not in sgE2E_sw_distribution_dict.keys():
                                sgE2E_sw_distribution_dict[(op, len_bytes)] = [software_cost]
                            elif (op, len_bytes) in sgE2E_sw_distribution_dict.keys():
                                sgE2E_sw_distribution_dict[(op, len_bytes)].append(software_cost)
                            '''
                            curr_hw_cost = curr_total = 0

                        sgE2E_e2e_distribution_by_pid_dic.setdefault((pid, op, len_bytes, e2e_seq, e2e_event),
                                                                    []).append(e2e_duration)
                        ''''
                        if not sgE2E_e2e_distribution_by_pid_dic:
                            sgE2E_e2e_distribution_by_pid_dic[(pid, op, len_bytes, e2e_seq, e2e_event)] = [e2e_duration]
                        elif (pid, op, len_bytes, e2e_seq, e2e_event) not in sgE2E_e2e_distribution_by_pid_dic.keys():
                            sgE2E_e2e_distribution_by_pid_dic[(pid, op, len_bytes, e2e_seq, e2e_event)] = [e2e_duration]
                        elif (pid, op, len_bytes, e2e_seq, e2e_event) in sgE2E_e2e_distribution_by_pid_dic.keys():
                            sgE2E_e2e_distribution_by_pid_dic[(pid, op, len_bytes, e2e_seq, e2e_event)].append(e2e_duration)
                        '''
                        sgE2E_e2e_distribution_by_chunk_dic.setdefault((op, len_bytes, e2e_seq, e2e_event),
                                                                     []).append(e2e_duration)
                        '''
                        if not sgE2E_e2e_distribution_by_chunk_dic:
                            sgE2E_e2e_distribution_by_chunk_dic[(op, len_bytes, e2e_seq, e2e_event)] = [e2e_duration]
                        elif (op, len_bytes, e2e_seq, e2e_event) not in sgE2E_e2e_distribution_by_chunk_dic.keys():
                            sgE2E_e2e_distribution_by_chunk_dic[(op, len_bytes, e2e_seq, e2e_event)] = [e2e_duration]
                        elif (op, len_bytes, e2e_seq, e2e_event) in sgE2E_e2e_distribution_by_chunk_dic.keys():
                            sgE2E_e2e_distribution_by_chunk_dic[(op, len_bytes, e2e_seq, e2e_event)].append(e2e_duration)
                        '''

    return


def e2e_histogram_pdf_show_by_pid():
    src_dict = sgE2E_e2e_distribution_by_pid_dic
    histogram_threshold = 200
    pid_op_len_seq_event_tuple_list = sorted(src_dict.keys())

    try:
        hist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_histogram_by_pid.pdf")
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
        dist_pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_scattergram_by_pid.pdf")
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

    fd = open(gvar.gOutput_Dir_Default+"Report_by_pid.log", 'w')
    bak_stdout = sys.stdout
    sys.stdout = fd
    for (pid, op, len_bytes, e2e_seq, e2e_event) in pid_op_len_seq_event_tuple_list:
        curr_e2e_event = e2e_event
        if curr_pid is not pid or curr_len_bytes != len_bytes:
            curr_pid = pid
            curr_len_bytes = len_bytes
            print("          ")
            print("  -----------------------------------------------------------")
            print("  Task-PID: %s. Chunk Size : %s bytes[%s]" % (pid, len_bytes, op))
        first_event = curr_e2e_event.split('-')[0]
        second_event = curr_e2e_event.split('-')[-1]
        ln = len(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mx = max(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mn = min(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)])
        mean = round(np.mean(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)]), 6)
        median = round(np.median(src_dict[(pid, op, len_bytes, e2e_seq, e2e_event)]), 6)
        print("    %d: %s<---->%s" % (e2e_seq, first_event, second_event))
        print("          |--%d cases"% ln)
        print("          |--Mean:[%f s], Median:[%f s], Max:[%f s], Min:[%f s]" % (mean, median, mx, mn))
        if first_event == gvar.gReqEvent_start and second_event == gvar.gReqEvent_end:
            print("          |-- I/O speed:[%0.3f MB/s (mean)], [%0.3f MB/s (median)]" %
                    (
                        round((1/float(mean) * float(len_bytes))/1024/1024, 3),
                        round((1/float(median) * float(len_bytes)) / 1024 / 1024, 3)
                    )
                  )
    sys.stdout = bak_stdout
    fd.close()


def e2e_stat_analyzer_by_op_len():

    src_dict = sgE2E_e2e_distribution_by_chunk_dic

    curr_pid = ''
    pdf_ok = True
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


def software_hardware_duration_division():

    if not sgE2E_sw_distribution_dict:
        return
    if not sgE2E_hw_distribution_dict:
        return
    if not sgE2E_e2e_distribution_by_chunk_dic:
        return
    hw_dict = sgE2E_hw_distribution_dict
    sw_dict = sgE2E_sw_distribution_dict
    distr_dict = sgE2E_e2e_distribution_by_chunk_dic
    op_len_tuple_list = sorted(hw_dict.keys())
    colors = ["blue", "red", "coral", "green", "yellow", "orange"]
    
    try:
        pdf = PdfPages(gvar.gOutput_Dir_Default+"sgE2E_hw_sf_division.pdf")
    except:
        melib.me_warning("Create sgE2E_hw_sf_division file failed.")
        return
    """  Step 1: Hardware and software duration distribution """
    for (op, length) in op_len_tuple_list:

        hw_items_ln = len(hw_dict[(op, length)])

        if (op, length) in sw_dict.keys():
            sw_items_ln = len(sw_dict[(op, length)])
            if hw_items_ln != sw_items_ln:
                continue
            hw_list_data = hw_dict[(op, length)][gvar.gDefault_graph_start_from_item:gvar.gDefault_graph_max_items]
            sw_list_data = sw_dict[(op, length)][gvar.gDefault_graph_start_from_item:gvar.gDefault_graph_max_items]

            hw_y = [i * 1000 for i in hw_list_data]
            sw_y = [i * 1000 for i in sw_list_data]
            x = np.arange(len(hw_list_data)) + 1

            plt.figure()
            plt.plot(x, hw_y, 'g-', alpha=0.75, linewidth=1.0, label='HW')
            plt.plot(x, sw_y, 'r-', alpha=0.75, linewidth=1.0, label='SW')
            plt.ylabel('Millisecond (ms)', fontsize=10)
            plt.xlabel('T', fontsize=10)
            title = op + '/' + str(length)  #'/' + e2e_event
            plt.title(title)
            plt.grid(False)
            plt.legend(fontsize=10, loc='best')
            pdf.savefig()
            plt.close()
    """
    Step 2: percentage pie char of each layer duration 
    """
    curr_op = 'none'
    curr_len_bytes = 0
    op_len_seq_event_tuple_list = sorted(distr_dict.keys())
    labels = []
    quants = []
    items = 0
    for (op, len_bytes, e2e_seq, e2e_event) in op_len_seq_event_tuple_list:
        if curr_op is not 'none':
            if curr_op is not op or curr_len_bytes != len_bytes:
                if items > 1:
                    x = [i * 1000000 for i in quants]
                    plt.figure()
                    plt.pie(x, autopct='%1.1f%%', pctdistance=0.8, shadow=True)
                    plt.title(curr_op + '/' + str(curr_len_bytes))
                    plt.axis('equal')
                    plt.legend(fontsize=10, loc='best', labels=labels)
                    pdf.savefig()
                    plt.close()
                quants = []
                labels = []
                items = 0

        if e2e_seq != 0:  # if e2e_seq is 0, this is a total duration
            labels.append(e2e_event)
            mean = round(np.mean(distr_dict[(op, len_bytes, e2e_seq, e2e_event)]), 6)
            quants.append(mean)
            items += 1
            curr_op = op
            curr_len_bytes = len_bytes

    if quants and labels:
        if items > 1:
            x = [i * 1000000 for i in quants]  # convert float to int
            plt.figure()
            plt.pie(x, autopct='%1.1f%%', pctdistance=0.8, shadow=True, startangle=90)
            plt.axis('equal')
            plt.title(curr_op + '/' + str(curr_len_bytes))
            plt.legend(fontsize=5, labels=labels)
            pdf.savefig()
            plt.close()

    pdf.close()


def e2e_main():

    if sgEvent_Property_DataBank_groupbyrequest and sgPID_list:
        melib.me_pprint_dict_file(gvar.gOutput_Dir_Default+"00-sgEvent_Property_DataBank_groupbyrequest.log",
                                  sgEvent_Property_DataBank_groupbyrequest)

        '''
        melib.me_pprint_dict_scream(sgEvent_Property_DataBank_groupbyrequest)
        melib.me_pickle_save_obj("./00-pickle-sgEvent_Property_DataBank_groupbyrequest.log",
        sgEvent_Property_DataBank_groupbyrequest)
        
        property_databank_jsobj = json.dumps(sgEvent_Property_DataBank_groupbyrequest)
        js_file_obj = open('sgEvent_Property_DataBank_groupbyrequest.json', 'w')
        js_file_obj.write(property_databank_jsobj)
        js_file_obj.close()
        '''

        """  Step 1 """
        print("Step 1: parsing distribution raw data bank ......")
        e2e_duration_calculator()  # fill in sgE2E_Duration_DataBank.

        if sgE2E_Duration_DataBank:
            #melib.me_pprint_dict_scream(sgE2E_Duration_DataBank)
            melib.me_pprint_dict_file(gvar.gOutput_Dir_Default+"01-sgE2E_Duration_DataBank.log",
                                      sgE2E_Duration_DataBank)
            #melib.me_pickle_save_obj("./01-pickle-sgE2E_Duration_DataBank.log",
            #                         sgE2E_Duration_DataBank)

            """ Step 2 """
            print("Step 2: databank resolving ......")
            e2e_databank_resolver('default')  # to resolve the databank and fill in several key dictionaries.

            if sgE2E_e2e_distribution_by_pid_dic:  # analyze and generate the result file by pid
                #melib.me_pprint_dict_scream(sgE2E_e2e_distribution_by_pid_dic)
                melib.me_pprint_dict_file(gvar.gOutput_Dir_Default+"./02-sgE2E_e2e_distribution_by_pid_dic.log",
                                          sgE2E_e2e_distribution_by_pid_dic)
                """ Step 3 """
                print("Step 3-1: analyzing I/O status by pid ......")
                e2e_stat_analyzer_by_pid()
                print("Step 3-2: outputting scattergram pdf by pid ......")
                e2e_scattergram_pdf_show_by_pid()
                print("Step 3-3: outputting histogram pdf by pid ......")
                e2e_histogram_pdf_show_by_pid()

            if sgE2E_e2e_distribution_by_chunk_dic:  # analyze and generate the result file by op+len
                melib.me_pprint_dict_file(gvar.gOutput_Dir_Default+"./02-sgE2E_e2e_distribution_by_chunk_dic.log",
                                          sgE2E_e2e_distribution_by_chunk_dic)
                """ Step 4 """
                print("Step 4-1: analyzing I/O status by op_len ......")
                e2e_stat_analyzer_by_op_len()
                print("Step 4-2: outputting scattergram pdf by op_len ......")
                e2e_scattergram_pdf_show_by_op_len()
                print("Step 4-3: outputting histogram pdf by op_len ......")
                e2e_histogram_pdf_show_by_op_len()
        """ Step 5 """
        print("Step 5: SW and HW duration division ....")
        software_hardware_duration_division()

    else:
        melib.me_warning("sgEvent_Property_DataBank_groupbyrequest is empty.")
        raise melib.DefinedExcepton("Parsing failure")
    return 1
