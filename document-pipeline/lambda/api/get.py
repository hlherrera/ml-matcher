import json
import os

import datastore


def handler(event, context):
    print(event)
    param = 0
    try:
        param = abs(int(event.get('pathParameters', {}).get('doc_id', 0)))
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
    doc = ds.queryDocument(table_idx, param)
    print(doc)

    return {
        'statusCode': 200 if doc else 404,
        'headers': {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Credentials": True
        },
        'body': json.dumps(doc) if doc else "Not Found",
        "isBase64Encoded": False
    }
