#!/usr/bin/python
#
# weewx driver that reads data from MQTT subscription
# ***UPDATED JANUARY 23, 2019 - This driver works with the weewx-mqtt extension ONLY.
#
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.
#
# See http://www.gnu.org/licenses/

#
# The units must be weewx.US:
#   degree_F, inHg, inch, inch_per_hour, mile_per_hour
#
# To use this driver, put this file in the weewx user directory, then make
# the following changes to weewx.conf:
#
# [Station]
#     station_type = wxMesh
# [wxMesh]
#     host = localhost           # MQTT broker hostname
#     topic = weather/+          # topic
#     driver = user.wxMesh
#
# Borrowed from the weewx-mqtt extension for MQTT with TLS/SSL support.
# Use of TLS to encrypt connection to broker.  The TLS options will be passed to
# Paho client tls_set method.  Refer to Paho client documentation for details:
# 
#   https://eclipse.org/paho/clients/python/docs/
# 
# [wxMesh]
#        [[tls]]
#        # CA certificates file (mandatory)
#        ca_certs = /etc/ssl/certs/ca-certificates.crt
#        # PEM encoded client certificate file (optional)
#        certfile = /home/user/.ssh/id.crt
#        # private key file (optional)
#        keyfile = /home/user/.ssh/id.key
#        # Certificate requirements imposed on the broker (optional).
#        #   Options are 'none', 'optional' or 'required'.
#        #   Default is 'required'.
#        cert_reqs = required
#        # SSL/TLS protocol (optional).
#        #   Options include sslv1, sslv2, sslv23, tls, tlsv1.
#        #   Default is 'tlsv1'
#        #   Not all options are supported by all systems.
#        tls_version = tlsv1
#        # Allowable encryption ciphers (optional).
#        #   To specify multiple cyphers, delimit with commas and enclose
#        #   in quotes.
#        #ciphers =
#
# If the variables in the file have names different from those in weewx, then
# create a mapping such as this:
#
# [wxMesh]
#     ...
#     [[label_map]]
#         temp = outTemp
#         humi = outHumidity
#         in_temp = inTemp
#         in_humid = inHumidity

from __future__ import with_statement
import syslog
import time
import json
import Queue
import paho.mqtt.client as mqtt
import weewx.drivers

DRIVER_VERSION = "0.2_pat_obrien_custom_weewx-mqtt_extension_driver"

