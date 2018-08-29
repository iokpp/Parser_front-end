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
from lib import melib
import gvar
import conf

#{'task name': [4096, ...], ...}
sgWA_VFS_write = dict()
#{'HW name': [4096, ....]}
sgWA_HW_write = dict()

#{'HW name': [4096, ....]}
sgRemap_write = dict()

#{'task name': [4096, ...], ...}
sgRA_VFS_read = dict()
#{'HW name': [4096, ....]}
sgRA_HW_read = dict()

#{'HW name': [4096, ....]}
sgRemap_read = dict()


def add_to_VFS_write_dict(task_str, bytes_len):
    sgWA_VFS_write.setdefault(task_str, []).append(bytes_len)
    '''
    if not sgWA_VFS_write:
        sgWA_VFS_write[task_str] = [bytes_len]
    elif task_str not in sgWA_VFS_write.keys():
        sgWA_VFS_write[task_str] = [bytes_len]
    elif task_str in sgWA_VFS_write.keys():
        sgWA_VFS_write[task_str].append(bytes_len)
    '''


def add_to_HW_write_dict(task_str, bytes_len):
    sgWA_HW_write.setdefault(task_str, []).append(bytes_len)
    '''
    if not sgWA_HW_write:
        sgWA_HW_write[task_str] = [bytes_len]
    elif task_str not in sgWA_HW_write.keys():
        sgWA_HW_write[task_str] = [bytes_len]
    elif task_str in sgWA_HW_write.keys():
        sgWA_HW_write[task_str].append(bytes_len)
    '''

def add_remap_write_dict(task_str, bytes_len):
    sgRemap_write.setdefault(task_str, []).append(bytes_len)
    '''
    if not sgRemap_write:
        sgRemap_write[task_str] = [bytes_len]
    elif task_str not in sgRemap_write.keys():
        sgRemap_write[task_str] = [bytes_len]
    elif task_str in sgRemap_write.keys():
        sgRemap_write[task_str].append(bytes_len)
    '''


def add_to_wa_property_tree(funcs):

    if funcs:
        task_pid = ''
        if gvar.gWA_RA_mode == gvar.gWA_RA_mode_by_task:
            task_pid = funcs[gvar.gmenu_task]
        else:
            task_pid = funcs[gvar.gmenu_PID]

        if funcs[gvar.gmenu_func] == 'sys_write':
            if funcs[gvar.gmenu_events] == gvar.gReqEvent_start:
                add_to_VFS_write_dict(task_pid, funcs[gvar.gmenu_len])
        elif funcs[gvar.gmenu_func] == 'sys_read':
            if funcs[gvar.gmenu_events] == gvar.gReqEvent_start:
                sgRA_VFS_read.setdefault(task_pid, []).append(funcs[gvar.gmenu_len])

        if funcs[gvar.gmenu_func] == 'block_bio_remap':
            if funcs[gvar.gmenu_op] == gvar.gWrite_Req:
                add_remap_write_dict(task_pid, funcs[gvar.gmenu_len])
            elif funcs[gvar.gmenu_op] == gvar.gRead_Req:
                sgRemap_read.setdefault(task_pid, []).append(funcs[gvar.gmenu_len])

        if funcs[gvar.gmenu_func] in conf.gWA_HW_transfer_completion_flags:
            if funcs[gvar.gmenu_op] == gvar.gWrite_Req:
                add_to_HW_write_dict(funcs[gvar.gmenu_func], funcs[gvar.gmenu_len])
            elif funcs[gvar.gmenu_op] == gvar.gRead_Req:
                sgRA_HW_read.setdefault(funcs[gvar.gmenu_func], []).append(funcs[gvar.gmenu_len])


def print_entry():
    if gvar.gWA_RA_mode == gvar.gWA_RA_mode_by_task:
        print("  [Task]")
    else:
        print("  [Task-PID]")
    #print("     |")
    print("     ")

def wa_main():
    """
    The WA(write amplification) is based on the below definition.
    https://en.wikipedia.org/wiki/Write_amplification
    its calculating method:

          data written to the hardware memory
    WA = ---------------------------------------
          data written by the host(user space)

    :param lines:
    :return:

    """
    print("")
    print("  -----------------[Write statistics]--------------------")
    print("  1.---[VFS_write] -- Data written through user space: ")
    for task in sgWA_VFS_write.keys():
        vfs_write = sum(sgWA_VFS_write[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
              (task, melib.bytes_to_mb_kb(vfs_write), len(sgWA_VFS_write[task])))

    print("  2.---[remap] -- Logical block address remaps to physical: ")

    for task in sgRemap_write.keys():
        remap_write = sum(sgRemap_write[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
              (task, melib.bytes_to_mb_kb(remap_write), len(sgRemap_write[task])))

    print("  3.---[HW write finished] ")

    for task in sgWA_HW_write.keys():
        hw_write = sum(sgWA_HW_write[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
              (task,  melib.bytes_to_mb_kb(hw_write), len(sgWA_HW_write[task])))

    print("")
    print("  -----------------[Read statistics]---------------------")
    print("  1.---[VFS_read] -- Data read through user space: ")
    #print_entry()
    for task in sgRA_VFS_read.keys():
        vfs_read = sum(sgRA_VFS_read[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
                  (task, melib.bytes_to_mb_kb(vfs_read),  len(sgRA_VFS_read[task])))

    print("  2.---[remap] -- Logical block address remaps to physical: ")
   # print_entry()
    for task in sgRemap_read.keys():
        remap_read = sum(sgRemap_read[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
              (task, melib.bytes_to_mb_kb(remap_read), len(sgRemap_read[task])))

    print("  3.---[HW read finished] ")
    #print_entry()
    for task in sgRA_HW_read.keys():
        hw_read = sum(sgRA_HW_read[task])
        print("       Task [%s]:    ---- [%s]:[%d]  " %
              (task, melib.bytes_to_mb_kb(hw_read),  len(sgRA_HW_read[task])))




