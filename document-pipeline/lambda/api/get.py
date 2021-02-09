import json
import os

import boto3
import datastore

s3 = boto3.client("s3")
EXPIRE_TIME = 3600


def handler(event, context):
    print(event)
    param = 0
    try:
        path_param = event.get('pathParameters') or dict({})
        param = abs(int(path_param.get('doc_id', 0)))
    except:
        return {
            'statusCode': 400,
            'headers': {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Credentials": True
            },
            'body': "Bad Request",
            "isBase64Encoded": False
        }
    docs_table = os.environ.get('DOCUMENTS_TABLE')
    table_idx = os.environ.get('TABLE_GSI_NAME')

    ds = datastore.DocumentStore(docs_table, None)
    doc = ds.queryDocument(table_idx, str(param))
    print(doc)

    try:
        bucket_name, object_key = doc['bucketName'], doc['objectName']
        del doc['bucketName']
        del doc['objectName']
        del doc['documentId']
        if bucket_name != object_key != '-':
            doc['url'] = s3.generate_presigned_url('get_object',
                                                   Params={'Bucket': bucket_name,
                                                           'Key': object_key},
                                                   ExpiresIn=EXPIRE_TIME)
    except Exception as e:
        print(e)

    return {
        'statusCode': 200 if doc else 404,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps(doc) if doc else "Not Found",
        "isBase64Encoded": False
    }
