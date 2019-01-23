<h1>
  wxMesh Driver for subscription of weewx-mqtt published messages
</h1>

Forked from [morrowwm/weewxMQTT](https://github.com/morrowwm/weewxMQTT)

<h2>Description</h2>
<p>An extension of weewx to add a driver which gets data via an MQTT subscription. Also will shortly add the software from the other side of the MQTT broker. Main part of that is an RF24Mesh process.
</p>

**This driver is made to work as a receiver of data published from the [weewx-mqtt](https://github.com/weewx/weewx/wiki/mqtt) extension only.**

* Updated to be able to connect to SSL/TLS Brokers too

This is because weewx-mqtt publishes data with `observation_unitLabel`. So this driver is looking for that, trimming the `_unitLabel` off the key name, then sends the key and value to the loop untouched. 

Because of this, this driver makes a great candidate to get a lab system going that has mirrored “production” data. 

* Production weewx will publish data to MQTT using the `weewx-mqtt` extension. 
* The lab system will use this driver to subscribe to that data and process it as LOOP data.

<p>Works well with the <a href='https://mosquitto.org/'>Mosquitto</a> MQTT message broker.</p>


<h2>Installation</h2>
<p>
Install paho MQTT client using
    sudo pip install paho-mqtt
</p>

Place the wxMesh.py into your `bin/user` folder

Update weewx.conf with the sample below. Remove the TLS option if you don't require it. 

```
[Station]
    station_type = wxMesh

[wxMesh]
    # pip install paho-mqtt if you don’t have it installed already
    host = your.mqtt.broker
    port = 1883
    topic = weather/weewx/loop (or whatever topic weewx-mqtt is publishing to)
    driver = user.wxMesh
    [[tls]]
        tls_version = tlsv1
        ca_certs = /etc/ssl/certs/ca-certificates.crt
```

<p>weewxMQTT (and wxMesh) is licensed under the GNU Public License v3.</p>
