#!/usr/bin/env node
import * as cdk from "@aws-cdk/core";
import "source-map-support/register";
import { DocumentPipelineStack } from "../lib/document-pipeline-stack";

const app = new cdk.App();
new DocumentPipelineStack(app, "DocumentPipelineStack");
