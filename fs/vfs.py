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


def vfs_functions2dict_parser(funcs):
    ret_dict = {}
    funcs_list = re.split(r"[:()\s]+", funcs)


    if funcs_list[0] in conf.gE2E_events_funcs_filter_dict['vfs']:
        ret_dict[gvar.gmenu_func] = funcs_list[0]

        if ret_dict[gvar.gmenu_func] == 'sys_read':
            ret_dict[gvar.gmenu_op] = gvar.gRead_Req
        elif ret_dict[gvar.gmenu_func] == 'sys_write':
            ret_dict[gvar.gmenu_op] = gvar.gWrite_Req
        else:
            ret_dict[gvar.gmenu_op] = None

        if '->' in funcs_list:
            if funcs_list[funcs_list.index('->') + 1].startswith("0x"):
                ret_dict[gvar.gmenu_len] = funcs_list[funcs_list.index('->') + 1].split('x')[1]  # remove 0x, then get
            else:
                ret_dict[gvar.gmenu_len] = funcs_list[funcs_list.index('->') + 1]
            ret_dict[gvar.gmenu_events] = gvar.gReqEvent_end
        elif 'count' in funcs_list:
            if funcs_list[funcs_list.index('count') + 1].startswith("0x"):
                ret_dict[gvar.gmenu_len] = funcs_list[funcs_list.index('count') + 1].split('x')[1]  # remove 0x, then get

            else:
                ret_dict[gvar.gmenu_len] = funcs_list[funcs_list.index('count') + 1]
            ret_dict[gvar.gmenu_events] = gvar.gReqEvent_start
        ret_dict[gvar.gmenu_len] = int(ret_dict[gvar.gmenu_len], 16)  # hexadecimal data length transfer to decimalism
        return ret_dict
    else:
        return None
