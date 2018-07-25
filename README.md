Ftparser (ftrace parser) or IOKPP (I/O key performance parameter)
============
Free use of this software is granted under the terms of the GNU Public License (GPL).

This tool is used to analyze/parse the linux function trace (ftrace) log,
and provide the I/O performance related parameters.

At the initial version, this tool is purely developed by python and mainly based
on the ftrace log.
About ftrace (https://elinux.org/Ftrace).
============

Dependencies
============

 * python2
 * numpy
 * matplotlib


Usage
=====
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

TODO
====
 * How to fix the condition that there are some requests missing event points
 * Add system level WA analyzer
 * Add SCSI protocol analyzer
    - 1. multiple tasks distribution
    - 2. accessing chunk size distribution
    - 3. LBA
 * Add the support for the Sync I/O read
 * Add the support for the read-ahead
Known Issues
FIXME
=============
 *


Developers
=============
 Bean Huo beanhuo@micron.com

