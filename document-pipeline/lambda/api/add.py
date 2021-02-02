import base64
import datetime
import json
import os
from uuid import uuid4

import boto3
import datastore
from helper import AwsHelper


def handler(event, context):
    print(event)

    dt = round(datetime.datetime.utcnow().timestamp()*1000)
    if event['isBase64Encoded']:
        return manageFile(event, dt)
    else:
        return manageText(event, dt)


def manageFile(event, id_generated):
    file_content = base64.b64decode(event['body'])
    key = 'f-{}-{}.pdf'.format(id_generated, str(uuid4()))
    s3 = boto3.client('s3')
    try:
        s3.put_object(
            Bucket=os.environ.get(
                'BUCKET_NAME'),
            Key=key,
            Body=file_content
        )
    except Exception as e:
        raise (e)

    return {
        'statusCode': 200,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps({
            'id': id_generated,
            'bucket': os.environ.get('BUCKET_NAME'),
            'key': key
        }),
        "isBase64Encoded": False
    }


def manageText(event, id_generated):
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

    if doc_text is not None:
        docs_table = os.environ.get('DOCUMENTS_TABLE')
        doc_id = str(uuid4())

        ds = datastore.DocumentStore(docs_table, None)
        ds.createDocument(doc_id, "-", "-", int(id_generated))
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
                'id': id_generated
            }),
            "isBase64Encoded": False
        }
