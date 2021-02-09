import json
import os
import re
import urllib
import uuid

import datastore
from helper import FileHelper


def processRequest(request):

    output = ""

    print("request: {}".format(request))

    bucketName = request["bucketName"]
    objectName = request["objectName"]
    documentsTable = request["documentsTable"]
    outputTable = request["outputTable"]
    documentIndex = request['documentIndexTable']

    print("Input Object: {}/{}".format(bucketName, objectName))

    ext = FileHelper.getFileExtenstion(objectName.lower())
    print("Extension: {}".format(ext))

    if(ext and ext in ["jpg", "jpeg", "png", "pdf"]):
        documentId = str(uuid.uuid1())
        ds = datastore.DocumentStore(documentsTable, outputTable)
        (createdOn,) = re.match("f-(\d{20})", objectName).groups()

        doc = ds.queryDocument(documentIndex, createdOn)

        if doc is None:
            ds.createDocument(documentId, bucketName, objectName, createdOn)
        else:
            existingId = doc.get('documentId')
            print(
                f'Put new document version. OLD: {existingId} -- NEW: {documentId}')
            ds.putDocumentVersion(existingId, documentId,
                                  bucketName, objectName)

        output = "Saved document {} for {}/{}".format(
            documentId, bucketName, objectName)

        print(output)

    return {
        'statusCode': 200,
        'body': json.dumps(output)
    }


def lambda_handler(event, context):

    print("event: {}".format(event))

    request = {}
    request["bucketName"] = event['Records'][0]['s3']['bucket']['name']
    request["objectName"] = urllib.parse.unquote_plus(
        event['Records'][0]['s3']['object']['key'])
    request["documentsTable"] = os.environ['DOCUMENTS_TABLE']
    request["outputTable"] = os.environ['OUTPUT_TABLE']
    request['documentIndexTable'] = os.environ.get('TABLE_GSI_NAME')

    return processRequest(request)
