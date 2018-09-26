#!/usr/bin/python
# # !/usr/bin/env python
"""
Copyright 2018 Micron Inc. Munich
"""


import sys
import re
import gvar
import conf
from lib import melib

''' Block trace event formant:
task pid     cpu            timestamp   function  
iozone-5029  [005] ...1   365.499344: scsi_dispatch_cmd_start:

host_no=0 channel=0 id=0 lun=3 data_sgl=16 prot_sgl=0 prot_op=SCSI_PROT_NORMAL tag=5
        op      address     len
cmnd=(WRITE_10 lba=5026608 txlen=16 protect=0 raw=2a 00 00 4c b3 30 00 00 10 00)
'''

'''
def parser_scsi_trace_event(event):
    para_dict = {}
    delimiter = '\s\('
    temp = melib.me_split(delimiter, event)
    task_pid = temp[0]
    para_dict['task'] = task_pid.split('-')[0]
    para_dict['pid'] = task_pid.split('-')[-1]
    para_dict['cpu'] = temp[1][1:-1]
    para_dict['timestamp'] = temp[3][:-1]
    para_dict['function'] = temp[4][:-1]

    para_dict[gvar.gmenu_op] = temp[temp.index('cmnd=') + 1]

    if para_dict[gvar.gmenu_op].startswith('WRITE'):
        para_dict[gvar.gmenu_op] = gvar.gWrite_Req
    elif para_dict[gvar.gmenu_op].startswith('READ'):
        para_dict[gvar.gmenu_op] = gvar.gRead_Req
    else:
        para_dict[gvar.gmenu_op] = None

    str_addr = temp[temp.index('cmnd=') + 2]
    para_dict['address'] = str(long(str_addr.split('=')[1]) * gvar.gSectorsPerBlock)

    str_len = temp[temp.index('cmnd=') + 3]
    para_dict['len'] = str(long(str_len.split('=')[1]) * gvar.gSCSI_LogicalBlockSize_Bytes )
    return para_dict

'''

'''
scsi_dispatch_cmd_done: host_no=0 channel=0 id=0 lun=3 data_sgl=16 prot_sgl=0 prot_op=SCSI_PROT_NORMAL \
tag=14 cmnd=(WRITE_10 lba=4922384 txlen=16 protect=0 raw=2a 00 00 4b 1c 10 00 00 10 00) result=(driver=DRIVER_OK \
host=DID_OK message=COMMAND_COMPLETE status=SAM_STAT_GOOD)
'''


def parser_scsi_trace_event_str(funcs):
    ret_dict = {}
    funcs_list = re.split(r"[:=()\s]+", funcs)

    ret_dict[gvar.gmenu_events] = funcs_list[0]
    ret_dict[gvar.gmenu_func] = funcs_list[0]
    ret_dict[gvar.gmenu_op] = ret_dict[gvar.gScsi_cmd] = funcs_list[funcs_list.index('cmnd') + 1]

    if ret_dict[gvar.gmenu_op].startswith('WRITE'):
        ret_dict[gvar.gmenu_op] = gvar.gWrite_Req
    elif ret_dict[gvar.gmenu_op].startswith('READ'):
        ret_dict[gvar.gmenu_op] = gvar.gRead_Req
    else:
        ret_dict[gvar.gmenu_op] = None

    ret_dict[gvar.gmenu_lba] = funcs_list[funcs_list.index('lba') + 1]
    ret_dict[gvar.gmenu_lba] = str(int(ret_dict[gvar.gmenu_lba]) * gvar.gSectorsPerBlock)

    ret_dict[gvar.gmenu_len] = funcs_list[funcs_list.index('txlen') + 1]
    ret_dict[gvar.gmenu_len] = int(ret_dict[gvar.gmenu_len]) * gvar.gSCSI_LogicalBlockSize_Bytes  # convert to bytes

    ret_dict[gvar.gScsi_host_no] = funcs_list[funcs_list.index('host_no') + 1]
    ret_dict[gvar.gScsi_channel] = funcs_list[funcs_list.index('channel') + 1]
    ret_dict[gvar.gScsi_id] = funcs_list[funcs_list.index('id') + 1]
    ret_dict[gvar.gScsi_lun] = funcs_list[funcs_list.index('lun') + 1]
    ret_dict[gvar.gScsi_raw] = funcs_list[funcs_list.index('raw') + 1:]

    return ret_dict


def scsi_functions2dict_parser(funcs):
    ret_dict = {}
    funcs_list = re.split(r"[:()\s]+", funcs)

    if funcs_list[0] in conf.gE2E_events_funcs_filter_dict['scsi']:

        if funcs_list[0] in conf.gFuns_dict['scsi']:
            return None
        elif funcs_list[0] in conf.gEvents_dict['scsi']:
            ret_dict = parser_scsi_trace_event_str(funcs)
        return ret_dict
    else:
        return None
