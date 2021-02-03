import datetime
import json
import os
import sys

import datastore
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer

from utils import add_handler, init_logger

documentTable = os.environ.get('DOCUMENTS_TABLE')

efs_path = os.environ.get('MODEL_PATH')
model_index_path = os.path.join(efs_path, 'ml-index.bin')

dim = int(os.environ.get('MODEL_DIM'))
model = SentenceTransformer(os.environ.get('MODEL_NAME'))
model.max_seq_length = 500


n_elements = 1000000
doc_index = hnswlib.Index(space='cosine', dim=dim)
doc_index.init_index(max_elements=n_elements, ef_construction=200, M=50)

db = datastore.DocumentStore(documentTable, '')


def save_in_index(data, label, log):

    try:
        log.info('-- Reading Index')
        doc_index.load_index(model_index_path, max_elements=n_elements)

        log.info(f"-- Index loaded with # threads: {doc_index.num_threads}")
        log.info(
            f"Parameters passed to constructor:  space={doc_index.space}, dim={doc_index.dim}")
    except Exception as e:
        log.warn(e)
        log.warn(
            "-- Index didn't load because is first time and file index not exist")
        pass

    doc_index.set_ef(200)

    log.info(
        f"Index construction: M={doc_index.M}, ef_construction={doc_index.ef_construction}")
    log.info(f"-- Index: Maximun Total of items: {n_elements}")
    log.info(
        f"-- Index: Current number of items: {doc_index.element_count}")
    log.info(
        f"Search speed/quality trade-off parameter: ef={doc_index.ef}")

    log.info("-- Add to Index an item: " + str(label))
    doc_index.add_items(data, int(label))
    log.info("-- Save Index to disk")
    doc_index.save_index(model_index_path)


def handler(event, context):
    log = init_logger()
    log = add_handler(log)
    log.info(event)

    # Retrieve inputs
    log.info(f"INFO -- Retrieve Document Text")
    text = event['detail']['text']
    doc_id = event['detail']['documentId']

    document = db.getDocument(doc_id)
    log.info(document)

    # Process input image
    log.info(f"INFO -- Processing Text")
    value = model.encode(text)

    log.info(f"INFO -- Saving indexes")
    document['documentCreatedOn'] = int(document['documentCreatedOn'])
    save_in_index(value, document['documentCreatedOn'], log)

    log.info(f"Returning data")
    response = {
        "statusCode": 200,
        "isBase64Encoded": False,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(document)
    }

    return response
