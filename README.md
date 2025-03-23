# jesync_qos_static_mod
Mod for MikroTik-LibreQos-Integration adding Static IP

If you are a user of Libreqos and utilize the Mikrotik-LibreQos-Integration,
the Python script eliminates the need for manual input of static IPs in the ShapedDevices.csv With my modification,
you can now input static IPs manually without concern that the Mikrotik-LibreQos-Integration will remove your static device upon running.
To implement this modification, simply replace your current updatecsv.py and include the additional file
jesync_static_device.json same path with your lebreqos directory.
