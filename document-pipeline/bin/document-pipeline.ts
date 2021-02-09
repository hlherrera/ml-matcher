#!/usr/bin/env node
import * as cdk from "@aws-cdk/core";
import "source-map-support/register";
import { DocumentPipelineStack } from "../lib/document-pipeline-stack";

const ENV = process.env.ENV || "Dev";
const app = new cdk.App();

const props =
  ENV === "Dev"
    ? {}
    : {
        env: { account: "657799620713", region: "us-east-1" },
      };
new DocumentPipelineStack(
  app,
  ENV === "Dev" ? "DocumentPipelineStack" : "DocumentPipelineStack" + ENV,
  props
);
