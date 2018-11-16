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

import gvar
import conf
import csv
from lib import melib

sgPtcl_output_dir = ''

'''
sgPtcl_raw_data is three-dimension nested dictionary.
in which, contains:
sgPtcl_raw_data[protocol][recode index][chunk] = 11332,
sgPtcl_raw_data[protocol][recode index][lba] = 11332,
sgPtcl_raw_data[protocol][recode index][I/O] = read/write,
sgPtcl_raw_data[protocol][recode index][event] = dispatch/done,
'''
sgPtcl_raw_data = melib.MultipleDimensionNestDict()

def add_to_ptcl_property_tree(func_dict):
    # fill in the protocol layer infor data structure
    if func_dict[gvar.gmenu_events] in conf.gPtcl_trace_points[gvar.gPtcl_mode]:
        index = 1
        op = func_dict.get(gvar.gmenu_op)
        bytes = func_dict.get(gvar.gmenu_len)
        lba = func_dict.get(gvar.gmenu_lba)
        event = func_dict.get(gvar.gmenu_events)
        time = func_dict.get(gvar.gmenu_time)

        if sgPtcl_raw_data:
            index = list(sgPtcl_raw_data[gvar.gPtcl_mode].keys())[-1]
            index = index + 1
        sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gmenu_len] = bytes
        sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gmenu_lba] = lba
        sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gmenu_op] = op
        sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gmenu_time] = time

        if gvar.gPtcl_mode == gvar.gPtcl_SCSI and\
                event in conf.gPtcl_trace_points[gvar.gPtcl_SCSI]:
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_channel] = func_dict.get(gvar.gScsi_channel)
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_lun] = func_dict.get(gvar.gScsi_lun)
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_host_no] = func_dict.get(gvar.gScsi_host_no)
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_id] = func_dict.get(gvar.gScsi_id)
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_cmd] = func_dict.get(gvar.gScsi_cmd)
            sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_raw] = func_dict.get(gvar.gScsi_raw)
            if event == 'scsi_dispatch_cmd_start':
                sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_event] = 'dispatch'
            elif event == 'scsi_dispatch_cmd_done':
                sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_event] = 'completed'
            else:
                sgPtcl_raw_data[gvar.gPtcl_mode][index][gvar.gScsi_event] = 'Unknown'


def save_result_into_csv():
    if sgPtcl_raw_data:
        csv_file = sgPtcl_output_dir + '/' + gvar.gPtcl_mode + '.csv'
        fd = open(csv_file, "wb")
        csv_writer = csv.writer(fd, dialect="excel")
        head_title = ['No.', gvar.gmenu_time]

        if gvar.gPtcl_mode == gvar.gPtcl_SCSI:
            scsi_title = [gvar.gScsi_event, gvar.gScsi_cmd, gvar.gScsi_host_no, gvar.gScsi_channel, gvar.gScsi_id,
                          gvar.gScsi_lun, gvar.gmenu_lba, gvar.gmenu_len, gvar.gScsi_raw]
            head_title = head_title + scsi_title
        csv_writer.writerow(head_title)

        for index in list(sgPtcl_raw_data[gvar.gPtcl_mode].keys()):
            line = [index]

            for i in range(1, len(head_title)):
                line.append(sgPtcl_raw_data[gvar.gPtcl_mode][index][head_title[i]])
            csv_writer.writerow(line)


def ptcl_main(original_lines, opts):

    global sgPtcl_output_dir
    sgPtcl_output_dir = gvar.gOutput_Dir_Default + '/ptcl/'
    melib.mkdir(sgPtcl_output_dir)

    if sgPtcl_raw_data:
        save_result_into_csv()
        melib.me_pprint_dict_file(sgPtcl_output_dir + '00-ptcl-Raw-Data.log',
                                  sgPtcl_raw_data)

