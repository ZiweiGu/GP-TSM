from flask import Flask, render_template, request, flash, redirect, url_for
import llm
import re
import logging
import warnings

# Suppress urllib3 OpenSSL warning (it's just a warning, not an error)
warnings.filterwarnings('ignore', message='.*urllib3.*OpenSSL.*')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = Flask(__name__) # Initialize the web app
app.secret_key = 'gptsm'

PARAGRAPH_SHORTEST = 10
LINE_LENGTH = 89

LEVEL_4_OPACITY = '#000000'
LEVEL_3_OPACITY = '#767676'
LEVEL_2_OPACITY = '#A0A0A0'
LEVEL_1_OPACITY = '#B9B9B9'
LEVEL_0_OPACITY = '#D0D0D0'

@app.route('/')
def automated():
    return render_template('automated.html', sentence_list=[])

@app.route('/add_paragraph', methods=['POST'])
def add_paragraph():
    form_input = request.form.get("paragraph")
    logger.info(f'User Input: {form_input}')
    k = request.form.get("key")
    
    # Clean up API key (remove whitespace)
    if k:
        k = k.strip()
    
    if not k or len(k) == 0:
        flash('Please provide an OpenAI API key', 'error')
        return redirect(url_for('automated'))
    
    sentence_list = []
    paragraphs = [s for s in form_input.split("\n") if len(s) > 2]
    
    for i, paragraph in enumerate(paragraphs):
        l0 = ''
        vl0 = ''
        try:
            for d in llm.get_shortened_paragraph(paragraph, k, system_message=llm.UK_LAW_SYSTEM_MESSAGE):
                l0 += d['0'] + ' '
                vl0 += generate_vl0(d['0'], d['1'], d['2'], d['3'], d['4']) + ' '
        except Exception as e:
            error_msg = str(e)
            error_type = type(e).__name__
            logger.error(f'Error type: {error_type}, Error message: {error_msg}')
            
            # Check for OpenAI authentication errors
            try:
                from openai import AuthenticationError, APIError, RateLimitError, APIConnectionError
                if isinstance(e, AuthenticationError):
                    flash(f'Authentication error: Incorrect API key provided. Please check your API key.', 'error')
                    logger.error(f'OpenAI AuthenticationError: {error_msg}')
                elif isinstance(e, RateLimitError):
                    flash(f'Rate limit error: {error_msg}. Please try again later.', 'error')
                    logger.error(f'OpenAI RateLimitError: {error_msg}')
                elif isinstance(e, APIConnectionError):
                    flash(f'Connection error: {error_msg}. Please check your internet connection.', 'error')
                    logger.error(f'OpenAI APIConnectionError: {error_msg}')
                elif isinstance(e, APIError):
                    if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower() or 'invalid api key' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                        flash(f'Authentication error: Incorrect API key provided. Please check your API key.', 'error')
                    else:
                        flash(f'API error: {error_msg}', 'error')
                    logger.error(f'OpenAI APIError: {error_msg}')
                else:
                    if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower() or 'invalid' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                        flash(f'Authentication error: Incorrect API key provided. Please check your API key.', 'error')
                    else:
                        flash(f'An error occurred: {error_msg}', 'error')
            except ImportError:
                # Fallback if OpenAI exceptions can't be imported
                if 'authentication' in error_msg.lower() or 'api key' in error_msg.lower() or 'invalid' in error_msg.lower() or 'unauthorized' in error_msg.lower():
                    flash(f'Authentication error: Incorrect API key provided. Please check your API key.', 'error')
                else:
                    flash(f'An error occurred: {error_msg}', 'error')
            return redirect(url_for('automated'))
        sentence_list.append({
            'id': i+1,
            'l0': add_linebreaks(l0, LINE_LENGTH),
            'vl0': add_linebreaks(vl0, LINE_LENGTH)
        })
    return render_template('automated.html', sentence_list=sentence_list) # refresh the page after form submission


def bionic(w):
    return w


def is_equal(w1, w2):
    punc = ['.', ',', ':', '?', '!', ';', '"', '(', ')']
    tmp1 = w1
    tmp2 = w2
    if w1[-1] in punc:
        tmp1 = w1[:-1]
    if w2[-1] in punc:
        tmp2 = w2[:-1]
    return (tmp1.lower() == tmp2.lower())


def generate_vl0(l0, l1, l2, l3, l4): # underline
    """Generate visualization with salience levels using position-aware alignment.

    We align tokens across levels via LCS and CHAIN the alignments to keep
    occurrences consistent (especially for repeated tokens like "the").
    """
    # Split by sentence to avoid cross-sentence alignment issues
    l0_sentences = llm._split_into_sentences(l0)
    l1_sentences = llm._split_into_sentences(l1) if l1 else []
    l2_sentences = llm._split_into_sentences(l2) if l2 else []
    l3_sentences = llm._split_into_sentences(l3) if l3 else []
    l4_sentences = llm._split_into_sentences(l4) if l4 else []

    # If sentence counts drift (LLM removed punctuation), fall back to full-paragraph alignment
    if not (len(l0_sentences) == len(l1_sentences) == len(l2_sentences) == len(l3_sentences) == len(l4_sentences)):
        return _generate_vl0_single_sentence(l0, l1, l2, l3, l4)

    rendered_sentences = []
    for idx in range(len(l0_sentences)):
        rendered_sentences.append(
            _generate_vl0_single_sentence(
                l0_sentences[idx],
                l1_sentences[idx],
                l2_sentences[idx],
                l3_sentences[idx],
                l4_sentences[idx],
            )
        )

    return " ".join(s for s in rendered_sentences if s)


