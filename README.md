IOKPP front-end (I/O key performance parameter )
============
Free use of this software is granted under the terms of the GNU Public License (GPL).

IOkpp(IO key performance parameter) is a storage subsystem timing analysis tool,
it provides a non-invasive method to collect timing data on the Linux storage
subsystem from user space on path to the storage device. It consists of front-end
tool (parser) and back-end tool.
This tool is a front-end part,which runs on the target platform, and is used to
analyze/parse the log of IOKPP back-end tool, and provide the I/O performance
timing statistics. 
The back-end of IOKPP runs on the target machine side, which is used to install/enable
trace event, trigger Linux I/O request event and collect trace event log.


The key functions include:

1. Time consumption which costs from one event to another event
2. System layer WA(write amplification)
3. Time costs compare between Hardware data transfer and  software layers happened.
4. SCSI protocol analyzer
5. Multiple I/O requests distribution on the storage device
6. Time costs distribution on specified events

At the initial version, this front-end tool is purely developed by python.



Dependencies
============

 * python2
 * numpy
 * matplotlib

Install dependencies:
  sudo apt-get install python-numpy
  sudo apt-get install python-matplotlib

or 
  sudo pip install numpy
  sudo pip install matplotlib

Usage
============
    This program is to parse the log which came from ftrace or IOKPP back-end tool.
    Before using this tool, make sure your log contains these key items:
    [ TASK-PID   CPU#  TIMESTAMP  FUNCTION ].

    Options:
        -d/--debug  Print more information for debugging, this will be very noisy.
        -h/--help   Show this usage help.
        -V/v        Show version.
        --out <output file folder>
                    Specify the output directory

        -i <file>   Specify the input fil
        --split     Split original trace log into several file by PID
        --e2e <group mode>
                    Print out IO performance key parameters based on the
                    specified input log file.
                    There are two kinds of group mode, "event" and "request".

               --e2e request: The all events associated with one I/O request, will
                               be grouped together, then calculate each stage time
                               consumption.
               --e2e event:    This will just group the same e2e (from event A to
                               event B) together, and then calculate its time consumption.
        --start <start index>
                    Specify from which index the histogram/bar/distribution
                    chart start to show on output file.

        --end <end index>
                    Specify from which index the histogram/bar/distribution
                    chart stop to show on output file.

        --wa <pid|task>
                    Analyze the system level WA (write amplification)

        --protocol [<scsi|nvme>]
                    SCSI and NVMe protocol analyzer.
    Eg:
        1. Split the log into several file according to PID.
       	IOparser -i ftrace.log  --split
        2. Parse the log and show its record frm index 1 to 100
        IOparser -i ftrace.log  --e2e event --start 1 --end 100 --out ./out
        3. Calculate the WA in the log
        IOparser -i ftrace.log  --wa task


TODO list
============
 * Add SCSI protocol analyzer
    - 1. multiple tasks distribution
    - 2. accessing chunk size distribution
    - 3. LBA


FIXME list
============
 * None


Developers
============
 Bean Huo beanhuo@micron.com