def logmsg(dst, msg):
    syslog.syslog(dst, 'wxMesh: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def _get_as_float(d, s):
    v = None
    if s in d:
        try:
            v = float(d[s])
        except ValueError, e:
            logerr("cannot read value for '%s': %s" % (s, e))
    return v

def loader(config_dict, engine):
    return wxMesh(**config_dict['wxMesh'])

class TLSDefaults(object):
    def __init__(self):
        import ssl

        # Paho acceptable TLS options
        self.TLS_OPTIONS = [
            'ca_certs', 'certfile', 'keyfile',
            'cert_reqs', 'tls_version', 'ciphers'
            ]
        # map for Paho acceptable TLS cert request options
        self.CERT_REQ_OPTIONS = {
            'none': ssl.CERT_NONE,
            'optional': ssl.CERT_OPTIONAL,
            'required': ssl.CERT_REQUIRED
            }
        # Map for Paho acceptable TLS version options. Some options are
        # dependent on the OpenSSL install so catch exceptions
        self.TLS_VER_OPTIONS = dict()
        try:
            self.TLS_VER_OPTIONS['sslv2'] = ssl.PROTOCOL_SSLv2
        except AttributeError:
            pass
        try:
            self.TLS_VER_OPTIONS['sslv3'] = ssl.PROTOCOL_SSLv3
        except AttributeError:
            pass
        self.TLS_VER_OPTIONS['sslv23'] = ssl.PROTOCOL_SSLv23
        self.TLS_VER_OPTIONS['tlsv1'] = ssl.PROTOCOL_TLSv1
        try:
            self.TLS_VER_OPTIONS['tls'] = ssl.PROTOCOL_TLS
        except AttributeError:
            pass

    
class wxMesh(weewx.drivers.AbstractDevice):
    """weewx driver that reads data from a file"""
    
    def __init__(self, **stn_dict):
        # where to find the data file
        self.host = stn_dict.get('host', 'localhost')
        self.port = stn_dict.get('port', '1883')
        self.connect_timeout = stn_dict.get('connect_timeout', 60)
        self.topic = stn_dict.get('topic', 'weather')
        self.username = stn_dict.get('username', None)
        self.password = stn_dict.get('password', None)
        self.client_id = stn_dict.get('client', 'wxclient') # MQTT client id - adjust as desired
        # SSL borrowed from weewx-mqtt extension.
        self.tls_map = stn_dict.get('tls', {})
        self.tls_dict = {}
        if len(self.tls_map) > 0:
            # We have TLS options so construct a dict to configure Paho TLS
            dflts = TLSDefaults()
            for opt in self.tls_map:
                if opt == 'cert_reqs':
                    if self.tls_map[opt] in dflts.CERT_REQ_OPTIONS:
                        self.tls_dict[opt] = dflts.CERT_REQ_OPTIONS.get(self.tls_map[opt])
                elif opt == 'tls_version':
                    if self.tls_map[opt] in dflts.TLS_VER_OPTIONS:
                        self.tls_dict[opt] = dflts.TLS_VER_OPTIONS.get(self.tls_map[opt])
                elif opt in dflts.TLS_OPTIONS:
                    self.tls_dict[opt] = self.tls_map[opt]
            #loginf("TLS parameters: %s" % self.tls_dict)

        # Mapping from variable names to weewx names
        self.label_map = stn_dict.get('label_map', {})

        loginf("MQTT host is %s" % self.host)
        loginf("MQTT port is %s" % self.port)
        loginf("MQTT connect timeout is %s" % self.connect_timeout)
        if len(self.tls_dict) > 0:
            loginf("network encryption/authentication will be attempted")
            loginf("TLS parameters: %s" % self.tls_dict)
        loginf("MQTT topic is %s" % self.topic)
        loginf("MQTT client is %s" % self.client_id)
        loginf('label map is %s' % self.label_map)

        self.payload = Queue.Queue()

        self.client = mqtt.Client(client_id=self.client_id, protocol=mqtt.MQTTv31)
        
        if self.username is not None and self.password is not None:
            self.client.username_pw_set(self.username, self.password)
            
        # If we have TLS opts configure TLS on our broker connection
        if len(self.tls_dict) > 0:
            self.client.tls_set(**self.tls_dict)

    # The callback for when a PUBLISH message is received from the MQTT server.
    def on_message(self, client, userdata, msg):
        #loginf("MQTT message received")
        #loginf(msg.topic+" "+str(msg.payload))
        self.payload.put(msg.payload,)
        logdbg("Added to queue of %d message %s" % (self.payload.qsize(), msg.payload))
    
    def on_connect(self, client, userdata, flags, rc):
        # Print result code. Good for troubleshooting.
        # 0: Connection successful 
        # 1: Connection refused - incorrect protocol version 
        # 2: Connection refused - invalid client identifier 
        # 3: Connection refused - server unavailable 
        # 4: Connection refused - bad username or password 
        # 5: Connection refused - not authorised 
        # 6-255: Currently unused.
        loginf("Connected with result code: "+str(rc))
        self.client.subscribe(self.topic)
        
    #def closePort(self):
        #self.client.disconnect()
        #self.client.loop_stop()

    def genLoopPackets(self):
        # Connect
        self.client.connect(self.host, self.port, self.connect_timeout)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.loop_start()

        while True:
            # read whatever values we can get from the MQTT broker
            #loginf("Queue of %d entries" % self.payload.qsize())
            #loginf("Waiting for non-empty queue")
            while not self.payload.empty(): 
                msg = str(self.payload.get(block=True, timeout=3)) # block until something gets queued
                logdbg("Working on queue of size %d with payload : %s" % (self.payload.qsize(), msg))
                data = json.loads( msg )
                output = {}
                for (key, value) in data.items():
                    # Remove the unit label from the observation and remove the unicode. weewx-mqtt adds this. 
                    key = key.split("_")[0].encode('utf-8')
                    output[key] = value.encode('utf-8')
                    
                # Build the weewx loop packet
                _packet = {'usUnits': output["usUnits"]}
                for (key, value) in output.items():
                    #_packet[self.label_map.get(key, key)] = _get_as_float(output, value)
                    _packet[self.label_map.get(key, key)] = float(value)
                #print _packet
                loginf("MQTT message processed for LOOP. MQTT payload dateTime: %s" % int( _packet['dateTime'] ) )
                yield _packet
        
        #self.client.disconnect()
        #self.client.loop_stop()
        
    @property
    def hardware_name(self):
        return "wxMesh"
