#!/usr/bin/env node
import * as cdk from "@aws-cdk/core";
import "source-map-support/register";
import { DocumentPipelineStack } from "../lib/document-pipeline-stack";

const ENV = process.env.ENV || "Dev";
const app = new cdk.App();
const props = {};
new DocumentPipelineStack(app, "DocumentPipelineStack" + ENV, props);
