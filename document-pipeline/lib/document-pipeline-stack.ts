import { LambdaFunction } from "@aws-cdk/aws-events-targets";
import {
  DynamoEventSource,
  S3EventSource,
  SnsEventSource,
  SqsEventSource,
} from "@aws-cdk/aws-lambda-event-sources";
import * as cdk from "@aws-cdk/core";
import events = require("@aws-cdk/aws-events");
import iam = require("@aws-cdk/aws-iam");
import sns = require("@aws-cdk/aws-sns");
import snsSubscriptions = require("@aws-cdk/aws-sns-subscriptions");
import sqs = require("@aws-cdk/aws-sqs");
import dynamodb = require("@aws-cdk/aws-dynamodb");
import lambda = require("@aws-cdk/aws-lambda");
import s3 = require("@aws-cdk/aws-s3");
import efs = require("@aws-cdk/aws-efs");
import ec2 = require("@aws-cdk/aws-ec2");
import ecr = require("@aws-cdk/aws-ecr");
import apiGW = require("@aws-cdk/aws-apigateway");
import apiPI = require("@aws-cdk/aws-apigatewayv2-integrations");
import autoscaling = require("@aws-cdk/aws-applicationautoscaling");

import path = require("path");

const ENV = process.env.ENV || "Dev";
const BUS_EVENT = "TextractEventBus" + ENV;
const BUS_EVENT_SOURCE = "textract.pipeline";
const BUS_EVENT_DETAIL_TYPE = "Document Text Extracted";
const MODEL_PATH = "/mnt/model";
const MODEL_NAME = "distilbert-multilingual-nli-stsb-quora-ranking";

const getNLTKLayer = (version = 27) => {
  return `arn:aws:lambda:${process.env.AWS_REGION}:770693421928:layer:Klayers-python38-nltk:${version}`;
};

