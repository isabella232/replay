import os
from flask import Flask, request, json, abort
from flask_cors import CORS
import gzip
import uuid
import json
import requests
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import sqlalchemy
from sqlalchemy import create_engine
import io
from six import BytesIO
from gzip import GzipFile
import urllib3
http = urllib3.PoolManager()

import psycopg2
import string
import psycopg2.extras

# must path auth key in URL or else 403 CSRF error
SENTRY_API_STORE_ONPREMISE ="http://localhost:9000/api/2/store/?sentry_key=759bf0ad07984bb3941e677b35a13d2c&sentry_version=7"

app = Flask(__name__)
CORS(app)

HOST='localhost'
DATABASE='postgres'
USERNAME='admin'
PASSWORD='admin'
db = create_engine('postgresql://' + USERNAME + ':' + PASSWORD + '@' + HOST + ':5432/' + DATABASE)

# STEP1
# MODIFIED_DSN_SAVE - Intercepts event from sentry sdk and saves them to DB. No forward of event to your Sentry instance.
@app.route('/api/2/store/', methods=['POST'])
def save():
    print('type(request)', type(request)) # <class 'werkzeug.local.LocalProxy'
    print('type(request.headers)', type(request.headers)) # <class 'werkzeug.datastructures.EnvironHeaders'>

    request_headers = {}
    for key in ['Host','Accept-Encoding','Content-Length','Content-Encoding','Content-Type','User-Agent']:
        request_headers[key] = request.headers.get(key)
    print('request_headers', request_headers)

    insert_query = """ INSERT INTO events (type, name, data, headers) VALUES (%s,%s,%s,%s)"""
    record = ('python', 'example', request.data, json.dumps(request_headers)) # type(json.dumps(request_headers)) <type 'str'>

    with db.connect() as conn:
        conn.execute(insert_query, record)
        conn.close()
    print("\n DONE \n")
    # does not log on the python app.py side, because sync sentry_sdk.capture_exception()
    return 'event was undertaken from its journey to Sentry'

# STEP1
# MODIFIED_DSN_SAVE_AND_FORWARD
@app.route('/api/3/store/', methods=['POST'])
def save_and_forward():
    # print('type(request)', type(request)) # <class 'werkzeug.local.LocalProxy'
    # print('type(request.headers)', type(request.headers)) # <class 'werkzeug.datastructures.EnvironHeaders'>

    # Save
    request_headers = {}
    for key in ['Host','Accept-Encoding','Content-Length','Content-Encoding','Content-Type','User-Agent']:
        request_headers[key] = request.headers.get(key)
    print('request_headers', request_headers)

    insert_query = """ INSERT INTO events (type, name, data, headers) VALUES (%s,%s,%s,%s)"""
    record = ('python', 'example', request.data, json.dumps(request_headers)) # type(json.dumps(request_headers)) <type 'str'>

    with db.connect() as conn:
        conn.execute(insert_query, record)
        conn.close()

    # Forward
    try:
        response = http.request(
            "POST", str(SENTRY_API_STORE_ONPREMISE), body=request.data, headers=request_headers 
        )

        print("%s RESPONSE and event_id %s" % (response.status, response.data))
        return 'success save_and_forward' # not read by sdk
    except Exception as err:
        print('LOCAL EXCEPTION', err)

# STEP1
# MODIFIED_DSN_FORWARD - Intercepts the payload sent by sentry_sdk in app.py, and then sends it to a Sentry instance
@app.route('/api/4/store/', methods=['POST'])
def forward():
    # print('type(request)', type(request)) # <class 'werkzeug.local.LocalProxy'
    # print('type(request.headers)', type(request.headers)) # <class 'werkzeug.datastructures.EnvironHeaders'>
    # print('request.headers', request.headers) (K | V line separated)
    # print('type(request.data)', type(request.data)) # <class 'bytes'>

    request_headers = {}
    for key in ['Host','Accept-Encoding','Content-Length','Content-Encoding','Content-Type','User-Agent']:
        request_headers[key] = request.headers.get(key)
    print('request_headers', request_headers)

    # TESTING...WORKS
    # body = decompress_gzip(request.data)
    # newbody = compress_gzip(json.loads(body))
    
    try:
        response = http.request(
            "POST", str(SENTRY_API_STORE_ONPREMISE), body=request.data, headers=request_headers 
        )

        print("%s RESPONSE and event_id %s" % (response.status, response.data))
        return 'success'
    except Exception as err:
        print('LOCAL EXCEPTION', err)

    return 'event was impersonated to Sentry'

def decompress_gzip(encoded_data):
    try:
        fp = BytesIO(encoded_data)
        try:
            f = GzipFile(fileobj=fp)
            return f.read().decode("utf-8")
        finally:
            f.close()
    except Exception as e:
        raise e

def compress_gzip(unencoded_data):
    try:
        body = io.BytesIO()
        with gzip.GzipFile(fileobj=body, mode="w") as f:
            f.write(json.dumps(unencoded_data, allow_nan=False).encode("utf-8"))
    except Exception as e:
        raise e
    return body

