#!/usr/bin/python3

from send_string import BtkStringClient
from time import sleep
import keymap
import getopt
import sys
import os


def modgen(keys):
    tmp = [0, 0, 0, 0, 0, 0, 0, 0]

    tmp[0] = 1 if ("RIGHTMETA") in keys else 0
    tmp[1] = 1 if ("RIGHTALT") in keys else 0
    tmp[2] = 1 if ("RIGHTSHIFT") in keys else 0
    tmp[3] = 1 if ("RIGHTCTRL") in keys else 0
    tmp[4] = 1 if ("GUI" or "META" or "LEFTMETA") in keys else 0
    tmp[5] = 1 if ("ALT" or "LEFTALT") in keys else 0
    tmp[6] = 1 if ("SHIFT" or "LEFTSHIFT") in keys else 0
    tmp[7] = 1 if ("CTRL" or "LEFTCTRL") in keys else 0

    return tmp

def f_word(word, line):
    if(word == 'REM' or word == '#'):
      print('COMMENT')

    elif(word == 'STRING'):
        ducky.send_string(txt[line][7:])
    
    elif(word == 'DELAY'):
        sleep(DEFAULT_DELAY/1000) if len(txt[line]) == 5 else sleep(int(txt[line][6:])/1000)

    elif(f'KEY_{word}' in keymap.keytable):
        tmpm = modgen(txt[line].split()[:-1])
        tmpk = txt[line].split()[-1].upper()
        ducky.send_key_down(keymap.keytable[f'KEY_{tmpk}'], tmpm)
        ducky.send_key_up()
    
    else:
        print('NOT FOUND: '+ word)


if __name__ == "__main__":
    if not os.geteuid() == 0:
        sys.exit("[!]Run as root")

    sopts = 'hd:'
    opts, args = getopt.getopt(sys.argv[1:], sopts)

    for opt, arg in opts:
        if opt == '-h':
            print(f'\nUsage:\n\tpython {sys.argv[0]} -d [DUCKY_TXT]')
            sys.exit()
        elif opt == '-d':
            ducky = arg

        with open(ducky, 'r') as f:
            txt = f.readlines()

        for i in range(len(txt)):
            txt[i] = txt[i].strip()

        ducky = BtkStringClient()

        for line in range(len(txt)):
            if txt[line]:
                f_word(txt[line].split()[0], line)
