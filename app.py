from flask import Flask, render_template, request, flash, redirect, url_for
import llm
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
    """Generate visualization with salience levels.
    Matches words sequentially across levels to track when each specific word was deleted.
    Words deleted in earlier rounds get lighter shades (lower salience).
    
    Salience levels:
    - Level 0 (lightest gray): Word cut in first round (appears in l0 but not l1)
    - Level 1: Word cut in second round (appears in l1 but not l2)
    - Level 2: Word cut in third round (appears in l2 but not l3)
    - Level 3: Word cut in fourth round (appears in l3 but not l4)
    - Level 4 (darkest/black): Word kept through all rounds (appears in l4)
    """
    l0_lst = l0.split()
    l1_lst = l1.split() if l1 else []
    l2_lst = l2.split() if l2 else []
    l3_lst = l3.split() if l3 else []
    l4_lst = l4.split() if l4 else []
    
    # Track position pointers for each level to match words sequentially
    p1 = 0  # pointer for level 1
    p2 = 0  # pointer for level 2
    p3 = 0  # pointer for level 3
    p4 = 0  # pointer for level 4
    
    rst = ''
    for w in l0_lst:
        # Check if this word matches the word at current pointer in level 1
        matched_l1 = p1 < len(l1_lst) and is_equal(w, l1_lst[p1])
        
        if not matched_l1:
            # Word doesn't appear in level 1 -> cut in round 1 -> salience 0 (lightest gray)
            rst += ('<span style="color:' + LEVEL_0_OPACITY + '"> ' + w + ' </span> ')
        else:
            # Word appears in level 1, advance pointer and check deeper levels
            p1 += 1
            matched = False
            
            # Check level 4 first (highest salience)
            if p4 < len(l4_lst) and is_equal(w, l4_lst[p4]):
                p4 += 1
                rst += ('<span style="color:' + LEVEL_4_OPACITY + '"> ' + bionic(w) + ' </span> ')
                matched = True
            elif p3 < len(l3_lst) and is_equal(w, l3_lst[p3]):
                # Check level 3
                p3 += 1
                rst += ('<span style="color:' + LEVEL_3_OPACITY + '"> ' + w + ' </span> ')
                matched = True
            elif p2 < len(l2_lst) and is_equal(w, l2_lst[p2]):
                # Check level 2
                p2 += 1
                rst += ('<span style="color:' + LEVEL_2_OPACITY + '"> ' + w + ' </span> ')
                matched = True
            else:
                # Word appears in level 1 but not in 2, 3, or 4 -> cut in round 2 -> salience 1
                rst += ('<span style="color:' + LEVEL_1_OPACITY + '"> ' + w + ' </span> ')
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