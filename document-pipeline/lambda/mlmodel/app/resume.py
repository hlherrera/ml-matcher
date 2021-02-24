import re
from string import punctuation

MAX_WORDS = 80

non_words = list(punctuation)
non_words.extend(['¿', '¡'])
non_words.extend(map(str, range(10)))


def get_resume(text):
    lower_text = text.lower()
    lower_text = re.sub(r"\s[\d\W]+\s", " ", lower_text)
    lower_text = re.sub(r"\W+", " ", lower_text)
    lower_text = re.sub(r"http\S+", "https", lower_text)
    lower_text = re.sub(r"http\S+", "https", lower_text)
    lower_text = ''.join([c for c in lower_text if c not in non_words])

    return " ".join(list(filter(lambda w: len(w) > 2, lower_text.split(" ")))[:MAX_WORDS])
