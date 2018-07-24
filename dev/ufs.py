#!/usr/bin/python
# # !/usr/bin/env python
"""
Copyright 2018 Micron Inc. Munich
"""


import sys
import os
import melib

SCSI_BLOCK_SIZE_BYTE = melib.gSCSI_LogicalBlockSize_Bytes
SECTOR_SIZE_BYTE = melib.gLogicalSectorSize_Bytes


sgVFS_EXT4 =\
    ['sys_read',    # vfs
     'generic_file_read_iter']  # ext4 read start

sgBlk =\
    ['block_bio_remap',
     'block_bio_queue',
     'block_getrq',
     'block_rq_insert',
     'block_rq_issue',
     'block_rq_complete']

sgPlug_unPlug =\
    ['block_unplug',
     'block_plug']


def io_kpp_main(lines):
    return 1