def _generate_vl0_single_sentence(l0, l1, l2, l3, l4):
    l0_tokens = l0.split()
    l1_tokens = l1.split() if l1 else []
    l2_tokens = l2.split() if l2 else []
    l3_tokens = l3.split() if l3 else []
    l4_tokens = l4.split() if l4 else []

    def normalize_token(token: str) -> str:
        token = token.lower().strip()
        token = token.replace("’", "'").replace("‘", "'").replace("‛", "'").replace("`", "'")
        # Strip leading/trailing punctuation but keep internal apostrophes/hyphens
        return re.sub(r"^[^a-z0-9']+|[^a-z0-9']+$", "", token)

    def lcs_pairs(source_tokens, target_tokens):
        """Return matched index pairs (i, j) via LCS using normalized tokens."""
        source_norm = [normalize_token(t) for t in source_tokens]
        target_norm = [normalize_token(t) for t in target_tokens]
        n = len(source_norm)
        m = len(target_norm)
        dp = [[0] * (m + 1) for _ in range(n + 1)]
        for i in range(n - 1, -1, -1):
            for j in range(m - 1, -1, -1):
                if source_norm[i] and source_norm[i] == target_norm[j]:
                    dp[i][j] = 1 + dp[i + 1][j + 1]
                else:
                    dp[i][j] = max(dp[i + 1][j], dp[i][j + 1])
        # Reconstruct one LCS path (favor earlier source positions)
        i = 0
        j = 0
        pairs = []
        while i < n and j < m:
            if source_norm[i] and source_norm[i] == target_norm[j]:
                # If skipping either side keeps the same LCS length, prefer skipping
                # to avoid always matching the earliest repeated token.
                if dp[i + 1][j] == dp[i][j]:
                    i += 1
                    continue
                if dp[i][j + 1] == dp[i][j]:
                    j += 1
                    continue
                pairs.append((i, j))
                i += 1
                j += 1
            else:
                if dp[i + 1][j] >= dp[i][j + 1]:
                    i += 1
                else:
                    j += 1
        return pairs

    # Align l0->l1, then chain l1->l2, l2->l3, l3->l4 to keep positions consistent.
    pairs01 = lcs_pairs(l0_tokens, l1_tokens)
    l0_to_l1 = {i: j for i, j in pairs01}
    l1_to_l0 = {j: i for i, j in pairs01}
    l0_in_l1 = set(l0_to_l1.keys())

    pairs12 = lcs_pairs(l1_tokens, l2_tokens)
    l0_in_l2 = {l1_to_l0[i1] for i1, _ in pairs12 if i1 in l1_to_l0}

    pairs23 = lcs_pairs(l2_tokens, l3_tokens)
    # map l2 index to l0 via l1
    l2_to_l1 = {j2: i1 for i1, j2 in pairs12}
    l0_in_l3 = {l1_to_l0[l2_to_l1[i2]] for i2, _ in pairs23 if i2 in l2_to_l1 and l2_to_l1[i2] in l1_to_l0}

    pairs34 = lcs_pairs(l3_tokens, l4_tokens)
    l3_to_l2 = {j3: i2 for i2, j3 in pairs23}
    l0_in_l4 = {
        l1_to_l0[l2_to_l1[l3_to_l2[i3]]]
        for i3, _ in pairs34
        if i3 in l3_to_l2 and l3_to_l2[i3] in l2_to_l1 and l2_to_l1[l3_to_l2[i3]] in l1_to_l0
    }

    rst = ''
    for idx, w in enumerate(l0_tokens):
        if idx in l0_in_l4:
            rst += ('<span style="color:' + LEVEL_4_OPACITY + '"> ' + bionic(w) + ' </span> ')
        elif idx in l0_in_l3:
            rst += ('<span style="color:' + LEVEL_3_OPACITY + '"> ' + w + ' </span> ')
        elif idx in l0_in_l2:
            rst += ('<span style="color:' + LEVEL_2_OPACITY + '"> ' + w + ' </span> ')
        elif idx in l0_in_l1:
            rst += ('<span style="color:' + LEVEL_1_OPACITY + '"> ' + w + ' </span> ')
        else:
            rst += ('<span style="color:' + LEVEL_0_OPACITY + '"> ' + w + ' </span> ')
    return rst


def add_linebreaks(p, line_length):
    count = 0
    rst = ''
    for w in p.split():
        rst += (w + ' ')
        if '<span' not in w and 'background-color' not in w and 'color' not in w and '</span>' not in w:
            if '<b>' in w:
                count += (len(w) + 1 - 7) 
            else:
                count += (len(w) + 1) 
            if count > line_length:
                rst += '<br>'
                count  = 0
    return rst
    # return p


if __name__ == "__main__":
    import os
    # Use port from environment variable, or default to 5001
    port = int(os.environ.get('PORT', 5001))
    with app.app_context():
        app.run(debug=True, port=port, host='127.0.0.1') 