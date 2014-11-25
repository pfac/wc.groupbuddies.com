#This file takes in inputs from a variety of sensor files, and outputs information to a variety of services
import sys
sys.dont_write_bytecode = True

import RPi.GPIO as GPIO
import ConfigParser
import time
import inspect
import os
import logging
import signal
from sys import exit
from sensors import sensor
from outputs import output

import requests

pid = str(os.getpid())
pidfile = "/tmp/ldr.pid"

if os.path.isfile(pidfile):
    print "%s already exists, exiting" % pidfile
    sys.exit()
else:
    file(pidfile, 'w').write(pid)

def signal_handler(signal, frame):
    print('Exiting!')
    os.unlink(pidfile)
    exit(0)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def get_subclasses(mod,cls):
    for name, obj in inspect.getmembers(mod):
        if hasattr(obj, "__bases__") and cls in obj.__bases__:
            return obj


if not os.path.isfile('sensors.cfg'):
    print("Unable to access config file: sensors.cfg")
    exit(1)

sensorConfig = ConfigParser.SafeConfigParser()
sensorConfig.read('sensors.cfg')

sensorNames = sensorConfig.sections()

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM) #Use BCM GPIO numbers.

sensorPlugins = []
for i in sensorNames:
    try:
        try:
            filename = sensorConfig.get(i,"filename")
        except Exception:
            print("Error: no filename config option found for sensor plugin " + i)
            raise
        try:
            enabled = sensorConfig.getboolean(i,"enabled")
        except Exception:
            enabled = True

        #if enabled, load the plugin
        if enabled:
            try:
                mod = __import__('sensors.'+filename,fromlist=['a']) #Why does this work?
            except Exception:
                print("Error: could not import sensor module " + filename)
                raise

            try:    
                sensorClass = get_subclasses(mod,sensor.Sensor)
                if sensorClass == None:
                    raise AttributeError
            except Exception:
                print("Error: could not find a subclass of sensor.Sensor in module " + filename)
                raise

            try:    
                reqd = sensorClass.requiredData
            except Exception:
                reqd =    []
            try:
                opt = sensorClass.optionalData
            except Exception:
                opt = []

            pluginData = {}

            class MissingField(Exception): pass
                        
            for requiredField in reqd:
                if sensorConfig.has_option(i,requiredField):
                    pluginData[requiredField]=sensorConfig.get(i,requiredField)
                else:
                    print("Error: Missing required field '" + requiredField + "' for sensor plugin " + i)
                    raise MissingField
            for optionalField in opt:
                if sensorConfig.has_option(i,optionalField):
                    pluginData[optionalField]=sensorConfig.get(i,optionalField)
            instClass = sensorClass(pluginData)
            sensorPlugins.append(instClass)
            print("Success: Loaded sensor plugin " + i)
    except Exception as e: #add specific exception for missing module
        print("Error: Did not import sensor plugin " + i )
        raise e


if not os.path.isfile("outputs.cfg"):
    print("Unable to access config file: outputs.cfg")

outputConfig = ConfigParser.SafeConfigParser()
outputConfig.read("outputs.cfg")

outputNames = outputConfig.sections()

outputPlugins = []

for i in outputNames:
    try:    
        try:
            filename = outputConfig.get(i,"filename")
        except Exception:
            print("Error: no filename config option found for output plugin " + i)
            raise
        try:
            enabled = outputConfig.getboolean(i,"enabled")
        except Exception:
            enabled = True

        #if enabled, load the plugin
        if enabled:
            try:
                mod = __import__('outputs.'+filename,fromlist=['a']) #Why does this work?
            except Exception:
                print("Error: could not import output module " + filename)
                raise

            try:    
                outputClass = get_subclasses(mod,output.Output)
                if outputClass == None:
                    raise AttributeError
            except Exception:
                print("Error: could not find a subclass of output.Output in module " + filename)
                raise
            try:    
                reqd = outputClass.requiredData
            except Exception:
                reqd =    []
            try:
                opt = outputClass.optionalData
            except Exception:
                opt = []
            
            if outputConfig.has_option(i,"async"):
                async = outputConfig.getbool(i,"async")
            else:
                async = False
            
            pluginData = {}

            class MissingField(Exception): pass
                        
            for requiredField in reqd:
                if outputConfig.has_option(i,requiredField):
                    pluginData[requiredField]=outputConfig.get(i,requiredField)
                else:
                    print("Error: Missing required field '" + requiredField + "' for output plugin " + i)
                    raise MissingField
            for optionalField in opt:
                if outputConfig.has_option(i,optionalField):
                    pluginData[optionalField]=outputConfig.get(i,optionalField)
            instClass = outputClass(pluginData)
            instClass.async = async
            outputPlugins.append(instClass)
            print("Success: Loaded output plugin " + i)
    except Exception as e: #add specific exception for missing module
        print("Error: Did not import output plugin " + i )
        raise e

if not os.path.isfile("settings.cfg"):
    print("Unable to access config file: settings.cfg")

mainConfig = ConfigParser.SafeConfigParser()
mainConfig.read("settings.cfg")

lastUpdated = 0
delayTime = mainConfig.getfloat("Main","uploadDelay")
redPin = mainConfig.getint("Main","redPin")
greenPin = mainConfig.getint("Main","greenPin")
url = mainConfig.get("Main", "url")
threshold = mainConfig.getint("Main", "threshold")
GPIO.setup(redPin,GPIO.OUT,initial=GPIO.LOW)
GPIO.setup(greenPin,GPIO.OUT,initial=GPIO.LOW)

while True:
	value = 0
	for i in sensorPlugins:
	    value = i.getVal()
	result = value < threshold
	request_url = ("%s/%s" % (url, result)).lower()
	# print ("%s    %s  %s  %s" % (request_url, value, threshold, result))
	response = requests.put(request_url)
	logging.info("Uploaded successfully")
	GPIO.output(greenPin,GPIO.HIGH)
	GPIO.output(greenPin,GPIO.LOW)
	GPIO.output(redPin,GPIO.LOW)
	time.sleep(delayTime)
