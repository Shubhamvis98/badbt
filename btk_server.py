#!/usr/bin/python3
#
# Bluetooth keyboard/Mouse emulator DBUS Service
#

from __future__ import absolute_import, print_function
from optparse import OptionParser, make_option
import os
import sys
import uuid
import dbus
import dbus.service
import dbus.mainloop.glib
import time
import socket
import getopt
from gi.repository import GLib
from dbus.mainloop.glib import DBusGMainLoop
import logging
from logging import debug, info, warning, error
import bluetooth
from bluetooth import *
import subprocess

# TODO   File "/root/badbt/btk_server.py", line 166, in <module>
#     myservice = BTKbService()
#                 ^^^^^^^^^^^^^
#   File "/root/badbt/btk_server.py", line 132, in __init__
#     self.device.listen()
#   File "/root/badbt/btk_server.py", line 97, in listen
#     self.scontrol.bind((socket.BDADDR_ANY, self.P_CTRL))
# OSError: [Errno 98] Address already in use

logging.basicConfig(level=logging.DEBUG)

class BTKbDevice():
    # define some constants
    P_CTRL = 17  # Service port - must match port configured in SDP record
    P_INTR = 19  # Interrupt port - must match port configured in SDP record
    # dbus path of the bluez profile we will create
    # file path of the sdp record to load
    SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
    # UUID value must match Generic Attribute Profile UUID
    UUID = subprocess.getoutput("bluetoothctl show | awk '/Generic Attribute Profile/' | awk -F'[()]' '{print $2}'")

    def __init__(self, bt_name, if_name):
        print("2. Setting up BT device")
        self.bt_name = bt_name
        self.if_name = if_name
        self.MY_ADDRESS = if_addr
        self.if_class = if_class
        self.init_bt_device()
        self.init_bluez_profile()

    # configure the bluetooth hardware device
    def init_bt_device(self):
        print("3. Configuring Device name: " + self.bt_name)
        # temporary patch
        with open('/etc/init.d/bluetooth') as f:
            if 'NOPLUGIN_OPTION=""' in f.read():
                print('** Fixing bluetooth service patch and restarting.. **'),
                os.system("sed -i '/NOPLUGIN_OPTION=\"\"/d' /etc/init.d/bluetooth && service bluetooth restart")
        # set the device class to a keybord and set the name
        os.system("hciconfig " + self.if_name + " up")
        os.system("hciconfig " + self.if_name + " name \"" + self.bt_name + "\"")
        # make the device discoverable
        os.system("hciconfig " + self.if_name + " piscan")

    # set up a bluez profile to advertise device capabilities from a loaded service record
    def init_bluez_profile(self):
        print("4. Configuring Bluez Profile")
        # setup profile options
        service_record = self.read_sdp_service_record()
        opts = {
            "AutoConnect": True,
            "ServiceRecord": service_record
        }
        # retrieve a proxy for the bluez profile interface
        bus = dbus.SystemBus()
        manager = dbus.Interface(bus.get_object(
            "org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile("/org/bluez/" + self.if_name, BTKbDevice.UUID, opts)
        print("6. Profile registered ")
        os.system("hciconfig " + self.if_name + " class " + self.if_class)

    # read and return an sdp record from a file
    def read_sdp_service_record(self):
        print("5. Reading service record")
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        except:
            sys.exit("Could not open the sdp record. Exiting...")
        return fh.read()

    # listen for incoming client connections
    def listen(self):
        print("\033[0;33m7. Waiting for connections\033[0m")
        self.scontrol = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)  # BluetoothSocket(L2CAP)
        self.sinterrupt = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)  # BluetoothSocket(L2CAP)
        self.scontrol.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sinterrupt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # bind these sockets to a port - port zero to select next available
        self.scontrol.bind((socket.BDADDR_ANY, self.P_CTRL))
        self.sinterrupt.bind((socket.BDADDR_ANY, self.P_INTR))

        # Start listening on the server sockets
        self.scontrol.listen(5)
        self.sinterrupt.listen(5)

        self.ccontrol, cinfo = self.scontrol.accept()
        print (
            "\033[0;32mGot a connection on the control channel from %s \033[0m" % cinfo[0])

        self.cinterrupt, cinfo = self.sinterrupt.accept()
        print (
            "\033[0;32mGot a connection on the interrupt channel from %s \033[0m" % cinfo[0])

    # send a string to the bluetooth host machine
    def send_string(self, message):
        try:
            self.cinterrupt.send(bytes(message))
        except OSError as err:
            error(err)


class BTKbService(dbus.service.Object):

    def __init__(self, bt_name, if_name):
        print("1. Setting up service")
        # set up as a dbus service
        bus_name = dbus.service.BusName(
            "org.thanhle.btkbservice", bus=dbus.SystemBus())
        dbus.service.Object.__init__(
            self, bus_name, "/org/thanhle/btkbservice")
        # create and setup our device
        self.device = BTKbDevice(bt_name, if_name)
        # start listening for connections
        self.device.listen()

    @dbus.service.method('org.thanhle.btkbservice', in_signature='yay')
    def send_keys(self, modifier_byte, keys):
        print("Get send_keys request through dbus")
        print("key msg: ", keys)
        state = [ 0xA1, 1, 0, 0, 0, 0, 0, 0, 0, 0 ]
        state[2] = int(modifier_byte)
        count = 4
        for key_code in keys:
            if(count < 10):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)

    @dbus.service.method('org.thanhle.btkbservice', in_signature='yay')
    def send_mouse(self, modifier_byte, keys):
        state = [0xA1, 2, 0, 0, 0, 0]
        count = 2
        for key_code in keys:
            if(count < 6):
                state[count] = int(key_code)
            count += 1
        self.device.send_string(state)


# main routine
if __name__ == "__main__":
    if not os.geteuid() == 0:
        sys.exit("[!]Run as root")

    MY_DEV_NAME = "Keyboard"
    bt_name = MY_DEV_NAME
    if_name = 'hci0'
    sopts = 'hn:i:c:a'
    if_class = '0x000540'
    if_addr = '22:22:EA:CF:3C:1E'
    opts, args = getopt.getopt(sys.argv[1:], sopts)

    for opt, arg in opts:
        if opt == '-h':
            print(f'\nUsage:\n\tpython {sys.argv[0]} -n [BT_NAME] -i [INTERFACE] -i [CLASS] -a [ADDRESS]\n\n\tDefault Values:\n\t\tBT_NAME:\t{bt_name}\n\t\tINTERFACE:\t{if_name}\n\t\tCLASS:\t{if_class}\n\t\tADDRESS:\t{if_addr}')
            sys.exit()
        elif opt == '-n':
            bt_name = arg
        elif opt == '-i':
            if_name = arg
        elif opt == '-c':
            if_class = arg
        elif opt == '-a':
            if_addr = arg

    try:
        DBusGMainLoop(set_as_default=True)
        myservice = BTKbService(bt_name, if_name)
        loop = GLib.MainLoop()
        loop.run()
    except KeyboardInterrupt:
        sys.exit()
