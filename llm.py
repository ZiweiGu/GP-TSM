from promptengine.pipelines import PromptPipeline
from promptengine.template import PromptTemplate, PromptPermutationGenerator
from promptengine.utils import LLM, extract_responses, is_valid_filepath
import eval_response
import json
import re


MAX_DEPTH = 4 #The 'max depth', or number of successive times we'll try to shorten # make it based on semantic distance 
# semantic score compare with the ORIGINAL paragraph (minimum 1 round; with additional rounds conditioned on score >= threshold)
TEMPERATURE = 0.8 #The temperature for ChatGPT calls
N = 2 #The number of responses to request from ChatGPT, for *each* query 
# framing of paper: focus on forgrounding how AI can hallucinate, especially summarization leading to misinformation. Because of that,
# we design a purely extractive system  "AI-resilient interface design" help humans notice, recover
# strike editing, redo GRE and open-ended reading; in future work, we mention editing and reading questions

GRAMMER_SCORE_RULE = {'A': 1, 'B': 0.5, 'C': 0}

UK_LAW_SYSTEM_MESSAGE = "You are an expert legal assistant. Your goal is to reveal the core legal structure. You MUST aggressively delete specific dates, locations, and citations as they are considered noise here. However, you must PRESERVE legal terms of art (e.g., 'common ground', 'proprietor', 'registered') and the logical flow of the argument. Focus on the main legal action."

EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE = \
"""For each sentence in the following paragraph from a legal document, delete phrases that are not the main subject, verb, or object of the sentence, or key modifiers/ terms, while preserving the main meaning of the sentence as much as possible. Be aggressive in removing parentheticals, attached clauses, and details about dates/ location. The length of the result should be at most 80 percent of the original length (you must delete at least 20% of the text). Important: Please make sure the result remains grammatical!!
"${paragraph}"

Please do not add any new words or change words, only delete words."""

EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE_AGGRESSIVE = \
"""For each sentence in the following paragraph from a legal document, delete phrases that are not the main subject, verb, or object of the sentence, or key modifiers/ terms, while preserving the main meaning of the sentence as much as possible. Be more aggressive in removing parentheticals, attached clauses, and details about dates/ location. The length of the result should be at most 70 percent of the original length (you must delete at least 30% of the text). Important: Please make sure the result remains grammatical!!
"${paragraph}"

Please do not add any new words or change words, only delete words."""

GRAMMAR_CHECKER_PROMPT_TEMPLATE = \
"""Score the following paragraph from a legal document by how grammatical it is. Be strict in your evaluation - only mark as A if the text is fully grammatically correct with proper sentence structure, subject-verb agreement, and correct word order.
"${paragraph}"

Answer A for grammatically correct, B for moderately grammatical (minor issues), and C for bad grammar (major grammatical errors). Only respond with one letter."""

# PromptPipeline that runs the 'extractive shortner' prompt, and cache's responses.
class ExtractiveShortenerPromptPipeline(PromptPipeline):
    def __init__(self, use_aggressive=False):
        if use_aggressive:
            self._template = PromptTemplate(EXTRACTIVE_SHORTENER_PROMPT_TEMPLATE_AGGRESSIVE)
        else:
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
    """Extract the grammar score letter (A, B, or C) from the LLM response."""
    # Clean the score string
    score = score.strip().upper()
    
    # Try to find the letter A, B, or C in the response
    # Look for patterns like "A", "A.", "A (", "Answer: A", etc.
    if 'Answer' in score:
        # Extract everything after "Answer" or "Answer:"
        score = score.split('Answer', 1)[-1].strip()
        if score.startswith(':'):
            score = score[1:].strip()
    
    # Look for A, B, or C (possibly followed by punctuation or parentheses)
    import re
    # Match A, B, or C at word boundaries or start of string, possibly followed by punctuation
    match = re.search(r'\b([ABC])\b', score)
    if match:
        return match.group(1)
    
    # Fallback: check if the first character is A, B, or C
    if score and score[0] in ['A', 'B', 'C']:
        return score[0]
    
    # If no match found, return the original (will cause KeyError, but better than returning invalid value)
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

