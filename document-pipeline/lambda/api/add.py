import base64
import datetime
import json
import os
from uuid import uuid4

import boto3


def handler(event, context):
    dt = round(datetime.datetime.utcnow().timestamp()*1000)
    file_content = base64.b64decode(event['body'])
    key = 'f-{}-{}.pdf'.format(dt, str(uuid4()))
    s3 = boto3.client('s3')
    try:
        s3_response = s3.put_object(
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
            'id': dt,
            'bucket': os.environ.get('BUCKET_NAME'),
            'key': key
        }),
        "isBase64Encoded": False
    }
