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
```
Usage:
        python ducky.py -d [DUCKY_TXT]
```
- In another terminal, run `sudo python ducky.py -d rubberducky_input.txt` to inject the keystrokes.