#!/usr/bin/env python
"""
this is a common library
"""

import sys
import os
import re
import collections
from pprint import *
import pickle

'''
special key name for the dictionary:
task: pid: cpu: timestamp: function: op: address: len
'''

DEBUG = 0
LogFD = 0
color_names = {
    'aliceblue':            '#F0F8FF',
    'antiquewhite':         '#FAEBD7',
    'aqua':                 '#00FFFF',
    'aquamarine':           '#7FFFD4',
    'azure':                '#F0FFFF',
    'beige':                '#F5F5DC',
    'bisque':               '#FFE4C4',
    'black':                '#000000',
    'blanchedalmond':       '#FFEBCD',
    'blue':                 '#0000FF',
    'blueviolet':           '#8A2BE2',
    'brown':                '#A52A2A',
    'burlywood':            '#DEB887',
    'cadetblue':            '#5F9EA0',
    'chartreuse':           '#7FFF00',
    'chocolate':            '#D2691E',
    'coral':                '#FF7F50',
    'cornflowerblue':       '#6495ED',
    'cornsilk':             '#FFF8DC',
    'crimson':              '#DC143C',
    'cyan':                 '#00FFFF',
    'darkblue':             '#00008B',
    'darkcyan':             '#008B8B',
    'darkgoldenrod':        '#B8860B',
    'darkgray':             '#A9A9A9',
    'darkgreen':            '#006400',
    'darkkhaki':            '#BDB76B',
    'darkmagenta':          '#8B008B',
    'darkolivegreen':       '#556B2F',
    'darkorange':           '#FF8C00',
    'darkorchid':           '#9932CC',
    'darkred':              '#8B0000',
    'darksalmon':           '#E9967A',
    'darkseagreen':         '#8FBC8F',
    'darkslateblue':        '#483D8B',
    'darkslategray':        '#2F4F4F',
    'darkturquoise':        '#00CED1',
    'darkviolet':           '#9400D3',
    'deeppink':             '#FF1493',
    'deepskyblue':          '#00BFFF',
    'dimgray':              '#696969',
    'dodgerblue':           '#1E90FF',
    'firebrick':            '#B22222',
    'floralwhite':          '#FFFAF0',
    'forestgreen':          '#228B22',
    'fuchsia':              '#FF00FF',
    'gainsboro':            '#DCDCDC',
    'ghostwhite':           '#F8F8FF',
    'gold':                 '#FFD700',
    'goldenrod':            '#DAA520',
    'gray':                 '#808080',
    'green':                '#008000',
    'greenyellow':          '#ADFF2F',
    'honeydew':             '#F0FFF0',
    'hotpink':              '#FF69B4',
    'indianred':            '#CD5C5C',
    'indigo':               '#4B0082',
    'ivory':                '#FFFFF0',
    'khaki':                '#F0E68C',
    'lavender':             '#E6E6FA',
    'lavenderblush':        '#FFF0F5',
    'lawngreen':            '#7CFC00',
    'lemonchiffon':         '#FFFACD',
    'lightblue':            '#ADD8E6',
    'lightcoral':           '#F08080',
    'lightcyan':            '#E0FFFF',
    'lightgoldenrodyellow': '#FAFAD2',
    'lightgreen':           '#90EE90',
    'lightgray':            '#D3D3D3',
    'lightpink':            '#FFB6C1',
    'lightsalmon':          '#FFA07A',
    'lightseagreen':        '#20B2AA',
    'lightskyblue':         '#87CEFA',
    'lightslategray':       '#778899',
    'lightsteelblue':       '#B0C4DE',
    'lightyellow':          '#FFFFE0',
    'lime':                 '#00FF00',
    'limegreen':            '#32CD32',
    'linen':                '#FAF0E6',
    'magenta':              '#FF00FF',
    'maroon':               '#800000',
    'mediumaquamarine':     '#66CDAA',
    'mediumblue':           '#0000CD',
    'mediumorchid':         '#BA55D3',
    'mediumpurple':         '#9370DB',
    'mediumseagreen':       '#3CB371',
    'mediumslateblue':      '#7B68EE',
    'mediumspringgreen':    '#00FA9A',
    'mediumturquoise':      '#48D1CC',
    'mediumvioletred':      '#C71585',
    'midnightblue':         '#191970',
    'mintcream':            '#F5FFFA',
    'mistyrose':            '#FFE4E1',
    'moccasin':             '#FFE4B5',
    'navajowhite':          '#FFDEAD',
    'navy':                 '#000080',
    'oldlace':              '#FDF5E6',
    'olive':                '#808000',
    'olivedrab':            '#6B8E23',
    'orange':               '#FFA500',
    'orangered':            '#FF4500',
    'orchid':               '#DA70D6',
    'palegoldenrod':        '#EEE8AA',
    'palegreen':            '#98FB98',
    'paleturquoise':        '#AFEEEE',
    'palevioletred':        '#DB7093',
    'papayawhip':           '#FFEFD5',
    'peachpuff':            '#FFDAB9',
    'peru':                 '#CD853F',
    'pink':                 '#FFC0CB',
    'plum':                 '#DDA0DD',
    'powderblue':           '#B0E0E6',
    'purple':               '#800080',
    'red':                  '#FF0000',
    'rosybrown':            '#BC8F8F',
    'royalblue':            '#4169E1',
    'saddlebrown':          '#8B4513',
    'salmon':               '#FA8072',
    'sandybrown':           '#FAA460',
    'seagreen':             '#2E8B57',
    'seashell':             '#FFF5EE',
    'sienna':               '#A0522D',
    'silver':               '#C0C0C0',
    'skyblue':              '#87CEEB',
    'slateblue':            '#6A5ACD',
    'slategray':            '#708090',
    'snow':                 '#FFFAFA',
    'springgreen':          '#00FF7F',
    'steelblue':            '#4682B4',
    'tan':                  '#D2B48C',
    'teal':                 '#008080',
    'thistle':              '#D8BFD8',
    'tomato':               '#FF6347',
    'turquoise':            '#40E0D0',
    'violet':               '#EE82EE',
    'wheat':                '#F5DEB3',
    'white':                '#FFFFFF',
    'whitesmoke':           '#F5F5F5',
    'yellow':               '#FFFF00',
    'yellowgreen':          '#9ACD32'
}

