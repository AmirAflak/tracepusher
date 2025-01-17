import sys
import requests
import time
import secrets
import argparse

# This script is very simple. It does the equivalent of:
# curl -i -X POST http(s)://endpoint/v1/traces \
# -H "Content-Type: application/json" \
# -d @trace.json

#############################################################################
# USAGE
# python tracepusher.py -ep=http(s)://localhost:4318 -sen=serviceNameA -spn=spanX -dur=2
#############################################################################

# Returns attributes list:
# From spec: https://opentelemetry.io/docs/concepts/signals/traces/#attributes
# Syntax: {
#           "key": "my.scope.attribute",
#           "value": {
#             "stringValue": "some scope attribute"
#           }
#         }
# Ref: https://github.com/open-telemetry/opentelemetry-proto/blob/9876ebfc5bcf629d1438d1cf1ee8a1a4ec21676c/examples/trace.json#L20-L56
# Values must be a non-null string, boolean, floating point value, integer, or an array of these values
# stringValue, boolValue, intValue, doubleValue, arrayValue, kvlistValue, bytesValue are all valid
def get_span_attributes_list(args):

    arg_list = []

    if args == None or len(args) < 1:
        return arg_list

    for item in args:
        # How many = are in the item?
        # 0 = invalid item. Ignore
        # 1 = key=value (tracepusher assumes type=stringValue)
        # 2 = key=value=type (user is explicitly telling us the type. tracepusher uses it)
        # >3 = invalid item. tracepusher does not support span keys and value containing equals. Ignore.
        number_of_equals = item.count("=")
        if number_of_equals == 0 or number_of_equals > 2: continue

        key = ""
        value = ""
        type = "stringValue"

        if number_of_equals == 1:
            key, value = item.split("=", maxsplit=1)
            # User did not pass a type. Assuming type == 'stringValue'
        
        if number_of_equals == 2:
            key, value, type = item.split('=',maxsplit=2)
            # User passed an explicit type. Tracepusher will use it.

        arg_list.append({"key": key, "value": { type: value}})
    
    return arg_list

parser = argparse.ArgumentParser()

# Notes:
# You can use either short or long (mix and match is OK)
# Hyphens are replaced with underscores hence for retrieval
# and leading hyphens are trimmed
# --span-name becomes args.span_name
# Retrieval also uses the second parameter
# Hence args.dry_run will work but args.d won't
parser.add_argument('-ep', '--endpoint', required=True)
parser.add_argument('-sen','--service-name', required=True)
parser.add_argument('-spn', '--span-name', required=True)
parser.add_argument('-dur', '--duration', required=True, type=int)
parser.add_argument('-dr','--dry-run','--dry', required=False, default="False")
parser.add_argument('-x', '--debug', required=False, default="False")
parser.add_argument('-ts', '--time-shift', required=False, default="False")
parser.add_argument('-psid','--parent-span-id', required=False, default="")
parser.add_argument('-tid', '--trace-id', required=False, default="")
parser.add_argument('-sid', '--span-id', required=False, default="")
parser.add_argument('-spnattrs', '--span-attributes', required=False, nargs='*')


args = parser.parse_args()

endpoint = args.endpoint
service_name = args.service_name
span_name = args.span_name
duration = args.duration
dry_run = args.dry_run
debug_mode = args.debug
time_shift = args.time_shift
parent_span_id = args.parent_span_id
trace_id = args.trace_id
span_id = args.span_id

span_attributes_list = get_span_attributes_list(args.span_attributes)

# Debug mode required?
DEBUG_MODE = False
if debug_mode.lower() == "true":
   print("> Debug mode is ON")
   DEBUG_MODE = True

DRY_RUN = False
if dry_run.lower() == "true":
   print("> Dry run mode is ON. Nothing will actually be sent.")
   DRY_RUN = True

TIME_SHIFT = False
if time_shift.lower() == "true":
  print("> Time shift enabled. Will shift the start and end time back in time by DURATION seconds.")
  TIME_SHIFT = True

HAS_PARENT_SPAN = False
if parent_span_id != "":
  print(f"> Pushing a child (sub) span with parent span id: {parent_span_id}")
  HAS_PARENT_SPAN = True

if DEBUG_MODE:
  print(f"Endpoint: {endpoint}")
  print(f"Service Name: {service_name}")
  print(f"Span Name: {span_name}")
  print(f"Duration: {duration}")
  print(f"Dry Run: {type(dry_run)} = {dry_run}")
  print(f"Debug: {type(debug_mode)} = {debug_mode}")
  print(f"Time Shift: {type(time_shift)} = {time_shift}")
  print(f"Parent Span ID: {parent_span_id}")
  print(f"Trace ID: {trace_id}")
  print(f"Span ID: {span_id}")

# Generate random chars for trace and span IDs
# of 32 chars and 16 chars respectively
# per secrets documentation
# each byte is converted to two hex digits
# hence this "appears" wrong by half but isn't
# If this is a child span, we already have a trace_id and parent_span_id
# So do not generate
if trace_id == "":
  trace_id = secrets.token_hex(16)
if span_id == "":
  span_id = secrets.token_hex(8)


if DEBUG_MODE:
  print(f"Trace ID: {trace_id}")
  print(f"Span ID: {span_id}")
  print(f"Parent Span ID: {parent_span_id}")

duration_nanos = duration * 1000000000
# get time now
time_now = time.time_ns()
# calculate future time by adding that many seconds
time_future = time_now + duration_nanos

# shift time_now and time_future back by duration 
if TIME_SHIFT:
   time_now = time_now - duration_nanos
   time_future = time_future - duration_nanos

if DEBUG_MODE:
   print(f"Time shifted? {TIME_SHIFT}")
   print(f"Time now: {time_now}")
   print(f"Time future: {time_future}")

trace = {
 "resourceSpans": [
   {
     "resource": {
       "attributes": [
         {
           "key": "service.name",
           "value": {
             "stringValue": service_name
           }
         }
       ]
     },
     "scopeSpans": [
       {
         "scope": {
           "name": "manual-test"
         },
         "spans": [
           {
             "traceId": trace_id,
             "spanId": span_id,
             "name": span_name,
             "kind": "SPAN_KIND_INTERNAL",
             "start_time_unix_nano": time_now,
             "end_time_unix_nano": time_future,
             "droppedAttributesCount": 0,
             "attributes": span_attributes_list,
             "events": [],
             "droppedEventsCount": 0,
             "status": {
               "code": 1
             }
           }
         ]
       }
     ]
   }
 ]
}

if HAS_PARENT_SPAN:
  # Add parent_span_id field
  trace['resourceSpans'][0]['scopeSpans'][0]['spans'][0]['parentSpanId'] = parent_span_id

if DEBUG_MODE:
   print("Trace:")
   print(trace)

if DRY_RUN:
   print(f"Collector URL: {endpoint}. Service Name: {service_name}. Span Name: {span_name}. Trace Length (seconds): {duration}")
   # Only print if also not running in DEBUG_MODE
   # Otherwise we get a double print
   if not DEBUG_MODE:
     print("Trace:")
     print(trace)
   
if not DRY_RUN:
  resp = requests.post(f"{endpoint}/v1/traces", headers={ "Content-Type": "application/json" }, json=trace)
  print(resp)