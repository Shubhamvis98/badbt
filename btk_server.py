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

# No PIN and auto Accept pairing fix
# Bluetoot Classic NoInputNoOutputAgent - return UUID Classic
# Select Class Of Device (CoD)

DEVICE_COD = {
    # ===== Android / Generic Devices =====
    "carkit":      '0x420408',  # MAP/PBAP/HFP-enabled Car profile
    "keyboard":    '0x000540',  # Peripheral / Keyboard
    "mouse":       '0x000580',  # Peripheral / mouse
    "airbuds":     '0x240418',  # Audio/Video + Headset + CarKit/Handsfree
    "audio":       '0x240404',  # Generic audio sink (A2DP/AVRCP)
    "smartwatch":  '0x007004',  # Wearable (Watch)
    "healthband":  '0x007008',  # Wearable (Health tracker)
    "smartphone":  '0x020C00',  # Phone / Smartphone

    # ===== Apple variants (Apple uses slightly different CoDs) =====
    "iphone":      '0x020C00',  # Same as smartphone (Apple does not special-code iPhone)
    "airpods":     '0x240418',  # Handsfree + Audio (same as buds)
    "applewatch":  '0x007004',  # Same as smartwatch
}

device_type = "audio"

# No PIN Just Work Agent
class NoInputNoOutputAgent(dbus.service.Object):
    def __init__(self, bus, path):
        super().__init__(bus, path)
        self.bus = bus

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Release(self):
        print("[AGENT] Released")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestPinCode(self, device):
        print("[AGENT] RequestPinCode -> Reject")
        raise dbus.DBusException("org.bluez.Error.Rejected", "No pin code supported")

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        print("[AGENT] RequestPasskey -> Reject")
        raise dbus.DBusException("org.bluez.Error.Rejected", "No passkey supported")

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        # Auto-accept Just Works pairing
        print(f"[AGENT] RequestConfirmation for {device} passkey={passkey} -> AUTO-ACCEPT")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
    def DisplayPasskey(self, device, passkey):
        # Phone may ask to *display* passkey — we ignore it silently
        print(f"[AGENT] DisplayPasskey {device} passkey={passkey} (ignored)")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        # Phone may ask to *display* pincode — we ignore it silently
        print(f"[AGENT] DisplayPinCode {device} pincode={pincode} (ignored)")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        # Allow any service by default (not related to PIN)
        print(f"[AGENT] AuthorizeService {device} uuid={uuid} -> ALLOW")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
    def RequestAuthorization(self, device):
        print(f"[AGENT] RequestAuthorization for {device} -> allow")
        return

    @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
    def Cancel(self):
        print("[AGENT] Cancel called")

# UUID Fix
# OSError: [Errno 98] Address already in use

logging.basicConfig(level=logging.DEBUG)

class BTKbDevice():
    # define some constants
    P_CTRL = 17  # Service port - must match port configured in SDP record
    P_INTR = 19  # Interrupt port - must match port configured in SDP record
    # dbus path of the bluez profile we will create
    # file path of the sdp record to load
    SDP_RECORD_PATH = sys.path[0] + "/sdp_record.xml"
    # UUID value: [SIG] Human Interface Device (HID) Profile - [Protocol] Bluetooth BR/EDR (Bluetooth Classic)
    UUID = "00001124-0000-1000-8000-00805f9b34fb"
    #UUID = "0000110B-0000-1000-8000-00805f9b34fb"

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
        print("3. Configuring Device name: \033[0;92m" + self.bt_name + "\033[0m")
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
        # retrieve a proxy for the bluez agent and profile interface
        bus = dbus.SystemBus()

        # -----------------  Registering Custom DefaultAgent NoInputNoOutput ------------------
        print("4. Registering NoInputNoOutput agent...")
        AGENT_PATH = f"/org/bluez/agentNoIO"
        agent = NoInputNoOutputAgent(bus, AGENT_PATH)

        agent_manager = dbus.Interface(bus.get_object(
            "org.bluez", "/org/bluez"), "org.bluez.AgentManager1")

        # Register the agent
        agent_manager.RegisterAgent(AGENT_PATH, "NoInputNoOutput")

        # Make the Agent the global default (required for NO-PIN pairing)
        try:
            print("    Requesting Default Agent...")
            agent_manager.RequestDefaultAgent(AGENT_PATH)
            print("\033[0;92m    Custom agent registered\033[0m")
        except Exception as e:
            print("[WARN] RequestDefaultAgent failed (maybe another default agent exists):", e)
        # -------------------------------------------------------------------------------------

        print("5. Configuring Bluez Profile")
        # setup profile options
        service_record = self.read_sdp_service_record()
        opts = {
            "AutoConnect": True,
            "ServiceRecord": service_record,
            "RequireAuthentication": False,
            "RequireAuthorization": False,
            "RequireSecurity": False
        }

        manager = dbus.Interface(bus.get_object(
            "org.bluez", "/org/bluez"), "org.bluez.ProfileManager1")
        manager.RegisterProfile("/org/bluez/" + self.if_name, BTKbDevice.UUID, opts)
        print("7. Profile registered ")
        os.system("hciconfig " + self.if_name + " class " + self.if_class)

    # read and return an sdp record from a file
    def read_sdp_service_record(self):
        print("6. Reading service record")
        try:
            fh = open(BTKbDevice.SDP_RECORD_PATH, "r")
        except:
            sys.exit("Could not open the sdp record. Exiting...")
        return fh.read()

    # listen for incoming client connections
    def listen(self):
        print("\033[0;33m8. Waiting for connections\033[0m")
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

    bt_name = device_type
    if_name = "hci0"
    sopts = 'hn:i:c:a'
    #if_class = '0x000540'
    if_class = DEVICE_COD[device_type]
    if_addr = '22:22:EA:CF:3C:1E'
    opts, args = getopt.getopt(sys.argv[1:], sopts)

    for opt, arg in opts:
        if opt == '-h':
            print(f'\nUsage:\n\tpython {sys.argv[0]} -n [BT_NAME] -i [INTERFACE] -c [CLASS] -a [ADDRESS]\n\n\tDefault Values:\n\t\tBT_NAME:\t{bt_name}\n\t\tINTERFACE:\t{if_name}\n\t\tCLASS:\t{if_class}\n\t\tADDRESS:\t{if_addr}')
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
