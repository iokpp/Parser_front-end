
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
gEvents_dict =\
    {'vfs': ['sys_write',
             'sys_read'
             ],
     'ext4': ['ext4_direct_IO_enter',
              'ext4_direct_IO_exit',
              'ext4_sync_file_enter',
              'ext4_sync_file_exit',
              'ext4_da_write_begin',
              'ext4_da_write_end',
              'ext4_writepages',
              'ext4_writepages_result',
              'ext4_es_lookup_extent_enter',
              'ext4_es_lookup_extent_exit'
              ],
     'block': ['block_bio_remap',
               'block_bio_queue',
               'block_getrq',
               'block_plug',
               'block_unplug',
               'block_rq_insert',
               'block_rq_issue',
               'block_rq_complete'
               ],
     'scsi': ['scsi_dispatch_cmd_start',
              'scsi_dispatch_cmd_done'
              ],
     'dev': ['none'],
     'irq': ['irq_handler_entry',
             'irq_handler_exit'
             ]
     }

gFuns_dict =\
    {'vfs': ['none'
             ],
     'ext4': ['ext4_file_write_iter',
              '__generic_file_write_iter',
              'generic_perform_write',
              'generic_file_read_iter'
              ],
     'block': ['none'
               ],
     'scsi': ['scsi_queue_rq',
              'scsi_dma_map',
              'scsi_dma_unmap'
              ],
     'dev': ['ufshcd_intr'],
     'irq': ['none']
     }

gE2E_events_funcs_filter_dict = {
        'vfs': [
                'sys_write(fd:',
                'sys_write',
                'sys_read(fd:',
                'sys_read'
               ],
        'ext4': [
                 'ext4_file_write_iter',
                 'ext4_sync_file_enter',
                 'ext4_writepages',
                 'ext4_da_write_pages',
                 'ext4_sync_file_exit',
                 'ext4_writepages_result',
                 'generic_file_read_iter',
                 'ext4_direct_IO_enter',
                 'ext4_direct_IO_exit'
                ],
        'block': [
                 'block_bio_remap',
                 'block_bio_queue',
                 'block_getrq',
                 'block_plug',
                 'block_unplug',
                 'block_rq_insert',
                 'block_rq_issue',
                 'block_rq_complete',
                 ],
        'scsi': [
                 'scsi_dispatch_cmd_start',
                 'scsi_dispatch_cmd_done',
                ],
        'others': [

            ],
}


#
#
#
# User configure lists start
"""
Here is the list of events supported so far:
#VFS layer
    gvar.gReqEvent_start,
    gvar.gReqEvent_end,
#Ext4 FS
     'ext4_file_write_iter',
     'ext4_sync_file_enter',
     'ext4_sync_file_exit',
     'ext4_direct_IO_enter',
     'generic_file_read_iter',
     'ext4_direct_IO_enter',
     'ext4_direct_IO_exit'
 #Block Layer
     'block_bio_remap',
     'block_bio_queue',
     'block_getrq',
     'block_plug',
     'block_unplug',
     'block_rq_insert',
     'block_rq_issue',
     'block_rq_complete',
 #SCSI layer
     'scsi_dispatch_cmd_start',
     'scsi_dispatch_cmd_done'
"""

gE2E_trace_points_in_one_request = [
    # ----------VFS----------
    gvar.gReqEvent_start,
    gvar.gReqEvent_end,
    # ----------block--------
    # ---------SCSI---------
    'scsi_dispatch_cmd_start',
    'scsi_dispatch_cmd_done'
]

gE2E_filter_in_one_request = [
    gvar.gReqEvent_start + '-' + gvar.gReqEvent_end,
    gvar.gReqEvent_start + '-' + 'scsi_dispatch_cmd_start',
    'scsi_dispatch_cmd_start-scsi_dispatch_cmd_done',
    'scsi_dispatch_cmd_done-' + gvar.gReqEvent_end
]

gE2E_durations_trace = [
    gvar.gReqEvent_start + '-' + gvar.gReqEvent_end,
    gvar.gReqEvent_start + '-' + 'block_bio_remap',
    'block_bio_remap-block_rq_issue',
    'block_rq_issue-scsi_dispatch_cmd_start',
    'scsi_dispatch_cmd_start-scsi_dispatch_cmd_done',
    'scsi_dispatch_cmd_done-block_rq_complete',
    'block_rq_complete-' + gvar.gReqEvent_end
]

gE2E_HW_transfer_duration_define = (
    'scsi_dispatch_cmd_start-scsi_dispatch_cmd_done'
)

gWA_HW_transfer_completion_flags = [
    'scsi_dispatch_cmd_done'
]

gPtcl_trace_points = {
    gvar.gPtcl_SCSI: [
        'scsi_dispatch_cmd_start',
        'scsi_dispatch_cmd_done'
    ],
    gvar.gPtcl_UFS: [

    ]
}

gIO_event_trace_points = {
    'open':
        [
        'scsi_dispatch_cmd_start',
        ],
    'close':
        [
        'scsi_dispatch_cmd_done',
        ]
}
# User defined list end
