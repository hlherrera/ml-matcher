# Dockerfile based on https://docs.aws.amazon.com/lambda/latest/dg/images-create.html
FROM amazon/aws-lambda-python:3.8 as base-image

RUN yum install -y \
  gcc \
  gcc-c++ \
  make \
  cmake \
  unzip \
  libcurl4-openssl-dev && \
  yum -y clean all

COPY mlmodel/app/requirements.txt ${LAMBDA_TASK_ROOT}/

# Install python dependencies and runtime interface client
RUN python -m pip install \
  --no-cache-dir \
  wheel \
  awslambdaric \
  -r ${LAMBDA_TASK_ROOT}/requirements.txt

RUN rm -rf /var/cache/yum
RUN mkdir -p /mnt/model

# Copy source code files
COPY helper/python/* ${LAMBDA_TASK_ROOT}/
COPY api/* ${LAMBDA_TASK_ROOT}/
COPY mlmodel/app/* ${LAMBDA_TASK_ROOT}/

ENV MODEL_PATH=/mnt/model
ENV MODEL_NAME=distilbert-multilingual-nli-stsb-quora-ranking
ENV MODEL_DIM=768
ENV SENTENCE_TRANSFORMERS_HOME=/mnt/model

CMD [ "main.handler" ]