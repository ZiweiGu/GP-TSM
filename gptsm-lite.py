# This file is a variant of the original GP-TSM algorithm that runs faster, and is designed for 
# applications that require a high level of responsiveness or interactivity. It 
# achieves higher speed by using smaller values for N and MAX_DEPTH and removing
# grammaticality from evaluation, which is a time-consuming metric to compute. However,
# this may mean that the key grammar-preserving feature can be violated at times. To
# achieve the best output quality, please use the original version in llm.py. 
from promptengine.pipelines import PromptPipeline
from promptengine.template import PromptTemplate, PromptPermutationGenerator
from promptengine.utils import LLM, extract_responses, is_valid_filepath
import eval_response


MAX_DEPTH = 3 #The 'max depth', or number of successive times we'll try to shorten # make it based on semantic distance 
# semantic score compare with the ORIGINAL paragraph (minimum 1 round; with additional rounds conditioned on score >= threshold)
TEMPERATURE = 0.8 #The temperature for ChatGPT calls
N = 3 #The number of responses to request from ChatGPT, for *each* query 
# framing of paper: focus on forgrounding how AI can hallucinate, especially summarization leading to misinformation. Because of that,
# we design a purely extractive system  "AI-resilient interface design" help humans notice, recover
# strike editing, redo GRE and open-ended reading; in future work, we mention editing and reading questions


EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE = \
"""For each sentence in the following paragraph, delete phrases that are not the main subject, verb, or object of the sentence, or key modifiers/ terms. The length of the result should be at least 80 percent of the original length. Important: Please make sure the result remains grammatical!!
"${paragraph}"

Please do not add any new words or change words, only delete words."""


# PromptPipeline that runs the 'extractive shortner' prompt, and cache's responses.
class ExtractiveShortenerPromptPipeline(PromptPipeline):
    def __init__(self):
        self._template = PromptTemplate(EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE)
        storageFile = 'shortened_responses.json'
        super().__init__(storageFile)
    def gen_prompts(self, properties):
        gen_prompts = PromptPermutationGenerator(self._template)
        return list(gen_prompts({
            "paragraph": properties["paragraph"]
        }))


# Helper functions
def strip_wrapping_quotes(s: str) -> str:
    if s[0] == '"': s = s[1:]
    if s[-1] == '"': s = s[0:-1]
    return s

def get_shortened_paragraph(orig_paragraph, k, system_message: str = None):
    # rst = []
    extractive_shortener = ExtractiveShortenerPromptPipeline()
    cur_depth = 0
    best_responses = [orig_paragraph]
    paragraph = orig_paragraph
    while cur_depth < MAX_DEPTH:
        responses = []
        extractive_shortener.clear_cached_responses()
        for res in extractive_shortener.gen_responses({"paragraph": paragraph}, LLM.ChatGPT, n=N, temperature=TEMPERATURE, api_key=k, system_message=system_message):
            responses.extend(extract_responses(res, llm=LLM.ChatGPT))
        responses = [strip_wrapping_quotes(r) for r in responses]
        response_infos = []
        for response in responses:
            reverted = eval_response.revert_paraphrasing(paragraph, response)
            semantic_score = eval_response.evaluate_on_meaning(orig_paragraph, reverted)
            paraphrase_score = eval_response.evaluate_on_paraphrasing(paragraph, response)
            response_infos.append({
                "response": response,
                "reverted": reverted,
                "semantic_score": semantic_score,
                "paraphrase_score": paraphrase_score,
                "composite_score": semantic_score+ paraphrase_score + eval_response.evaluate_on_length(paragraph, reverted)
            })

        response_infos.sort(key=lambda x: x["composite_score"], reverse=True)
        # if best is where no change is present, look at other llm outputs. 
        best_response = response_infos[0]
        cur_depth += 1
        best_responses.append(best_response['reverted'])
        paragraph = best_response["reverted"]
    return best_responses