def _split_into_sentences(text):
    """Split text into sentences using simple regex-based approach."""
    # Split on sentence-ending punctuation followed by whitespace or end of string
    sentences = re.split(r'([.!?]+(?:\s+|$))', text)
    # Recombine sentences with their punctuation
    result = []
    for i in range(0, len(sentences) - 1, 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]
        sentence = sentence.strip()
        if sentence:
            result.append(sentence)
    # Handle case where there's no trailing punctuation
    if len(sentences) % 2 == 1 and sentences[-1].strip():
        result.append(sentences[-1].strip())
    return result if result else [text]

def _calculate_smooth_aggressiveness(word_count):
    """Calculate smooth aggressiveness value based on sentence word count."""
    min_length = 20     # Below this, use fully conservative
    max_length = 80     # Above this, use fully aggressive
    
    # Clamp and normalize word count to [0, 1] range
    if word_count <= min_length:
        aggressiveness = 0.0
    elif word_count >= max_length:
        aggressiveness = 1.0
    else:
        # Linear interpolation between min and max
        aggressiveness = (word_count - min_length) / (max_length - min_length)
    
    # Apply smoothstep function for smoother transition: 3x^2 - 2x^3
    smooth_aggressiveness = aggressiveness * aggressiveness * (3 - 2 * aggressiveness)
    return smooth_aggressiveness

def _get_parameters_for_aggressiveness(smooth_aggressiveness):
    """Get temperature, N, and optimal_length based on aggressiveness."""
    # Interpolate parameters smoothly based on aggressiveness (0 = conservative, 1 = aggressive)
    # Temperature: 0.1 (conservative) -> 0.1 (aggressive) - fixed at 0.1
    current_temperature = TEMPERATURE
    
    # N (number of candidates): 2 (conservative) -> 2 (aggressive) - fixed at 2
    current_n = N
    
    # Optimal length: 0.6 (conservative) -> 0.5 (aggressive)
    optimal_length = 0.6 - (0.6 - 0.5) * smooth_aggressiveness
    
    # Determine if we should use aggressive prompt template (threshold at 0.5 aggressiveness)
    use_aggressive = smooth_aggressiveness > 0.5
    
    return current_temperature, current_n, optimal_length, use_aggressive

