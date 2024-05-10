import openai
from promptengine.pipelines import PromptPipeline
from promptengine.template import PromptTemplate, PromptPermutationGenerator
from promptengine.utils import LLM, extract_responses, is_valid_filepath
import eval_response
import json


MAX_DEPTH = 4 #The 'max depth', or number of successive times we'll try to shorten # make it based on semantic distance 
# semantic score compare with the ORIGINAL paragraph (minimum 1 round; with additional rounds conditioned on score >= threshold)
TEMPERATURE = 0.8 #The temperature for ChatGPT calls
N = 5 #The number of responses to request from ChatGPT, for *each* query 
# framing of paper: focus on forgrounding how AI can hallucinate, especially summarization leading to misinformation. Because of that,
# we design a purely extractive system  "AI-resilient interface design" help humans notice, recover
# strike editing, redo GRE and open-ended reading; in future work, we mention editing and reading questions

GRAMMER_SCORE_RULE = {'A': 1, 'B': 0.5, 'C': 0}

EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE = \
"""For each sentence in the following paragraph, delete phrases that are not the main subject, verb, or object of the sentence, or key modifiers/ terms. The length of the result should be at least 80 percent of the original length. Important: Please make sure the result remains grammatical!!
"${paragraph}"

Please do not add any new words or change words, only delete words."""

GRAMMAR_CHECKER_PROMPT_TEMPLATE = \
"""Score the following paragraph by how grammatical it is.
"${paragraph}"

Answer A for grammatically correct, B for moderately grammatical, and C for bad grammar. Only respond with one letter."""

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
    
# PromptPipeline that runs the 'grammar checker' prompt, and cache's responses.
class GrammarCheckerPromptPipeline(PromptPipeline):
    def __init__(self):
        self._template = PromptTemplate(GRAMMAR_CHECKER_PROMPT_TEMPLATE)
        storageFile = 'grammar_checks.json'
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

def find_score(score):
    if 'Answer' in score:
        return score[7:] # Skip the Answer part
    if ' A ' in score:
        return 'A'
    if ' B ' in score:
        return 'B'
    if ' C ' in score:
        return 'C'
    return score

def for_viz(lst): #prepare data for the viz code in app.py
    if len(lst) == MAX_DEPTH + 1:
        return [{str(i): lst[i] for i in range(len(lst))}]
    rst = [{str(i): lst[i] for i in range(len(lst))}]
    for j in range(MAX_DEPTH - len(lst) + 1):
        rst[0][str(len(lst)+j)] = lst[-1]
    tgt = json.dumps(rst)
    with open("tgt.json", "w") as outfile:
        outfile.write(tgt)
    return rst

def get_shortened_paragraph(orig_paragraph, k):
    # rst = []
    openai.api_key = k
    extractive_shortener = ExtractiveShortenerPromptPipeline()
    grammar_checker = GrammarCheckerPromptPipeline()
    cur_depth = 0
    best_responses = [orig_paragraph]
    paragraph = orig_paragraph
    while cur_depth < MAX_DEPTH:
        responses = []
        extractive_shortener.clear_cached_responses()
        for res in extractive_shortener.gen_responses({"paragraph": paragraph}, LLM.ChatGPT, n=N, temperature=TEMPERATURE):
            responses.extend(extract_responses(res, llm=LLM.ChatGPT))
        responses = [strip_wrapping_quotes(r) for r in responses]
        response_infos = []
        for response in responses:
            reverted = eval_response.revert_paraphrasing(paragraph, response)
            grammar_scores = []
            grammar_checker.clear_cached_responses()
            for score in grammar_checker.gen_responses({"paragraph": reverted}, LLM.ChatGPT, n=1):
                grammar_scores.extend(extract_responses(score, llm=LLM.ChatGPT))
            grammar_score = GRAMMER_SCORE_RULE[find_score(grammar_scores[0])]
            semantic_score = eval_response.evaluate_on_meaning(orig_paragraph, reverted)
            paraphrase_score = eval_response.evaluate_on_paraphrasing(paragraph, response)
            response_infos.append({
                "response": response,
                "reverted": reverted,
                "grammar_score": grammar_score,
                "semantic_score": semantic_score,
                "paraphrase_score": paraphrase_score,
                "composite_score": semantic_score+ grammar_score + paraphrase_score + eval_response.evaluate_on_length(paragraph, reverted)
            })

        response_infos.sort(key=lambda x: x["composite_score"], reverse=True)
        # if best is where no change is present, look at other llm outputs. 
        best_response = response_infos[0]
        cur_depth += 1
        best_responses.append(best_response['reverted'])
        paragraph = best_response["reverted"]
    return for_viz(best_responses)


