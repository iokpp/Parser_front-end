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
import re
import gvar
import conf
from lib import melib


''' Block trace event formant:
task pid     cpu            timestamp   function            op address    len
iozone-5031  [003] ....   364.930479: block_bio_remap: 8,48 WS 39422848 + 128 <- (8,62) 191360
iozone-5031  [003] ...1   364.930490: block_rq_issue: 8,48 WS 0 () 39422848 + 128 tag=19 [iozone]
iozone-4036  [005] ...1   464.102303: block_plug: [iozone]
iozone-4036  [005] ....   464.102303: block_unplug: [iozone] 1 Sync
'''


def parser_block_trace_line(line):

    para_dict = {}
    temp = line.split()
    task_pid = temp[0]

    para_dict['task'] = task_pid.split('-')[0]
    para_dict['pid'] = task_pid.split('-')[-1]
    para_dict['cpu'] = temp[1][1:-1]
    para_dict['timestamp'] = temp[3][:-1]
    para_dict['function'] = temp[4][:-1]
    if para_dict['function'] != 'block_plug' and para_dict['function'] != 'block_unplug':
        if temp[6] in gvar.gBlk_Events_Write_OP_list:
            para_dict[gvar.gmenu_op] = gvar.gWrite_Req
        elif temp[6] in gvar.gBlk_Events_Read_OP_list:
            para_dict[gvar.gmenu_op] = gvar.gRead_Req
        else:
            para_dict[gvar.gmenu_op] = None

        para_dict['address'] = temp[temp.index('+') - 1]
        para_dict['len'] = temp[temp.index('+') + 1]
    elif para_dict['function'] == 'block_unplug':
        para_dict['count'] = temp[temp.index('block_unplug:') + 1 + 1]
    return para_dict


def parser_block_trace_event_str(func):

    para_dict = {}
    temp = func.split()

    para_dict[gvar.gmenu_func] = temp[0].split(':')[0]
    tp_func = para_dict[gvar.gmenu_func]
    para_dict[gvar.gmenu_events] = tp_func

    para_dict[gvar.gmenu_lba] = None
    para_dict[gvar.gmenu_sectors] = None
    para_dict[gvar.gmenu_len] = None

    if tp_func != 'block_plug' and tp_func != 'block_unplug':
        para_dict[gvar.gmenu_op] = temp[2]

        if para_dict[gvar.gmenu_op] in gvar.gBlk_Events_Write_OP_list:
            para_dict[gvar.gmenu_op] = gvar.gWrite_Req
        elif para_dict[gvar.gmenu_op] in gvar.gBlk_Events_Read_OP_list:
            para_dict[gvar.gmenu_op] = gvar.gRead_Req

        para_dict[gvar.gmenu_lba] = temp[temp.index('+') - 1]
        para_dict[gvar.gmenu_sectors] = temp[temp.index('+') + 1]
        para_dict[gvar.gmenu_len] = int(para_dict[gvar.gmenu_sectors]) * gvar.gLogicalSectorSize_Bytes

    elif para_dict[gvar.gmenu_func] == 'block_unplug':
        para_dict[gvar.gmenu_reqs_unplug] = temp[temp.index('block_unplug:') + 1 + 1]

    return para_dict


def blk_functions2dict_parser(funcs):
    ret_dict = {}
    funcs_list = re.split(r"[:()\s]+", funcs)

    if funcs_list[0] in conf.gFuns_dict['block']:
        # this is just a function trace log, currently, we have nothing.
        # ret_dict[gmenu_events] = ret_dict[gmenu_func]
        return None
    elif funcs_list[0] in conf.gEvents_dict['block']:
        # this is a block event, need to further parser.
        ret_dict = parser_block_trace_event_str(funcs)
        return ret_dict
    else:
        return None


