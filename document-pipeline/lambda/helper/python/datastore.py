import datetime

import boto3
from botocore.exceptions import ClientError

from helper import AwsHelper


class DocumentStore:

    def __init__(self, documentsTableName, outputTableName):
        self._documentsTableName = documentsTableName
        self._outputTableName = outputTableName

    def createDocument(self, documentId, bucketName, objectName, createdOn=round(datetime.datetime.utcnow().timestamp())):

        err = None

        dynamodb = AwsHelper().getResource("dynamodb")
        table = dynamodb.Table(self._documentsTableName)

        try:
            table.update_item(
                Key={"documentId": documentId},
                UpdateExpression='SET bucketName = :bucketNameValue, objectName = :objectNameValue, documentStatus = :documentstatusValue, documentCreatedOn = :documentCreatedOnValue',
                ConditionExpression='attribute_not_exists(documentId)',
                ExpressionAttributeValues={
                    ':bucketNameValue': bucketName,
                    ':objectNameValue': objectName,
                    ':documentstatusValue': 'IN_PROGRESS',
                    ':documentCreatedOnValue': createdOn
                }
            )
        except ClientError as e:
            print(e)
            if e.response['Error']['Code'] == "ConditionalCheckFailedException":
                print(e.response['Error']['Message'])
                err = {'Error': 'Document already exist.'}
            else:
                raise

        return err

    def updateDocumentStatus(self, documentId, documentStatus):

        err = None

        dynamodb = AwsHelper().getResource("dynamodb")
        table = dynamodb.Table(self._documentsTableName)

        try:
            table.update_item(
                Key={'documentId': documentId},
                UpdateExpression='SET documentStatus= :documentstatusValue',
                ConditionExpression='attribute_exists(documentId)',
                ExpressionAttributeValues={
                    ':documentstatusValue': documentStatus
                }
            )
        except ClientError as e:
            if e.response['Error']['Code'] == "ConditionalCheckFailedException":
                print(e.response['Error']['Message'])
                err = {'Error': 'Document does not exist.'}
            else:
                raise

        return err

    def markDocumentComplete(self, documentId, text):

        err = None

        dynamodb = AwsHelper().getResource("dynamodb")
        table = dynamodb.Table(self._documentsTableName)

        try:
            table.update_item(
                Key={'documentId': documentId},
                UpdateExpression='SET documentStatus= :documentstatusValue, documentCompletedOn = :documentCompletedOnValue, documentText = :documentText',
                ConditionExpression='attribute_exists(documentId)',
                ExpressionAttributeValues={
                    ':documentstatusValue': "SUCCEEDED",
                    ':documentCompletedOnValue': str(datetime.datetime.utcnow()),
                    ':documentText': text
                }
            )
        except ClientError as e:
            if e.response['Error']['Code'] == "ConditionalCheckFailedException":
                print(e.response['Error']['Message'])
                err = {'Error': 'Document does not exist.'}
            else:
                raise

        return err

    def getDocument(self, documentId):

        dynamodb = AwsHelper().getClient("dynamodb")

        ddbGetItemResponse = dynamodb.get_item(
            Key={'documentId': {'S': documentId}},
            TableName=self._documentsTableName
        )

        itemToReturn = None

        if('Item' in ddbGetItemResponse):
            itemToReturn = {'documentId': ddbGetItemResponse['Item']['documentId']['S'],
                            'bucketName': ddbGetItemResponse['Item']['bucketName']['S'],
                            'objectName': ddbGetItemResponse['Item']['objectName']['S'],
                            'documentStatus': ddbGetItemResponse['Item']['documentStatus']['S'],
                            'documentCreatedOn': ddbGetItemResponse['Item']['documentCreatedOn']['N']
                            }

        return itemToReturn

    def deleteDocument(self, documentId):

        dynamodb = AwsHelper().getResource("dynamodb")
        table = dynamodb.Table(self._documentsTableName)

        table.delete_item(
            Key={
                'documentId': documentId
            }
        )

    def getDocuments(self, nextToken=None):

        dynamodb = AwsHelper().getResource("dynamodb")
        table = dynamodb.Table(self._documentsTableName)

        pageSize = 25

        if(nextToken):
            response = table.scan(
                ExclusiveStartKey={"documentId": nextToken}, Limit=pageSize)
        else:
            response = table.scan(Limit=pageSize)

        print("response: {}".format(response))

        data = []

        if('Items' in response):
            data = response['Items']

        documents = {
            "documents": data
        }

        if 'LastEvaluatedKey' in response:
            nextToken = response['LastEvaluatedKey']['documentId']
            print("nexToken: {}".format(nextToken))
            documents["nextToken"] = nextToken

        return documents
