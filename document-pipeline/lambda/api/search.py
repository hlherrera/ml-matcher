import datetime
import json
import os
import sys

import datastore
import hnswlib
import numpy as np
from sentence_transformers import SentenceTransformer
from skills import get_skills
from utils import add_handler, init_logger

documentTable = os.environ.get('DOCUMENTS_TABLE')

efs_path = os.environ.get('MODEL_PATH')
model_index_name = os.environ.get('MODEL_INDEX_NAME', 'ml-index.bin')
model_index_path = os.path.join(efs_path, model_index_name)

dim = int(os.environ.get('MODEL_DIM'))
model = SentenceTransformer(os.environ.get('MODEL_NAME'))

n_elements = 500000
doc_index = hnswlib.Index(space='cosine', dim=dim)
doc_index.init_index(max_elements=n_elements, ef_construction=400, M=84)

db = datastore.DocumentStore(documentTable, '')

DEFAULT_QUANTITY_RESULTS = 20


def handler(event, context):
    log = init_logger()
    log = add_handler(log)
    log.info(event)

    n = DEFAULT_QUANTITY_RESULTS
    text = ""
    try:
        text = json.loads(event['body'])['text']
        n = abs(int(event['queryStringParameters']['n']
                    )) if 'n' in event['queryStringParameters'] else None
    except:
        log.info('Bad request params.')
        return {
            'statusCode': 400,
            'body': "{\"result\": \"Bad request\"}"
        }

    # Process input image
    log.info(f"INFO -- Processing Text")
    #txt_code = model.encode(text)
    skills_code = model.encode(get_skills(text))
    value = skills_code
    #value = np.concatenate((skills_code, txt_code))

    log.info(f'-- Reading Index: {model_index_path}')
    doc_index.load_index(model_index_path, max_elements=n_elements)
    log.info(
        f"\nParameters passed to constructor:  space={doc_index.space}, dim={doc_index.dim}")

    doc_index.set_ef(100)

    log.info(
        "-- Index: Current number of items: "+str(doc_index.element_count))
    n = min(doc_index.element_count, n or DEFAULT_QUANTITY_RESULTS)

    result = {}
    if n > 0:
        log.info(f'-- Searching for k: {n} neighbors')
        labels, distances = doc_index.knn_query(value, k=n)
        result = [{str(k): 1 - np.float64(v)}
                  for k, v in zip(labels[0], distances[0])]

    log.info('result:')
    print(result)

    return {
        'statusCode': 200,
        'body': json.dumps(result)
    }