export class DocumentPipelineStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // The code that defines your stack goes here

    //**********SNS Topics******************************
    const jobCompletionTopic = new sns.Topic(this, "JobCompletion" + ENV);

    //**********IAM Roles******************************
    const textractServiceRole = new iam.Role(
      this,
      "TextractServiceRole" + ENV,
      {
        assumedBy: new iam.ServicePrincipal("textract.amazonaws.com"),
      }
    );
    textractServiceRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        resources: [jobCompletionTopic.topicArn],
        actions: ["sns:Publish"],
      })
    );

    //************************* EVENT BUS ************************/

    const bus = new events.EventBus(this, "EventBus" + ENV, {
      eventBusName: BUS_EVENT,
    });
    const eventRuleProcess = new events.Rule(this, "EventRuleProcess" + ENV, {
      description: "Event rule for Textract",
      enabled: true,
      eventBus: bus,
      eventPattern: {
        detailType: [BUS_EVENT_DETAIL_TYPE],
        source: [BUS_EVENT_SOURCE],
      },
    });
    const eventRuleInference = new events.Rule(
      this,
      "EventRuleInference" + ENV,
      {
        description: "Event rule for Textract",
        enabled: true,
        eventBus: bus,
        eventPattern: {
          detailType: [BUS_EVENT_DETAIL_TYPE],
          source: [BUS_EVENT_SOURCE],
        },
      }
    );

    //**********S3 Batch Operations Role******************************
    const s3BatchOperationsRole = new iam.Role(
      this,
      "S3BatchOperationsRole" + ENV,
      {
        assumedBy: new iam.ServicePrincipal("batchoperations.s3.amazonaws.com"),
      }
    );

    //**********S3 Bucket******************************
    //S3 bucket for input documents and output
    const contentBucket = new s3.Bucket(this, "DocumentsBucket" + ENV, {
      versioned: false,
    });

    const existingContentBucket = new s3.Bucket(
      this,
      "ExistingDocumentsBucket" + ENV,
      { versioned: false }
    );
    existingContentBucket.grantReadWrite(s3BatchOperationsRole);

    const inventoryAndLogsBucket = new s3.Bucket(
      this,
      "InventoryAndLogsBucket" + ENV,
      { versioned: false }
    );
    inventoryAndLogsBucket.grantReadWrite(s3BatchOperationsRole);

    //**********DynamoDB Table*************************
    //DynamoDB table with links to output in S3
    const outputTable = new dynamodb.Table(this, "OutputTable" + ENV, {
      partitionKey: { name: "documentId", type: dynamodb.AttributeType.STRING },
      sortKey: { name: "outputType", type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    //DynamoDB table with links to output in S3
    const documentsTable = new dynamodb.Table(this, "DocumentsTable" + ENV, {
      partitionKey: { name: "documentId", type: dynamodb.AttributeType.STRING },
      stream: dynamodb.StreamViewType.NEW_IMAGE,
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
    });

    documentsTable.addGlobalSecondaryIndex({
      indexName: "document_table_name",
      partitionKey: { name: "objectName", type: dynamodb.AttributeType.STRING },
    });

    //**********SQS Queues*****************************
    //DLQ
    const dlq = new sqs.Queue(this, "DLQ" + ENV, {
      visibilityTimeout: cdk.Duration.seconds(30),
      retentionPeriod: cdk.Duration.seconds(1209600),
    });

    //Input Queue for sync jobs
    const syncJobsQueue = new sqs.Queue(this, "SyncJobs" + ENV, {
      visibilityTimeout: cdk.Duration.seconds(30),
      retentionPeriod: cdk.Duration.seconds(1209600),
      deadLetterQueue: { queue: dlq, maxReceiveCount: 50 },
    });

    //Input Queue for async jobs
    const asyncJobsQueue = new sqs.Queue(this, "AsyncJobs" + ENV, {
      visibilityTimeout: cdk.Duration.seconds(30),
      retentionPeriod: cdk.Duration.seconds(1209600),
      deadLetterQueue: { queue: dlq, maxReceiveCount: 50 },
    });

    //Queue
    const jobResultsQueue = new sqs.Queue(this, "JobResults" + ENV, {
      visibilityTimeout: cdk.Duration.seconds(900),
      retentionPeriod: cdk.Duration.seconds(1209600),
      deadLetterQueue: { queue: dlq, maxReceiveCount: 50 },
    });
    //Trigger
    //jobCompletionTopic.subscribeQueue(jobResultsQueue);
    jobCompletionTopic.addSubscription(
      new snsSubscriptions.SqsSubscription(jobResultsQueue)
    );

    //**********Lambda Functions******************************

    // Helper Layer with helper functions
    const helperLayer = new lambda.LayerVersion(this, "HelperLayer" + ENV, {
      code: lambda.Code.fromAsset("lambda/helper"),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_8],
      license: "Apache-2.0",
      description: "Helper layer.",
    });

    // Textractor helper layer
    const textractorLayer = new lambda.LayerVersion(this, "Textractor" + ENV, {
      code: lambda.Code.fromAsset("lambda/textractor"),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_8],
      license: "Apache-2.0",
      description: "Textractor layer.",
    });

    const nltkLayer = lambda.LayerVersion.fromLayerVersionArn(
      this,
      "NLTKLayer" + ENV,
      getNLTKLayer()
    );

    //------------------------------------------------------------

    // S3 Event processor
    const s3Processor = new lambda.Function(this, "S3Processor" + ENV, {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("lambda/s3processor"),
      handler: "lambda_function.lambda_handler",
      timeout: cdk.Duration.seconds(30),
      environment: {
        SYNC_QUEUE_URL: syncJobsQueue.queueUrl,
        ASYNC_QUEUE_URL: asyncJobsQueue.queueUrl,
        DOCUMENTS_TABLE: documentsTable.tableName,
        OUTPUT_TABLE: outputTable.tableName,
      },
    });
    //Layer
    s3Processor.addLayers(helperLayer);
    //Trigger
    s3Processor.addEventSource(
      new S3EventSource(contentBucket, {
        events: [s3.EventType.OBJECT_CREATED],
        filters: [{ suffix: ".pdf" }],
      })
    );
    s3Processor.addEventSource(
      new S3EventSource(contentBucket, {
        events: [s3.EventType.OBJECT_CREATED],
        filters: [{ suffix: ".png" }],
      })
    );
    s3Processor.addEventSource(
      new S3EventSource(contentBucket, {
        events: [s3.EventType.OBJECT_CREATED],
        filters: [{ suffix: ".jpg" }],
      })
    );
    s3Processor.addEventSource(
      new S3EventSource(contentBucket, {
        events: [s3.EventType.OBJECT_CREATED],
        filters: [{ suffix: ".jpeg" }],
      })
    );
    //Permissions
    documentsTable.grantReadWriteData(s3Processor);
    syncJobsQueue.grantSendMessages(s3Processor);
    asyncJobsQueue.grantSendMessages(s3Processor);

    //------------------------------------------------------------

    // S3 Batch Operations Event processor
    const s3BatchProcessor = new lambda.Function(
      this,
      "S3BatchProcessor" + ENV,
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        code: lambda.Code.fromAsset("lambda/s3batchprocessor"),
        handler: "lambda_function.lambda_handler",
        timeout: cdk.Duration.seconds(30),
        environment: {
          DOCUMENTS_TABLE: documentsTable.tableName,
          OUTPUT_TABLE: outputTable.tableName,
        },
        reservedConcurrentExecutions: 1,
      }
    );
    //Layer
    s3BatchProcessor.addLayers(helperLayer);
    //Permissions
    documentsTable.grantReadWriteData(s3BatchProcessor);
    s3BatchProcessor.grantInvoke(s3BatchOperationsRole);
    s3BatchOperationsRole.addToPolicy(
      new iam.PolicyStatement({
        actions: ["lambda:*"],
        resources: ["*"],
      })
    );
    //------------------------------------------------------------

    // Document processor (Router to Sync/Async Pipeline)
    const documentProcessor = new lambda.Function(this, "TaskProcessor" + ENV, {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("lambda/documentprocessor"),
      handler: "lambda_function.lambda_handler",
      timeout: cdk.Duration.seconds(900),
      environment: {
        SYNC_QUEUE_URL: syncJobsQueue.queueUrl,
        ASYNC_QUEUE_URL: asyncJobsQueue.queueUrl,
      },
    });
    //Layer
    documentProcessor.addLayers(helperLayer);
    //Trigger
    documentProcessor.addEventSource(
      new DynamoEventSource(documentsTable, {
        startingPosition: lambda.StartingPosition.TRIM_HORIZON,
      })
    );

    //Permissions
    documentsTable.grantReadWriteData(documentProcessor);
    syncJobsQueue.grantSendMessages(documentProcessor);
    asyncJobsQueue.grantSendMessages(documentProcessor);

    //------------------------------------------------------------

    // Sync Jobs Processor (Process jobs using sync APIs)
    const syncProcessor = new lambda.Function(this, "SyncProcessor" + ENV, {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("lambda/syncprocessor"),
      handler: "lambda_function.lambda_handler",
      reservedConcurrentExecutions: 1,
      timeout: cdk.Duration.seconds(30),
      environment: {
        OUTPUT_TABLE: outputTable.tableName,
        DOCUMENTS_TABLE: documentsTable.tableName,
        AWS_DATA_PATH: "models",
      },
    });
    //Layer
    syncProcessor.addLayers(helperLayer);
    syncProcessor.addLayers(textractorLayer);
    //Trigger
    syncProcessor.addEventSource(
      new SqsEventSource(syncJobsQueue, {
        batchSize: 1,
      })
    );
    //Permissions
    contentBucket.grantReadWrite(syncProcessor);
    existingContentBucket.grantReadWrite(syncProcessor);
    outputTable.grantReadWriteData(syncProcessor);
    documentsTable.grantReadWriteData(syncProcessor);
    syncProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["textract:*"],
        resources: ["*"],
      })
    );

    //------------------------------------------------------------

    // Async Job Processor (Start jobs using Async APIs)
    const asyncProcessor = new lambda.Function(this, "ASyncProcessor" + ENV, {
      runtime: lambda.Runtime.PYTHON_3_8,
      code: lambda.Code.fromAsset("lambda/asyncprocessor"),
      handler: "lambda_function.lambda_handler",
      reservedConcurrentExecutions: 1,
      timeout: cdk.Duration.seconds(60),
      environment: {
        ASYNC_QUEUE_URL: asyncJobsQueue.queueUrl,
        SNS_TOPIC_ARN: jobCompletionTopic.topicArn,
        SNS_ROLE_ARN: textractServiceRole.roleArn,
        AWS_DATA_PATH: "models",
      },
    });
    //asyncProcessor.addEnvironment("SNS_TOPIC_ARN", textractServiceRole.topicArn)

    //Layer
    asyncProcessor.addLayers(helperLayer);
    //Triggers
    // Run async job processor every 1 minute
    //Enable code below after test deploy
    const rule = new events.Rule(this, "Rule" + ENV, {
      schedule: events.Schedule.expression("rate(1 minute)"),
    });
    rule.addTarget(new LambdaFunction(asyncProcessor));

    //Run when a job is successfully complete
    asyncProcessor.addEventSource(new SnsEventSource(jobCompletionTopic));
    //Permissions
    contentBucket.grantRead(asyncProcessor);
    existingContentBucket.grantReadWrite(asyncProcessor);
    asyncJobsQueue.grantConsumeMessages(asyncProcessor);
    asyncProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["iam:PassRole"],
        resources: [textractServiceRole.roleArn],
      })
    );
    asyncProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["textract:*"],
        resources: ["*"],
      })
    );
    //------------------------------------------------------------

    // Async Jobs Results Processor
    const jobResultProcessor = new lambda.Function(
      this,
      "JobResultProcessor" + ENV,
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        code: lambda.Code.fromAsset("lambda/jobresultprocessor"),
        handler: "lambda_function.lambda_handler",
        memorySize: 3008,
        reservedConcurrentExecutions: 50,
        timeout: cdk.Duration.seconds(900),
        environment: {
          OUTPUT_TABLE: outputTable.tableName,
          DOCUMENTS_TABLE: documentsTable.tableName,
          AWS_DATA_PATH: "models",
          BUS_EVENT,
          BUS_EVENT_SOURCE,
          BUS_EVENT_DETAIL_TYPE,
        },
      }
    );
    //Layer
    jobResultProcessor.addLayers(helperLayer);
    jobResultProcessor.addLayers(textractorLayer);
    //Triggers
    jobResultProcessor.addEventSource(
      new SqsEventSource(jobResultsQueue, {
        batchSize: 1,
      })
    );
    //Permissions
    outputTable.grantReadWriteData(jobResultProcessor);
    documentsTable.grantReadWriteData(jobResultProcessor);
    contentBucket.grantReadWrite(jobResultProcessor);
    existingContentBucket.grantReadWrite(jobResultProcessor);
    jobResultProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["textract:*"],
        resources: ["*"],
      })
    );
    jobResultProcessor.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["events:PutEvents"],
        resources: [bus.eventBusArn],
      })
    );

    //--------------
    // Process Document NLTK

    const processDocumentText = new lambda.Function(
      this,
      "ProcessDocumentText" + ENV,
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        code: lambda.Code.fromAsset("lambda/nltk"),
        handler: "lambda_function.lambda_handler",
        timeout: cdk.Duration.seconds(900),
        environment: {
          DOCUMENTS_TABLE: documentsTable.tableName,
        },
      }
    );

    processDocumentText.addLayers(helperLayer);
    processDocumentText.addLayers(nltkLayer);

    eventRuleProcess.addTarget(new LambdaFunction(processDocumentText));

    //Permission
    documentsTable.grantReadWriteData(processDocumentText);

    // VPC definition.
    const vpc = new ec2.Vpc(this, "vpcDocument" + ENV, {
      maxAzs: 2,
      natGateways: 1,
    });

    // Security Group definitions.

    const efsSecurityGroup = new ec2.SecurityGroup(
      this,
      "efsDocumentSG" + ENV,
      {
        vpc,
        securityGroupName: "efsDocumentSG" + ENV,
      }
    );
    efsSecurityGroup.connections.allowToAnyIpv4(ec2.Port.tcp(2049));
    efsSecurityGroup.connections.allowFromAnyIpv4(ec2.Port.tcp(2049));

    // Elastic File System file system.
    // For the purpose of cost saving, provisioned troughput has been kept low.
    const fs = new efs.FileSystem(this, "fsDocument" + ENV, {
      vpc: vpc,
      securityGroup: efsSecurityGroup,
      throughputMode: efs.ThroughputMode.PROVISIONED,
      provisionedThroughputPerSecond: cdk.Size.mebibytes(10),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const efsAccessPoint = new efs.AccessPoint(this, "efsAccessPoint" + ENV, {
      fileSystem: fs,
      posixUser: {
        gid: "1000",
        uid: "1000",
      },
      createAcl: {
        ownerGid: "1000",
        ownerUid: "1000",
        permissions: "777",
      },
    });

    // Lambda function to code and index document.
    const addDocumentFunction = new lambda.DockerImageFunction(
      this,
      "DocumentExecuteInference" + ENV,
      {
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "..", "lambda"),
          {}
        ),
        timeout: cdk.Duration.seconds(900),
        memorySize: 10240,
        logRetention: 180,
        reservedConcurrentExecutions: 10,
        vpc,
        vpcSubnets: vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE }),
        filesystem: lambda.FileSystem.fromEfsAccessPoint(
          efsAccessPoint,
          MODEL_PATH
        ),
        environment: {
          DOCUMENTS_TABLE: documentsTable.tableName,
          MODEL_PATH,
          SENTENCE_TRANSFORMERS_HOME: MODEL_PATH,
          MODEL_NAME,
        },
      }
    );

    //permissions
    addDocumentFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName(
        "AmazonElasticFileSystemClientFullAccess"
      )
    );
    addDocumentFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["dynamodb:GetItem"],
        resources: [documentsTable.tableArn],
      })
    );
    eventRuleInference.addTarget(new LambdaFunction(addDocumentFunction));

    // api gateway
    const api = new apiGW.RestApi(this, "DocumentAPI" + ENV, {
      binaryMediaTypes: ["application/pdf"],
      deployOptions: {
        stageName: ENV,
        dataTraceEnabled: true,
        tracingEnabled: true,
        loggingLevel: apiGW.MethodLoggingLevel.INFO,
      },
    });
    new cdk.CfnOutput(this, "ApiUrl", { value: api.url });

    const apiDocs = api.root.addResource("documents");

    const addDocumentAPIFunction = new lambda.Function(
      this,
      "addDocumentAPIFn" + ENV,
      {
        runtime: lambda.Runtime.PYTHON_3_8,
        code: lambda.Code.fromAsset("lambda/api"),
        handler: "add.handler",
        timeout: cdk.Duration.seconds(30),
        environment: {
          BUCKET_NAME: contentBucket.bucketName,
        },
      }
    );
    addDocumentAPIFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["s3:PutObject", "s3:PutObjectAcl"],
        resources: [contentBucket.bucketArn, `${contentBucket.bucketArn}/*`],
      })
    );

    // Lambda function to make inference.
    const getDocumentAPIFunction = new lambda.DockerImageFunction(
      this,
      "getDocumentInferenceAPIFn" + ENV,
      {
        code: lambda.DockerImageCode.fromImageAsset(
          path.join(__dirname, "..", "lambda"),
          {
            entrypoint: ["/lambda-entrypoint.sh"],
            cmd: ["get.handler"],
          }
        ),
        timeout: cdk.Duration.seconds(60),
        memorySize: 5120,
        logRetention: 180,
        reservedConcurrentExecutions: 10,
        vpc,
        vpcSubnets: vpc.selectSubnets({ subnetType: ec2.SubnetType.PRIVATE }),
        filesystem: lambda.FileSystem.fromEfsAccessPoint(
          efsAccessPoint,
          MODEL_PATH
        ),
        environment: {
          DOCUMENTS_TABLE: documentsTable.tableName,
          MODEL_PATH,
          SENTENCE_TRANSFORMERS_HOME: MODEL_PATH,
          MODEL_NAME,
        },
      }
    );

    /*const target = new autoscaling.ScalableTarget(
      this,
      "GetDocumentScalableTarget-" + ENV,
      {
        serviceNamespace: autoscaling.ServiceNamespace.LAMBDA,
        maxCapacity: 10,
        minCapacity: 1,
        resourceId: `function:${getDocumentAPIFunction.functionName}:${getDocumentAPIFunction.currentVersion.version}`,
        scalableDimension: "lambda:function:ProvisionedConcurrency",
      }
    );

    target.scaleToTrackMetric("GetDocumentMetric-" + ENV, {
      targetValue: 0.9,
      predefinedMetric:
        autoscaling.PredefinedMetric.LAMBDA_PROVISIONED_CONCURRENCY_UTILIZATION,
    });*/

    //permissions
    getDocumentAPIFunction.role?.addManagedPolicy(
      iam.ManagedPolicy.fromAwsManagedPolicyName(
        "AmazonElasticFileSystemClientFullAccess"
      )
    );
    getDocumentAPIFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["dynamodb:GetItem"],
        resources: [documentsTable.tableArn],
      })
    );

    apiDocs.addMethod(
      "PUT",
      new apiGW.LambdaIntegration(addDocumentAPIFunction, {
        contentHandling: apiGW.ContentHandling.CONVERT_TO_TEXT,
      }),
      {
        methodResponses: [
          {
            statusCode: "200",
            responseParameters: {
              "method.response.header.Content-Type": true,
              "method.response.header.Access-Control-Allow-Origin": true,
              "method.response.header.Access-Control-Allow-Credentials": true,
            },
          },
        ],
      }
    );

    apiDocs.addMethod(
      "POST",
      new apiGW.LambdaIntegration(getDocumentAPIFunction)
    );
  }
}
