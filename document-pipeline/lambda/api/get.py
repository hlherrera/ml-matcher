import json


def lambda_handler(event, context):
    print("event: {}".format(event))

    return {
        'statusCode': 200,
        'body': json.dumps(event)
    }
