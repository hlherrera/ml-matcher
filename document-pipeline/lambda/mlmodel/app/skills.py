import os
from collections import Counter

import spacy

MAX_ENTITIES = 40
SKILLS_PATTERN_PATH = os.path.join(
    os.environ.get('LAMBDA_TASK_ROOT'),
    "skill_patterns.jsonl"
)

nlp = spacy.load(os.environ.get('SPACY_MODEL'))
ruler = nlp.add_pipe("entity_ruler")
ruler.from_disk(SKILLS_PATTERN_PATH)


def get_skills(text):
    doc = nlp(text)
    matchesLabel = []
    for ent in doc.ents:
        matchesLabel.append(ent.label_)

    skills_freq = Counter(matchesLabel)
    common_entities = skills_freq.most_common(MAX_ENTITIES)

    expr_skills = [(ent[0][6:]+" and "+ent[0][6:] if ent[1] > 2 else ent[0][6:])
                   for ent in common_entities if 'skill' in ent[0].lower()]

    return " or ".join(expr_skills).replace("-", " ")