class StatClass:
    def __init__(self):
        self.missing_items = 0


class MultipleDimensionNestDict(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


def tree():
    return collections.defaultdict(tree)


class DefinedExcepton(Exception):
    def __init__(self, error):
        super().__init__(self)
        self.error = error

    def __str__(self):
        return self.error


def usage():
    print("""Usage: %s [<options>] <filename>
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
        --e2e <group mode>      
                    Print out IO performance key parameters based on the
                    input file from ftrace.
                    There are two kinds of group mode, event and request.
                    If specifying 'request', that will group each request.
                    If specifying 'event', that will just group each e2e.
                    
        --wa        Analyze the system level WA (write amplification)                        
        --protocol [<scsi|nvme>]
                        protocol analyzer.
        
        eg:
            ftparser -f ./ftrace.log --wa
    """ % os.path.basename(sys.argv[0]))
    sys.exit(1)


def me_dbg(msg):
    global DEBUG
    if DEBUG:
        print("Debug:" + msg)


def me_warning(msg):
    print("Warning! "+msg)
    if LogFD:
        print >> LogFD, "Warning! "+msg



def me_error(msg):
    print("Error!!! "+msg)
    if LogFD:
        print >> LogFD, "Error!!! "+msg

def me_pprint_dict_scream(dictionary):
    if isinstance(dictionary, dict):
        #pp = pprint.PrettyPrinter(indent=4)
        pprint(dictionary)
    else:
        me_warning("Not dict type %s" % type(dictionary))


def me_pprint_dict_file(file, dictionary):
    if isinstance(dictionary, dict):
        try:
            with open(file, 'wt') as out:
                #pp = pprint.PrettyPrinter(indent=2)
                pprint(dictionary, stream = out)
        except:
            print("Opening/writing file %s failed." % file)
            return
    else:
        me_warning("Not dict type %s" % type(dictionary))


def mkdir(path):
    dir_str = path
    dir_str = dir_str.strip()
    dir_str = dir_str.rstrip("\\")
    is_exist = os.path.exists(dir_str)
    if is_exist:
        return
    else:
        os.makedirs(dir_str)
        return


def me_pickle_save_obj(file, obj):
    try:
        f = open(file, 'w')
    except:
        print("Opening file failed."% file)
    try:
        pickle.dump(obj,f, 0)
    except:
        print("Pickle file %s failed."% file)
    f.close()

'''
usage :
    delimiter = "\s\("
    me_split(s, delimiter)
'''


def me_split(delimiter, s):
    symbol = "[" + delimiter + "]+"
    result = re.split(symbol, s)
    return [x for x in result if x]


def is_cpu_field_string(string):
    """
    :param string: the string contains CPU ID, such as [0000], [0001]. or some else.
    :return: True if the str is CPU string, else false.
    """
    if isinstance(string, str):
        if string.startswith('[') and string.endswith(']'):
            cpu_id = re.split(r"\[|\]", string)[1]
            if cpu_id.isdigit() and len(cpu_id) == 3:  # by default, the CPU Id length is 3
                return True
    return False


def where_is_cpu_field(parts):
    """
    :param parts: the list
    :return: the index of CPUID if found CPUID,else None
    Used to find out the index of CPU ID in the list
    """
    if isinstance(parts, list):
        for item in parts:
            if is_cpu_field_string(item):
                return parts.index(item)
    return None


def is_skip_this_line(line_str):
    # skip blank lines
    if not line_str.strip():
        return True
    # skip delimiter lines
    elif line_str.startswith(" -------------------"):
        return True
    # handle pid-change lines, currently  we just skip, FIXME
    elif line_str.find(" => ") != -1:
        return True
    # Just skip IRQ change now FIXME
    elif line_str.find("===>") != -1 or line_str.find("<===") != -1:
        me_dbg("IRQ entry/exit matched")
        return True
    else:
        return False


def bytes_to_mb_kb(bytes):
    if bytes > 1024 * 1024:
        return str(round(float(bytes) / 1048576, 3)) + ' MB'
    elif bytes > 1024:
        return str(round(float(bytes) / 1024, 3)) + ' KB'
    else:
        return str(bytes) + ' Bytes'
