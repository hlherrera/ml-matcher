import base64
import datetime
import json
import os
from random import randint
from uuid import uuid4

import boto3
import datastore
from helper import AwsHelper

NANO_SECS = 1000000
EXPIRE_TIME = 3600


def handler(event, context):
    print(event)
    id = resolveId(event)

    if id is None:
        return {
            'statusCode': 400,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": True
            },
            'body': "Bad Request",
            "isBase64Encoded": False
        }

    if event['isBase64Encoded']:
        return manageFile(event, id)
    else:
        return manageText(event, id)


def resolveId(event):
    id = None
    evt_param = (event.get('pathParameters') or dict({})).get('doc_id', 0)
    try:
        id = abs(int(evt_param))
    except:
        print('Bad Request')
    if id == 0:
        s1, s2, s3, s4 = str(randint(0, 9)), str(
            randint(0, 9)), str(randint(0, 9)), str(randint(0, 9))
        id = str(round(datetime.datetime.utcnow().timestamp()
                       * NANO_SECS)) + s1 + s2 + s3 + s4
    return id


def manageFile(event, id_resolved):
    file_content = base64.b64decode(event['body'])
    key = 'f-{}-{}.pdf'.format(id_resolved, str(uuid4()))
    s3 = boto3.client('s3')
    s3_url = None
    try:
        s3.put_object(
            Bucket=os.environ.get(
                'BUCKET_NAME'),
            Key=key,
            Body=file_content
        )
        s3_url = s3.generate_presigned_url('get_object', Params={
            'Bucket': os.environ.get('BUCKET_NAME'),
            'Key': key
        }, ExpiresIn=EXPIRE_TIME)
    except Exception as e:
        raise (e)

    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps({
            'id': str(id_resolved),
            'url': s3_url
        }),
        "isBase64Encoded": False
    }


def manageText(event, id_resolved):
    doc_text = None
    try:
        doc_text = json.loads(event['body'])['text']
    except Exception as e:
        print('Error in request params')
        print(e)
        return {
            'statusCode': 400,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": True
            },
            'body': json.dumps({
                'result': 'Bad Request'
            }),
            "isBase64Encoded": False
        }

    docs_table = os.environ.get('DOCUMENTS_TABLE')
    docs_index = os.environ.get('TABLE_GSI_NAME')
    doc_id = str(uuid4())

    ds = datastore.DocumentStore(docs_table, None)
    doc = ds.queryDocument(docs_index, id_resolved)

    if doc is None:
        ds.createDocument(doc_id, "-", "-", id_resolved)
    else:
        doc_id = doc.get('documentId')

    ds.markDocumentComplete(doc_id, doc_text)
    events = AwsHelper().getClient("events")
    events.put_events(
        Entries=[
            {
                'Detail': json.dumps({'text': doc_text, 'documentId': doc_id}),
                'DetailType': os.environ.get('BUS_EVENT_DETAIL_TYPE'),
                'EventBusName': os.environ.get('BUS_EVENT'),
                'Source': os.environ.get('BUS_EVENT_SOURCE')
            }
        ]
    )

    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps({
            'id': str(id_resolved)
        }),
        "isBase64Encoded": False
    }
