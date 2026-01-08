from promptengine.pipelines import PromptPipeline
from promptengine.template import PromptTemplate, PromptPermutationGenerator
from promptengine.utils import LLM, extract_responses
import spacy
import string

nlp = spacy.load("en_core_web_sm")

TEMPERATURE = 1 #The temperature for ChatGPT calls

SENTENCE_SEGMENTER_PROMPT_TEMPLATE = \
"""Does the following sentence end properly?
"${sentence}"

Please answer only Yes or No."""

class SentenceSegmenterPromptPipeline(PromptPipeline):
    def __init__(self):
        self._template = PromptTemplate(SENTENCE_SEGMENTER_PROMPT_TEMPLATE)
        storageFile = 'responses.json'
        super().__init__(storageFile)
    def gen_prompts(self, properties):
        gen_prompts = PromptPermutationGenerator(self._template)
        return list(gen_prompts({
            "sentence": properties["sentence"]
        }))

def split_and_concatenate(sentence):
    # Remove punctuation at the end of the sentence
    result = []
    sentence = sentence.rstrip(string.punctuation)
    # Split the sentence into words
    tokens = []
    doc = nlp(sentence.strip())
    for token in doc:
        tokens.append(token.text)
        if token.head.i > token.i: # current word has a parent on the right of it, so ending the sentence here will not make sense.
            continue
        result.append((' '.join(tokens)))     
    return result

def strip_wrapping_quotes(s: str) -> str:
    if s[0] == '"': s = s[1:]
    if s[-1] == '"': s = s[0:-1]
    return s

def extract_new_phrases(sentences):
    new_phrases = []
    previous_sentence = ""
    for sentence in sentences:
        # Find the part of the sentence that is new compared to the previous one
        if sentence.startswith(previous_sentence):
            new_phrase = sentence[len(previous_sentence):]
        else:
            new_phrase = sentence
        new_phrases.append(new_phrase)
        previous_sentence = sentence
    return new_phrases

def find_segments(sentence, k):
    sentence_segmenter = SentenceSegmenterPromptPipeline()
    result = []
    for candidate in split_and_concatenate(sentence):
        responses = []
        sentence_segmenter.clear_cached_responses()
        for res in sentence_segmenter.gen_responses({"sentence": candidate}, LLM.ChatGPT, n=1, temperature=TEMPERATURE, api_key=k):
            responses.extend(extract_responses(res, llm=LLM.ChatGPT))
        responses = [strip_wrapping_quotes(r) for r in responses]
        if 'yes' in responses[0].lower():
            result.append(candidate)
    if len(sentence) > 0 and len(result) == 0:
        result.append(sentence)
    return extract_new_phrases(result)