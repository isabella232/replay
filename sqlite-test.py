from gzip import GzipFile
import json
from six import BytesIO
import sqlite3

# Functions from getsentry/sentry-python
def decompress_gzip(bytes_encoded_data):
    try:
        fp = BytesIO(bytes_encoded_data)
        try:
            f = GzipFile(fileobj=fp)
            return f.read().decode("utf-8")
        finally:
            f.close()
    except Exception as e:
        raise e

# if path is outside of directory, must use absolute path like /home/user/database.db
path_to_database = r"sqlite.db"
conn = sqlite3.connect(path_to_database)

try:
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM events")

        rows = cur.fetchall()
        print('TOTAL ROWS: ', len(rows))

        test = rows[-1]
        test = list(test)
        print('ID OF LATEST ROW', test[1])

        # <read-write buffer ptr 0x562a8e765e30, size 1522 at 0x562a8e765df0>
        # <type 'buffer'>
        # buffer = test[3]
        buffer = test[4]
        print('UBB', buffer)

        #  Print a Sample
        # print('type(buffer)', type(buffer))
        json_body = decompress_gzip(str(buffer))
        dict_body = json.loads(json_body)
        print('dict_body', dict_body)

        # print('dict_body', dict_body['event_id'])
except Exception as e:
    print('EXCEPTION', e)