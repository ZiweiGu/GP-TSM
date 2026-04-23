from flask import Flask, render_template, request, flash, redirect, url_for
import llm
import logging

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
    sentence_list = []
    paragraphs = [s for s in form_input.split("\n") if len(s) > 2]
    for i, paragraph in enumerate(paragraphs):
        l0 = ''
        vl0 = ''
        try:
            for d in llm.get_shortened_paragraph(paragraph, k):
                l0 += d['0'] + ' '
                vl0 += generate_vl0(d['0'], d['1'], d['2'], d['3'], d['4']) + ' '
        except Exception as e:
            flash(f'An authentication error occurred: openai.error.AuthenticationError: Incorrect API key provided', 'error')
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
    l0_lst = l0.split()
    l1_lst = l1.split()
    l2_lst = l2.split()
    l3_lst = l3.split()
    l4_lst = l4.split()
    p1 = 0 # pointer
    p2 = 0 # pointer
    p3 = 0 # pointer
    p4 = 0 # pointer
    rst = ''
    for w in l0_lst:
        if p1 < len(l1_lst) and not is_equal(w, l1_lst[p1]):
            rst += ('<span style="color:' + LEVEL_0_OPACITY + '"> ' + w + ' </span> ')
        elif p1 < len(l1_lst) and is_equal(w, l1_lst[p1]):
            p1 += 1
            matched = False
            if p4 < len(l4_lst) and is_equal(w, l4_lst[p4]):
                p4 += 1
                rst += ('<span style="color:' + LEVEL_4_OPACITY + '"> ' + bionic(w) + ' </span> ')
                matched = True
            if p3 < len(l3_lst) and is_equal(w, l3_lst[p3]):
                p3 += 1
                if not matched:
                    rst += ('<span style="color:' + LEVEL_3_OPACITY + '"> ' + w + ' </span> ')
                    matched = True
            if p2 < len(l2_lst) and is_equal(w, l2_lst[p2]):
                p2 += 1
                if not matched:
                    rst += ('<span style="color:' + LEVEL_2_OPACITY + '"> ' + w + ' </span> ')
                    matched = True
            if not matched:
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
    with app.app_context():
        app.run(debug=True) 