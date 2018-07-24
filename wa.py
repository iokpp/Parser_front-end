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

#{'task name': {4096, ...}, ...}
sgWA_VFS_write = dict()
#{'HW name': {4096, ....}}
sgSA_HW_write = dict()

#{'HW name': {4096, ....}}
sgRemap_write = dict()

def add_to_VFS_write_dict(task_str, bytes_len):
    if not sgWA_VFS_write:
        sgWA_VFS_write[task_str] = [bytes_len]
    elif task_str not in sgWA_VFS_write.keys():
        sgWA_VFS_write[task_str] = [bytes_len]
    elif task_str in sgWA_VFS_write.keys():
        sgWA_VFS_write[task_str].append(bytes_len)


def add_to_HW_write_dict(task_str, bytes_len):
    if not sgSA_HW_write:
        sgSA_HW_write[task_str] = [bytes_len]
    elif task_str not in sgSA_HW_write.keys():
        sgSA_HW_write[task_str] = [bytes_len]
    elif task_str in sgSA_HW_write.keys():
        sgSA_HW_write[task_str].append(bytes_len)

def add_remap_write_dict(task_str, bytes_len):
    if not sgRemap_write:
        sgRemap_write[task_str] = [bytes_len]
    elif task_str not in sgRemap_write.keys():
        sgRemap_write[task_str] = [bytes_len]
    elif task_str in sgRemap_write.keys():
        sgRemap_write[task_str].append(bytes_len)

def add_to_wa_property_tree(funcs):

    if funcs:
        if funcs[gvar.gmenu_func] == 'sys_write':
            if funcs[gvar.gmenu_events] == gvar.gReqEvent_start:
                add_to_VFS_write_dict(funcs[gvar.gmenu_task], funcs[gvar.gmenu_len])

        if funcs[gvar.gmenu_func] == 'block_bio_remap':
            if funcs[gvar.gmenu_op] == gvar.gWrite_Req:
                add_remap_write_dict(funcs[gvar.gmenu_task], funcs[gvar.gmenu_len])

        if funcs[gvar.gmenu_func] in gvar.gWA_HW_transfer_completion_flags:
            if funcs[gvar.gmenu_op] == gvar.gWrite_Req:
                add_to_HW_write_dict(funcs[gvar.gmenu_func], funcs[gvar.gmenu_len])


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
    print(" ---------------------------------1------------------------------------")
    for task in sgWA_VFS_write.keys():
        vfs_write = sum(sgWA_VFS_write[task])
        print("    Data written through user space task [%s]:[%d items] [%s] " %
                  (task, len(sgWA_VFS_write[task]), melib.bytes_to_mb_kb(vfs_write)))

    print(" ---------------------------------2------------------------------------")
    for task in sgRemap_write.keys():
        remap_write = sum(sgRemap_write[task])
        print("    Remap on task (%s):[%d items] [%s]." %
              (task, len(sgRemap_write[task]), melib.bytes_to_mb_kb(remap_write)))

    print(" ---------------------------------3------------------------------------")
    for task in sgSA_HW_write.keys():
        hw_write = sum(sgSA_HW_write[task])
        print("    Data written through (%s):[%d items] [%s]." %
              (task, len(sgSA_HW_write[task]), melib.bytes_to_mb_kb(hw_write)))




