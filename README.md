# B A D B T | Bluetooth Ducky

## Prerequisites:
- Python3
- python3-bluez

## Setup:
- Backup existing /usr/lib/systemd/system/bluetooth.service and place bluetooth.service to the same path
- Copy org.thanhle.btkbservice.conf to /etc/dbus-1/system.d
- Execute `sudo systemctl daemon-reload`
- Execute `sudo systemctl restart bluetooth`

```
Usage:
        python btk_server.py -n [BT_NAME] -i [INTERFACE]

        Default Values:
                BT_NAME:        Keyboard
                INTERFACE:      hci0

```
- Execute `sudo python btk_server.py` to start the server.
- Execute `python ducky.py -d [rubberducky_script_path]` to inject rubberducky script.
