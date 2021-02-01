import os
import re
from string import punctuation

import nltk
from botocore.exceptions import ClientError
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from helper import AwsHelper

nltk.data.path.append("/tmp")
nltk.download("punkt", download_dir="/tmp")
nltk.download('stopwords', download_dir="/tmp")

# punctuation to remove
non_words = list(punctuation)
# add spanish punctuation
non_words.extend(['¿', '¡'])


def tokenize(text, language):
    lower_text = text.lower()
    lower_text = re.sub(r"http\S+", "https", lower_text)
    lower_text = ''.join([c for c in lower_text if c not in non_words])
    tokens = word_tokenize(lower_text, language)
    return list(filter(lambda x: x not in stopwords.words('spanish'), tokens))


def updateDocumentKeywords(documentsTable, documentId, keywords):
    err = None
    dynamodb = AwsHelper().getResource("dynamodb")
    table = dynamodb.Table(documentsTable)

    try:
        table.update_item(
            Key={'documentId': documentId},
            UpdateExpression='SET keywords= :keywords',
            ConditionExpression='attribute_exists(documentId)',
            ExpressionAttributeValues={
                ':keywords': keywords
            }
        )
    except ClientError as e:
        if e.response['Error']['Code'] == "ConditionalCheckFailedException":
            print(e.response['Error']['Message'])
            err = {'Error': 'Document does not exist.'}
        else:
            raise
    return err


def processRequest(request):
    output = ""
    text = request["text"]
    documentsTable = request["documentsTable"]
    documentId = request["documentId"]

    keywords = tokenize(text, 'spanish')

    updateDocumentKeywords(documentsTable, documentId, keywords)

    return {
        'statusCode': 200,
        'body': output
    }


def lambda_handler(event, context):
    print("event: {}".format(event))

    text = event['detail']['text']
    doc_id = event['detail']['documentId']

    request = {}

    request["documentId"] = doc_id
    request["text"] = text
    request["documentsTable"] = os.environ['DOCUMENTS_TABLE']

    return processRequest(request)