# TODO
# STEP2
# Pass a pkey ID /impersonate/:id OR could default to whatever most recent event is
# Loads that event's bytes+headers from database and forwards to Sentry instance 
@app.route('/event-bytea/and/forward', methods=['GET']) #re-birth
def impersonator():

    # Set typecasting so psycopg2 returns bytea as 'bytes'. Without typecasting, it returns a MemoryView type
    def bytea2bytes(value, cur):
        m = psycopg2.BINARY(value, cur)
        if m is not None:
            return m.tobytes()

    BYTEA2BYTES = psycopg2.extensions.new_type(
        psycopg2.BINARY.values, 'BYTEA2BYTES', bytea2bytes)

    psycopg2.extensions.register_type(BYTEA2BYTES)

    with db.connect() as conn:
        rows = conn.execute( # <RowProxy>
            "SELECT * FROM events WHERE pk=3"
        ).fetchall()
        conn.close()
        row = rows[0]

    print('type(row)', type(row)) # 'sqlalchemy.engine.result.RowProxy'
    print('row.data LENGTH', len(row.data)) # 
    print('type(row.data)', type(row.data)) # <class 'bytes'>
    # print('row.data', row.data) # b'\x1f\x8b\......
    # print("row.headers", row.headers)


    body = decompress_gzip(row.data)
    json_body = json.loads(body)
    print('timestamp', json_body['timestamp'])
    print('event_id', json_body['event_id'])
    # json_body['timestamp'] = '2019-03-31T05:35:39.320763Z'
    json_body['event_id'] = uuid.uuid4().hex
    # print('timestamp', json_body['timestamp'])
    newbody = compress_gzip(json_body)

    # newbody = compress_gzip(json.loads(body))

    # print("body is \n", type(body))
    # print('LENGTH', len(body)) # TODO is length 0
    # print('type(body.getvalue())'

    try:
        response = http.request(
            "POST", str(SENTRY_API_STORE_ONPREMISE), body=newbody.getvalue(), headers=row.headers 
        )
    except Exception as err:
        print('LOCAL EXCEPTION', err)

    return 'loaded and forwarded to Sentry'

#################################################################################################

# TESTING 
# STEP1
# {"foo": "bar"}
@app.route('/event-bytea', methods=['POST'])
def event_bytea_post():
    print('/event-bytea POST')
    print('type(request.data)', type(request.data)) # bytes
    print('type(request.headers)', type(request.headers)) # <class 'werkzeug.datastructures.EnvironHeaders'>
    print('request.data', request.data) # b'{ "foo": "bar" }'

    request_headers = {}
    for key in ['Host','Accept-Encoding','Content-Length','Content-Encoding','Content-Type','User-Agent']:
        request_headers[key] = request.headers.get(key)
    print('request_headers', request_headers)

    insert_query = """ INSERT INTO events (type, name, data, headers) VALUES (%s,%s,%s,%s)"""
    record = ('python', 'example', request.data, json.dumps(request_headers)) # type(json.dumps(request_headers)) <type 'str'>

    with db.connect() as conn:
        conn.execute(insert_query, record)
        conn.close()
    return 'successfull bytea'

# TESTING
# STEP 2
# TODO
# Pass a pkey ID /impersonate/:id OR could default to whatever most recent event is
# Loads that event's bytes+headers from database
@app.route('/event-bytea', methods=['GET'])
def event_bytea_get():
    print('/event GET')

    # Set typecasting so psycopg2 returns bytea as 'bytes'. Without typecasting, it returns a MemoryView type
    def bytea2bytes(value, cur):
        m = psycopg2.BINARY(value, cur)
        if m is not None:
            return m.tobytes()
    BYTEA2BYTES = psycopg2.extensions.new_type(
        psycopg2.BINARY.values, 'BYTEA2BYTES', bytea2bytes)
    psycopg2.extensions.register_type(BYTEA2BYTES)

    with db.connect() as conn:
        results = conn.execute(
            "SELECT * FROM events WHERE pk=18"
        ).fetchall()
        conn.close()
        row_proxy = results[0]
        print('type(row_proxy)', type(row_proxy))

        print('row_proxy.data LENGTH', len(row_proxy.data))
        print('type(row_proxy.data)', type(row_proxy.data)) #'bytes' if you use the typecasting. 'MemoryView' if you don't use typecasting

        # only need to decompress the gzip if you're trying to read it in JSON or responde with JSON
        # body = decompress_gzip(row_proxy.data)

        return { "data": decompress_gzip(row_proxy.data), "headers": row_proxy.headers }
        # return { "data": row_proxy.data.decode("utf-8"), "headers": row_proxy.headers }


# TESTING
# STEP1
# @app.route('/event', methods=['POST'])
# def event():
#     print('/event POST')
#     record = ('python', 'example')
#     insert_query = """ INSERT INTO events (type, name) VALUES (%s,%s)"""
#     with db.connect() as conn:
#         conn.execute(
#             "INSERT INTO events (type,name) VALUES ('type4', 'name4')"
#         )
#         conn.close()
#         print("inserted")
#     return 'successful'
