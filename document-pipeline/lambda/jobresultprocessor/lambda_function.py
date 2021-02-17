import json
import os
import time

import boto3
import datastore
from helper import AwsHelper
from og import OutputGenerator

TECH_WORDS = {}
with open('tech.words.json') as json_file:
    TECH_WORDS = json.load(json_file)


def getJobResults(api, jobId):

    pages = []

    time.sleep(5)

    client = AwsHelper().getClient('textract')
    if(api == "StartDocumentTextDetection"):
        response = client.get_document_text_detection(JobId=jobId)
    else:
        response = client.get_document_analysis(JobId=jobId)
    pages.append(response)
    print("Resultset page received: {}".format(len(pages)))
    nextToken = None
    if('NextToken' in response):
        nextToken = response['NextToken']
        print("Next token: {}".format(nextToken))

    while(nextToken):
        time.sleep(5)

        if(api == "StartDocumentTextDetection"):
            response = client.get_document_text_detection(
                JobId=jobId, NextToken=nextToken)
        else:
            response = client.get_document_analysis(
                JobId=jobId, NextToken=nextToken)

        pages.append(response)
        print("Resultset page received: {}".format(len(pages)))
        nextToken = None
        if('NextToken' in response):
            nextToken = response['NextToken']
            print("Next token: {}".format(nextToken))

    return pages


def processRequest(request):

    output = ""

    print(request)

    jobId = request['jobId']
    jobTag = request['jobTag']
    jobAPI = request['jobAPI']
    jobStatus = request["jobStatus"]
    bucketName = request['bucketName']
    objectName = request['objectName']
    outputTable = request["outputTable"]
    documentsTable = request["documentsTable"]

    if jobStatus == 'FAILED':
        ds = datastore.DocumentStore(documentsTable, None)
        ds.updateDocumentStatus(jobTag, jobStatus)
        return {
            'statusCode': 200,
            'body': output
        }

    pages = getJobResults(jobAPI, jobId)

    print("Result pages received: {}".format(len(pages)))

    detectForms = False
    detectTables = False
    if(jobAPI == "StartDocumentAnalysis"):
        detectForms = True
        detectTables = True

    dynamodb = AwsHelper().getResource('dynamodb')
    ddb = dynamodb.Table(outputTable)

    opg = OutputGenerator(jobTag, pages, bucketName,
                          objectName, detectForms, detectTables, ddb)
    text = opg.run()

    text = " ".join([TECH_WORDS.get(w.lower()) or w for w in text.split(" ")])

    print("DocumentId: {}".format(jobTag))

    ds = datastore.DocumentStore(documentsTable, outputTable)
    ds.markDocumentComplete(jobTag, text)

    print('First 10 letters: ', text[0:10])
    output = "Processed -> Document: {}, Object: {}/{} processed.".format(
        jobTag, bucketName, objectName)

    print(output)

    events = AwsHelper().getClient("events")
    response = events.put_events(
        Entries=[
            {
                'Detail': json.dumps({'text': text, 'documentId': jobTag}),
                'DetailType': os.environ.get('BUS_EVENT_DETAIL_TYPE'),
                'EventBusName': os.environ.get('BUS_EVENT'),
                'Source': os.environ.get('BUS_EVENT_SOURCE')
            }
        ]
    )
    print(response['Entries'])

    return {
        'statusCode': 200,
        'body': output
    }


def lambda_handler(event, context):

    print("event: {}".format(event))

    body = json.loads(event['Records'][0]['body'])
    message = json.loads(body['Message'])

    print("Message: {}".format(message))

    request = {}

    request["jobId"] = message['JobId']
    request["jobTag"] = message['JobTag']
    request["jobStatus"] = message['Status']
    request["jobAPI"] = message['API']
    request["bucketName"] = message['DocumentLocation']['S3Bucket']
    request["objectName"] = message['DocumentLocation']['S3ObjectName']

    request["outputTable"] = os.environ['OUTPUT_TABLE']
    request["documentsTable"] = os.environ['DOCUMENTS_TABLE']

    return processRequest(request)


def lambda_handler_local(event, context):
    print("event: {}".format(event))
    return processRequest(event)
