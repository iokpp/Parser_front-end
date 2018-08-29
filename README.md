IOKPP front-end (I/O key performance parameter ) or Ftparser (ftrace parser)
============
Free use of this software is granted under the terms of the GNU Public License (GPL).

This tool is a front-end part of IOKPP, used to analyze/parse the trace log of IOKPP back-end tool,
and provide the I/O performance related parameters. The back-end of IOKPP runs on the target machine
side, which is used to trigger Linux I/O request event  and collect trace event log, and the front-end
tool run on the user end PC.

The key functions include:

1. Time consumption which costs from one event to another event
2. System layer WA(write amplification)
3. Time costs compare between Hardware data transfer and  software layers happened.
4. SCSI protocol analyzer
5. Multiple I/O requests distribution on the storage device
6. Time costs distribution on specified events

At the initial version, this tool is purely developed by python and mainly based
on the ftrace log.
About ftrace (https://elinux.org/Ftrace).


Dependencies
============

 * python2
 * numpy
 * matplotlib



Usage
============
 eg: ftparser -i ftrace_output_file.log --e2e

    This program parses the output from the linux function trace (ftrace)
    Options:
        -d, --debug Print more information for debugging, this will be very noisy.
        -k, --keep  Don't delete the files created
        -h, --help  Show this usage help.
        -V/v, --version   Show version information.
        --out <output file folder>  specify the output directory
        -i <file>   Specify the ftrace log, you can use trace-c.sh and
                    trace-cmd easily to get this log.
        --split     Split original trace log into several file by PID
                      eg: ftparser -f ftrace.log --split
        --e2e       Print out IO performance key parameters based on the
                    input file from ftrace.
        --wa        Analyze the system level WA (write amplification)
        --protocol [<scsi|nvme>]
                        protocol analyzer.

        eg:
            ftparser -f ./ftrace.log --wa


TODO list
============
 * Add SCSI protocol analyzer
    - 1. multiple tasks distribution
    - 2. accessing chunk size distribution
    - 3. LBA


FIXME list
============
 * Fix the condition that there are some requests missing event points


Developers
============
 Bean Huo beanhuo@micron.com

