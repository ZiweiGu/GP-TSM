
import os
import sys
import numpy as np
from sentence_transformers import SentenceTransformer, models
from sentence_transformers.util import cos_sim
from difflib import SequenceMatcher
import diff_text

OPTIMAL_LENGTH = 0.6
# Allow swapping the semantic embedding model (e.g., a legal-specific one) via env var.
# Default to a legal-domain model.
SEMANTIC_EMBEDDING_MODEL = os.getenv(
    "SEMANTIC_EMBEDDING_MODEL",
    "nlpaueb/legal-bert-base-uncased",
)


def _load_embedding_model(model_name: str) -> SentenceTransformer:
  # Some HF models (like legal-bert) aren't packaged as SentenceTransformers.
  # Build an explicit transformer+pooling pipeline to avoid warnings.
  if model_name == "nlpaueb/legal-bert-base-uncased":
    transformer = models.Transformer(model_name)
    pooling = models.Pooling(
      transformer.get_word_embedding_dimension(),
      pooling_mode_mean_tokens=True,
      pooling_mode_cls_token=False,
      pooling_mode_max_tokens=False,
    )
    return SentenceTransformer(modules=[transformer, pooling])
  return SentenceTransformer(model_name)


MPNET = _load_embedding_model(SEMANTIC_EMBEDDING_MODEL)


def evaluate_on_meaning(original_paragraph, response):
  '''
  1st possible evaluate function that checks the semantic closeness of the response
  to the original sentence; Could be used to infer whether important words are removed
  Returns: a float (cosine similarity value)
  '''
  embedding_original = MPNET.encode(original_paragraph)
  embedding_response = MPNET.encode(response)
  return cos_sim(embedding_original, embedding_response).item()


def evaluate_on_length(original_paragraph, response):
  '''
  2nd possible evaluate function that checks the lengths of the shortened sentence
  Could be used to infer whether unnecessary phrases are indeed removed
  Returns: a float (length shortened/length original)
  '''
  return 1 - abs(len(response)/len(original_paragraph) - OPTIMAL_LENGTH)


def evaluate_on_paraphrasing(original_paragraph, response):
  '''
  3rd possible evaluate function that checks the occurences of paraphrasing on a word level
  Returns: a float (# of non-occurences/length original)
  '''
  opcodes = diff_text.diff_text(original_paragraph, response, False)
  rst = 0
  for code in opcodes:
    if code[0] in ['insert', 'replace']:
      rst += 1
  return 1 - rst/len(original_paragraph.split())


# def evaluate_on_grammaticality(response):
#   '''
#   4th possible evaluate function that checks whether the shortened sentence is grammatical
#   Returns: 1 if grammatical, 0 otherwise
#   '''
#   checker = language_tool_python.LanguageTool('en-US')
#   matches = checker.check(response)
#   # checker.close()
#   for match in matches:
#     if match.ruleId not in ['UPPERCASE_SENTENCE_START']:
#       return 0
#   return 1

def composite(original_paragraph, response, grammar_score):
  # print('The composite score is ' + str(A*evaluate_on_meaning(original_paragraph, response) + B*evaluate_on_length(original_paragraph, response) + C*evaluate_on_paraphrasing(original_paragraph, response) + D* evaluate_on_grammaticality(response)))
  # return evaluate_on_meaning(original_paragraph, response) + evaluate_on_length(original_paragraph, response) + grammar_score
   return evaluate_on_length(original_paragraph, response) + grammar_score

def revert_paraphrasing(original_paragraph, response):
  p1 = original_paragraph.split()
  p2 = response.split()
  opcodes = diff_text.diff_text(original_paragraph, response, False)
  rst = ''
  for code in opcodes:
    if code[0] == 'equal':
      rst += (' '.join(p2[code[3]:code[4]]) + ' ')
    elif code[0] == 'replace':
      rst += (' '.join(p1[code[1]:code[2]]) + ' ')
  return rst
