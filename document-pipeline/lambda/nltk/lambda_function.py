import os
import re
from string import punctuation

from botocore.exceptions import ClientError
from helper import AwsHelper

import nltk
from nltk import FreqDist
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

nltk.data.path.append("/tmp")
nltk.download("punkt", download_dir="/tmp")
nltk.download('stopwords', download_dir="/tmp")

NUMBER_OF_WORDS = 15
# punctuation to remove
non_words = list(punctuation)
# add spanish punctuation
non_words.extend(['¿', '¡'])


def tokenize(text, language):
    lower_text = text.lower()
    lower_text = re.sub(r"\s[\d]+\s", " ", lower_text)
    lower_text = re.sub(r"http\S+", "https", lower_text)
    lower_text = ''.join([c for c in lower_text if c not in non_words])
    tokens = word_tokenize(lower_text, language)
    stopwords_set = set(stopwords.words('spanish')).union(
        stopwords.words('english'))
    return list(filter(lambda x: x not in stopwords_set, tokens))


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

    word_list = set(tokenize(text, 'spanish')).union(tokenize(text, 'english'))
    dist = FreqDist(word_list)
    keywords, _ = zip(*dist.most_common(NUMBER_OF_WORDS))

    updateDocumentKeywords(documentsTable, documentId, list(keywords))

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
