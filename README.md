# jesync_qos_static_mod
Mod for MikroTik-LibreQos-Integration adding Static IP

If you are a user of Libreqos and utilize the Mikrotik-LibreQos-Integration,
the Python script eliminates the need for manual input of static IPs in the ShapedDevices.csv With my modification,
you can now input static IPs manually without concern that the Mikrotik-LibreQos-Integration will remove your static device upon running.
To implement this modification, simply replace your current updatecsv.py and include the additional file
jesync_static_device.json same path with your lebreqos directory.

Guide on setting up your static devices

The initial step involves installing the [MikroTik-LibreQos-Integration](https://github.com/Kintoyyy/MikroTik-LibreQos-Integration/blob/main/Installation.md) and ensuring proper configuration. 
Verify that it is running smoothly before proceeding to replace the updatecsv.py file. Once everything is functioning correctly,
proceed to modify the jesync_static_device.json file.
To input the IP addresses of your static devices, 
simply open the jesync_static_device.json file. You can add multiple devices by following the provided sample data. 
After setting up the jesync_static_device.json file, upload it to your libreqos directory and remember to replace the previous updatecsv.py file.

NOTE:
Please refrain from replacing the Parent node "Static" in the jesync_static_devices.json file.
All static devices rely on this node as their parent. Changing this will result in errors.
