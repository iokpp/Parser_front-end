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
from lib import *
from gvar import *


def ext4_functions2dict_parser(funcs):
    ret_dict = {}
    funcs_list = re.split(r"[:()\s]+", funcs)

    if funcs_list[0] in gE2E_events_funcs_filter_dict['ext4']:
        ret_dict[gmenu_func] = funcs_list[0]

        if ret_dict[gmenu_func] in gFuns_dict['ext4']:
            # this is just a function trace log
            ret_dict[gmenu_events] = ret_dict[gmenu_func]
        elif ret_dict[gmenu_func] in gEvents_dict['ext4']:
            # this is a block event, need to further parser.
            # but currently, we only return function name
            ret_dict[gmenu_events] = ret_dict[gmenu_func]

        if "write" in funcs:
            ret_dict[gmenu_op] = gWrite_Req
        elif "read" in funcs:
            ret_dict[gmenu_op] = gRead_Req
        else:
            ret_dict[gmenu_op] = None

        ret_dict[gmenu_len] = None

        return ret_dict
    else:
        return None
