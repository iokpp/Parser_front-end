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

sgProtocol_output_dir = ''

SCSI_BLOCK_SIZE_BYTE = gvar.gSCSI_LogicalBlockSize_Bytes
SECTOR_SIZE_BYTE = gvar.gLogicalSectorSize_Bytes

'''
The opened tasks list, contains the count of opened
task in the device along the time. eg: [1,2,546,...]
'''
sgOpened_tasks_list = []


'''
sgRequest_counter_per_pid_op is three-dimension nested dictionary.
in which, contains the quantity of request associated with certain
PID, operation and chunk size.
eg: sgRequest_counter_per_pid_op[pid][op][chunk] = 11332,
'''
sgRequest_counter_per_pid_op = melib.MultipleDimensionNestDict()


def ptcl_main(original_lines, opts):

    sgProtocol_output_dir = gvar.gOutput_Dir_Default + '/protocol/'
    melib.mkdir(gvar.sgProtocol_output_dir)

    print(opts)
