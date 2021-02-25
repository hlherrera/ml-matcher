# Large scale Document Processing and CV Matcher

This project shows how you can extract text from documents and create a CV Matcher at scale.
Below are some of key attributes of reference architecture:

- An HTTP endpoint to add documents to Amazon S3 bucket.
- Process incoming documents to an Amazon S3 bucket.
- Serverless, highly available and highly scalable architecture.
- Easily handle spiky workloads.
- Pipelines to support both Sync and Async APIs of Amazon Textract.
- Control the rate at which you process documents without doing any complex distributed job management. This control can be important to protect your downstream systems which will be ingesting output from Textract.
- Bus Event to manage document processing.
- Index and Encode documents persisting them in AWS EFS.
- Implementation which takes advantage of AWS CDK to define infrastructure in code and provision it through CloudFormation.

### Image pipeline (Use Sync APIs of Amazon Textract)

1. The process starts as a message is sent to an Amazon SQS queue to analyze a document.
2. A Lambda function is invoked synchronously with an event that contains queue message.
3. Lambda function then calls Amazon Textract and store result in different datastores(DynamoDB, S3).

You control the throughput of your pipeline by controlling the batch size and lambda concurrency.

### Image and PDF pipeline (Use Async APIs of Amazon Textract)

1. The process starts when a message is sent to an SQS queue to analyze a document.
2. A job scheduler lambda function runs at certain frequency for example every 1 minute and poll for messages in the SQS queue.
3. For each message in the queue it submits an Amazon Textract job to process the document and continue submitting these jobs until it reaches the maximum limit of concurrent jobs in your AWS account.
4. As Amazon Textract is finished processing a document it sends a completion notification to an SNS topic.
5. SNS then triggers the job scheduler lambda function to start next set of Amazon Textract jobs.
6. SNS also sends a message to an SQS queue which is then processed by a Lambda function to get results from Amazon Textract and store them in a relevant dataset(DynamoDB, S3).

Your pipeline runs at maximum throughput based on limits on your account. If needed you can get limits raised for concurrent jobs and pipeline automatically adapts based on new limits.

### Resources Generated

DynamoDB is the central DB for document state storing.
https://console.aws.amazon.com/dynamodb/home?region=[region]#tables:

- ex.
  https://console.aws.amazon.com/dynamodb/home?region=us-east-1#tables:

- Tables:
  DocumentPipelineStack[ENV]-DocumentsTable[ENV][random-#]
  DocumentPipelineStack[ENV]-OutputTable[ENV][random-#]

## Document processing workflow

### Process incoming documents workflow

1. A document gets uploaded to an Amazon S3 bucket. It triggers a Lambda function which writes a task to process the document to DynamoDB.
2. Using DynamoDB streams, a Lambda function is triggered which writes to an SQS queue in one of the pipelines.
3. Documents are processed as described above by "Image Pipeline" or "Image and PDF Pipeline".

## Prerequisites

- Node.js
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)

## Setup

- Download this repo on your local machine
- Install [AWS Cloud Development Kit (CDK)](https://docs.aws.amazon.com/cdk/latest/guide/what-is.html): npm install -g aws-cdk
- Go to folder document-pipeline and run: npm install

## Deployment

- Run "npm run build" to build infrastructure
- Run "cdk bootstrap"
- Run "npm run cdk-dev" to deploy dev stack

## Test incoming documents

- Go to the Amazon S3 bucket "documentpipelinestack-documentsbucketxxxx" created by the stack and upload few sample documents (jpg/jpeg, png, pdf).
- You will see output files generated for each document with a folder name "{filename}-analysis" (refresh Amazon S3 bucket to see these results).

## Delete stack

- Run: cdk destroy
