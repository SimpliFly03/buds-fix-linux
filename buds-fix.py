import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GObject, GLib

import subprocess
import time

LOG_LEVEL = logging.INFO
#LOG_LEVEL = logging.DEBUG
LOG_FILE = "/dev/log"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
BLUEZ_DEV = "org.bluez.Device1"
MAC_ADDRESS = "00:00:00:00:00:00"

buds_client = subprocess.Popen(['echo', '"Buds"'], preexec_fn=os.setsid)
is_running = False

last_connect = time.time() - 60
last_disconnect = time.time() - 120

def device_property_changed_cb(property_name, value, path, interface, device_path):
    global bus
    global is_running
    global buds_client
    global last_connect
    global last_disconnect
    if property_name != BLUEZ_DEV:
        return

    device = dbus.Interface(bus.get_object("org.bluez", device_path), "org.freedesktop.DBus.Properties")
    properties = device.GetAll(BLUEZ_DEV)

    if properties["Address"] != MAC_ADDRESS:
        return

    logger.info("Getting dbus interface for device: %s interface: %s property_name: %s" % (device_path, interface, property_name))

    if properties["Connected"] == True and is_running == False:
        last_connect = time.time()
        buds_client = subprocess.Popen(
            ['/usr/bin/GalaxyBudsClient', '/StartMinimized'], preexec_fn=os.setsid)
        time.sleep(3)
        os.killpg(os.getpgid(buds_client.pid), signal.SIGKILL)
        buds_client.wait()
        buds_client = subprocess.Popen(
            ['/usr/bin/GalaxyBudsClient', '/StartMinimized'], preexec_fn=os.setsid)
        is_running = True
    elif properties["Connected"] == False and is_running == True:
        last_disconnect = time.time()
        os.killpg(os.getpgid(buds_client.pid), signal.SIGKILL)
        buds_client.wait()
        is_running = False
        if last_disconnect - last_connect < 10:
            rfcomm_fix = subprocess.Popen(['rfcomm', 'connect', 'rfcomm0', MAC_ADDRESS], preexec_fn=os.setsid)
            rfcomm_fix.wait()
            connect_fix = dbus.Interface(bus.get_object("org.bluez", device_path), BLUEZ_DEV)
            connect_fix.Connect()

#        cmd = "for i in $(pactl list short modules | grep module-loopback | grep source=bluez_source.%s | cut -f 1); do pactl unload-module $i; done" % bt_addr
#        logger.info("Running cmd: %s" % cmd)
#        os.system(cmd)

def shutdown(signum, frame):
    mainloop.quit()

if __name__ == "__main__":
    global bus
    # shut down on a TERM signal
    signal.signal(signal.SIGTERM, shutdown)

    # start logging
    logger = logging.getLogger("bt_auto_loader")
    logger.setLevel(LOG_LEVEL)
    logger.addHandler(logging.handlers.SysLogHandler(address = "/dev/log"))
    logger.info("Starting to monitor Bluetooth connections")

    # Get the system bus
    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SystemBus()
    except Exception as ex:
        logger.error("Unable to get the system dbus: '{0}'. Exiting. Is dbus running?".format(ex.message))
        sys.exit(1)

    # listen for signals on the Bluez bus
    bus.add_signal_receiver(device_property_changed_cb, bus_name="org.bluez", signal_name="PropertiesChanged", path_keyword="device_path", interface_keyword="interface")

    try:
        mainloop = GLib.MainLoop.new(None, False)
        mainloop.run()
    except KeyboardInterrupt:
        pass
    except:
        logger.error("Unable to run the gobject main loop")
        sys.exit(1)

    logger.info("Shutting down")
    sys.exit(0)