def get_shortened_paragraph(orig_paragraph, k, system_message: str = None):
    # Validate API key
    if not k or not k.strip():
        raise ValueError("API key is required but was not provided or is empty.")
    k = k.strip()  # Ensure key is clean
    
    # Split paragraph into sentences
    sentences = _split_into_sentences(orig_paragraph)
    
    # Process each sentence separately with sentence-level aggressiveness
    shortened_sentences = []
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
            
        # Calculate aggressiveness based on THIS SENTENCE's length, not the whole paragraph
        word_count = len(sentence.split())
        smooth_aggressiveness = _calculate_smooth_aggressiveness(word_count)
        
        # Get parameters for this sentence
        current_temperature, current_n, optimal_length, use_aggressive = _get_parameters_for_aggressiveness(smooth_aggressiveness)
        
        # Temporarily adjust OPTIMAL_LENGTH for this sentence
        original_optimal_length = eval_response.OPTIMAL_LENGTH
        eval_response.OPTIMAL_LENGTH = optimal_length
        
        # Process this sentence
        extractive_shortener = ExtractiveShortenerPromptPipeline(use_aggressive=use_aggressive)
        grammar_checker = GrammarCheckerPromptPipeline()
        cur_depth = 0
        best_responses = [sentence]
        paragraph = sentence
        orig_sentence = sentence  # Store original sentence for semantic comparison
        
        while cur_depth < MAX_DEPTH:
            responses = []
            extractive_shortener.clear_cached_responses()
            for res in extractive_shortener.gen_responses({"paragraph": paragraph}, LLM.ChatGPT, n=current_n, temperature=current_temperature, api_key=k, system_message=system_message):
                responses.extend(extract_responses(res, llm=LLM.ChatGPT))
            responses = [strip_wrapping_quotes(r) for r in responses]
            response_infos = []
            for response in responses:
                reverted = eval_response.revert_paraphrasing(paragraph, response)
                grammar_scores = []
                grammar_checker.clear_cached_responses()
                for score in grammar_checker.gen_responses({"paragraph": reverted}, LLM.ChatGPT, n=1, api_key=k):
                    grammar_scores.extend(extract_responses(score, llm=LLM.ChatGPT))
                
                grammar_letter = find_score(grammar_scores[0])
                grammar_score = GRAMMER_SCORE_RULE.get(grammar_letter, 0)  # Default to 0 if invalid
                
                # Strong penalty for poor grammar (C score) - heavily discourage ungrammatical results
                grammar_penalty = 0
                if grammar_letter == 'C':
                    grammar_penalty = -2.0  # Large penalty for bad grammar
                elif grammar_letter == 'B':
                    grammar_penalty = -0.3  # Small penalty for moderate grammar
                # A gets no penalty
                
                semantic_score = eval_response.evaluate_on_meaning(orig_sentence, reverted)  # Compare with original sentence
                paraphrase_score = eval_response.evaluate_on_paraphrasing(paragraph, response)
                length_score = eval_response.evaluate_on_length(paragraph, reverted)
                
                # Adjust composite score smoothly based on aggressiveness
                # Interpolate between conservative and aggressive scoring
                # Increased grammar weight to prioritize grammaticality
                if smooth_aggressiveness > 0.1:  # Only apply aggressive scoring if aggressiveness is meaningful
                    # Boost score for responses that actually reduce length significantly
                    length_reduction = 1 - (len(reverted) / len(paragraph)) if len(paragraph) > 0 else 0
                    length_bonus = length_reduction * 0.3 * smooth_aggressiveness  # Scale bonus by aggressiveness
                    
                    # Interpolate between conservative and aggressive composite scoring
                    # Increased grammar weight: 0.4 -> 0.5, and add grammar_penalty
                    conservative_score = semantic_score + (grammar_score * 1.5) + paraphrase_score + length_score + grammar_penalty
                    aggressive_score = (semantic_score * 0.3) + (grammar_score * 0.6) + (paraphrase_score * 0.15) + (length_score * 0.4) + length_bonus + grammar_penalty
                    composite_score = conservative_score * (1 - smooth_aggressiveness) + aggressive_score * smooth_aggressiveness
                else:
                    # Fully conservative scoring for very short sentences - prioritize grammar even more
                    composite_score = semantic_score + (grammar_score * 2.0) + paraphrase_score + length_score + grammar_penalty
                
                response_infos.append({
                    "response": response,
                    "reverted": reverted,
                    "grammar_score": grammar_score,
                    "grammar_letter": grammar_letter,  # Store letter for filtering
                    "semantic_score": semantic_score,
                    "paraphrase_score": paraphrase_score,
                    "composite_score": composite_score
                })
            
            # Filter out responses with poor grammar (C score) unless all responses are C
            # Prioritize A > B > C
            has_a = any(info['grammar_letter'] == 'A' for info in response_infos)
            has_b = any(info['grammar_letter'] == 'B' for info in response_infos)
            
            if has_a:
                # If we have A-rated responses, filter to only A-rated ones
                response_infos = [info for info in response_infos if info['grammar_letter'] == 'A']
            elif has_b:
                # If we have B-rated responses but no A, filter to only B-rated ones
                response_infos = [info for info in response_infos if info['grammar_letter'] == 'B']
            # If all are C, keep them all (better than nothing, but heavily penalized)

            response_infos.sort(key=lambda x: x["composite_score"], reverse=True)
            
            # If no valid responses after filtering, this shouldn't happen with current logic
            # (we keep C-rated responses if all are C), but handle it gracefully
            if not response_infos:
                # This edge case shouldn't occur, but if it does, break to avoid errors
                break
            
            # if best is where no change is present, look at other llm outputs. 
            best_response = response_infos[0]
            
            # Final grammar check: if best response has C grammar and we have alternatives, try to find better one
            if best_response.get('grammar_letter') == 'C' and len(response_infos) > 1:
                # Look for any B or A rated responses
                better_grammar_responses = [info for info in response_infos if info.get('grammar_letter') in ['A', 'B']]
                if better_grammar_responses:
                    # Prefer better grammar even if composite score is slightly lower
                    # Sort by grammar first (A > B > C), then by composite score
                    better_grammar_responses.sort(key=lambda x: (x.get('grammar_letter') != 'A', -x["composite_score"]))
                    best_response = better_grammar_responses[0]
            
            cur_depth += 1
            
            # Use smoothly adjusted stopping condition based on aggressiveness
            if smooth_aggressiveness > 0.3:  # Apply lenient stopping for moderately long sentences
                # Check if meaningful reduction occurred
                # Threshold scales with aggressiveness: more lenient for longer sentences
                original_len = len(paragraph.split())
                new_len = len(best_response['reverted'].split())
                reduction_ratio = (original_len - new_len) / original_len if original_len > 0 else 0
                
                # Scale thresholds based on aggressiveness (more lenient for longer sentences)
                min_reduction_ratio = 0.01 + 0.01 * smooth_aggressiveness  # 1% to 2% minimum reduction
                min_words_removed = int(3 + 2 * smooth_aggressiveness)  # 3 to 5 words minimum
                
                if reduction_ratio < min_reduction_ratio and (original_len - new_len) < min_words_removed:
                    # If reduction is minimal, try the next best response if available
                    if len(response_infos) > 1:
                        next_best = response_infos[1]
                        next_original_len = len(paragraph.split())
                        next_new_len = len(next_best['reverted'].split())
                        next_reduction_ratio = (next_original_len - next_new_len) / next_original_len if next_original_len > 0 else 0
                        if next_reduction_ratio > reduction_ratio:
                            best_response = next_best
                            new_len = next_new_len
                            reduction_ratio = next_reduction_ratio
                
                # Only stop if truly no meaningful reduction occurred AND we're not in the first iteration
                # This ensures we always try at least once, even with conservative parameters
                if reduction_ratio < (min_reduction_ratio * 0.5) and (original_len - new_len) < (min_words_removed - 1) and cur_depth > 1:
                    break # No meaningful words are deleted during this round, so quit
            else:
                # Original stopping condition for shorter sentences
                # Check word count instead of character length for more accurate comparison
                original_word_count = len(paragraph.split())
                new_word_count = len(best_response['reverted'].split())
                # Only stop if no words were deleted AND we're not in the first iteration
                # This ensures we always try at least once, even with conservative parameters
                if original_word_count == new_word_count and cur_depth > 1:
                    break # No more words are deleted during this round, so quit
            
            best_responses.append(best_response['reverted'])
            paragraph = best_response["reverted"]
        
        # Restore original OPTIMAL_LENGTH after processing this sentence
        eval_response.OPTIMAL_LENGTH = original_optimal_length
        
        # Store the shortened versions of this sentence
        shortened_sentences.append(best_responses)
    
    # Combine shortened sentences back into paragraph format
    # We need to merge the shortening levels across all sentences
    # Find the maximum depth across all sentences
    max_sentence_depth = max(len(sent_responses) for sent_responses in shortened_sentences) if shortened_sentences else 1
    
    # Combine sentences at each depth level
    combined_responses = []
    for depth in range(max_sentence_depth):
        combined_paragraph = []
        for sent_responses in shortened_sentences:
            # Use the response at this depth, or the last one if depth exceeds sentence's depth
            depth_idx = min(depth, len(sent_responses) - 1)
            combined_paragraph.append(sent_responses[depth_idx])
        combined_responses.append(' '.join(combined_paragraph))
    
    return for_viz(combined_responses)


