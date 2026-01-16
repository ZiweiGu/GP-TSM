from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, session
import llm
import logging
import warnings
import json
import re
import os
from datetime import datetime
from test_harness import TestHarness, load_legal_test_cases, TestCase

# Suppress urllib3 OpenSSL warning
warnings.filterwarnings('ignore', message='.*urllib3.*OpenSSL.*')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'gptsm-dashboard'

LINE_LENGTH = 89

LEVEL_4_OPACITY = '#000000'
LEVEL_3_OPACITY = '#767676'
LEVEL_2_OPACITY = '#A0A0A0'
LEVEL_1_OPACITY = '#B9B9B9'
LEVEL_0_OPACITY = '#D0D0D0'

RESULTS_FILE = 'dashboard_test_results.json'

# In-memory results to avoid oversized session cookies
LATEST_RESULTS = {
    "tests": {},
    "paragraphs": {}
}

PARAGRAPHS = [
    "As will shortly appear, the facts of this case demonstrate that the cessation of an otherwise qualifying period of reasonable belief before the making of the application for registration is by no means an unusual or unlikely situation. It may fairly be described as routine, or even typical. This is because the impetus which may lead S to seek to be registered as the owner of adjacent land which S formerly thought was already his (or hers) will often be the raising by his neighbour O of a dispute as to his ownership, backed up by evidence in support, which destroys S’s belief that it belongs to him, or at least makes his continuing belief unreasonable. But it is virtually inconceivable that S could then prepare and make such an application on the very same day as O first articulated his claim.",
    "The question of construction to be decided on this appeal arises because it is common ground that, as a matter of pure grammar, the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways, which I will call constructions A and B. Under construction A, the period of reasonable belief must be a period of at least ten years ending on the date of the application. Under the more lenient construction B, the period of reasonable belief can be any period of at least ten years within the potentially longer period of adverse possession which ends on the date of the application. Put another way, a period between the ending of a ten year period of reasonable belief and the date of the application will be fatal to the ability of S to satisfy the boundary condition under construction A, whereas it will not be fatal under construction B.",
    "The issue of construction to be decided on this appeal is in no sense fact sensitive, at least to the facts of this case. They may therefore be summarised shortly. On 20 September 2002 the respondent Mr Brown was registered as proprietor of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham (“the Brown land”). On 8 July 2004 the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land to the North East of it, and also lying to the West of the Promenade, including a dwelling house known as Valley View."
]

TEST_PARAGRAPH_MAP = {
    "test_1": 0,
    "test_2": 1,
    "test_3": 2,
    "test_4": 2
}


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


def generate_vl0(l0, l1, l2, l3, l4):
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
    """Return text as-is. Browser will handle line breaking naturally."""
    return p


def format_text_for_comparison(text, line_length=LINE_LENGTH):
    """Return text as-is. Browser will handle line breaking naturally."""
    return text


@app.route('/')
def dashboard():
    """Main dashboard page."""
    
    # Load test cases
    test_cases = load_legal_test_cases()
    
    saved_results = load_saved_results()

    # Prefer in-memory results, fall back to saved results
    if LATEST_RESULTS["tests"] or LATEST_RESULTS["paragraphs"]:
        active_test_results = LATEST_RESULTS["tests"]
        active_paragraph_results = LATEST_RESULTS["paragraphs"]
    else:
        # Backward-compatible: saved results may be a flat dict of tests
        active_test_results = saved_results.get('tests', saved_results)
        active_paragraph_results = saved_results.get('paragraphs', {})
    
    # Build paragraph data with attached tests
    paragraph_data = []
    for idx, paragraph in enumerate(PARAGRAPHS):
        paragraph_id = f"paragraph_{idx + 1}"
        paragraph_result = active_paragraph_results.get(paragraph_id)
        
        # Collect tests that belong to this paragraph
        paragraph_tests = []
        for test_case in test_cases:
            test_id = test_case.name.lower().replace(' ', '_')
            if TEST_PARAGRAPH_MAP.get(test_id) != idx:
                continue
            result = active_test_results.get(test_id)
            paragraph_tests.append({
                'id': test_id,
                'name': test_case.name,
                'assertions': test_case.assertions,
                'category': test_case.category,
                'has_results': result is not None,
                'result': result
            })
        
        paragraph_data.append({
            'id': paragraph_id,
            'index': idx + 1,
            'original_text': paragraph,
            'has_results': paragraph_result is not None,
            'result': paragraph_result,
            'tests': paragraph_tests,
            'has_test_results': bool(active_test_results)
        })
    
    has_results = bool(LATEST_RESULTS["tests"]) or bool(LATEST_RESULTS["paragraphs"])
    if not has_results:
        has_results = bool(active_test_results) or bool(active_paragraph_results)
    
    return render_template('test_dashboard.html', paragraph_data=paragraph_data, has_results=has_results)


@app.route('/run_tests', methods=['POST'])
def run_tests():
    """Run all tests with provided API key."""
    k = request.form.get("key")
    
    if not k or not k.strip():
        flash('Please provide an OpenAI API key', 'error')
        return redirect(url_for('dashboard'))
    
    k = k.strip()
    
    # Create test harness and load test cases
    harness = TestHarness(k, system_message=llm.UK_LAW_SYSTEM_MESSAGE)
    test_cases = load_legal_test_cases()
    
    for test_case in test_cases:
        harness.add_test_case(test_case)
    
    # Build paragraph visualizations and store levels for assertions
    paragraph_results = {}
    paragraph_levels = {}
    for idx, paragraph in enumerate(PARAGRAPHS):
        paragraph_id = f"paragraph_{idx + 1}"
        try:
            paragraph_rendered = ''
            paragraph_formatted = format_text_for_comparison(paragraph)
            paragraph_result = llm.get_shortened_paragraph(paragraph, k, system_message=llm.UK_LAW_SYSTEM_MESSAGE)
            if paragraph_result and len(paragraph_result) > 0:
                full_levels = paragraph_result[0]
                paragraph_levels[paragraph_id] = full_levels
                l0 = full_levels.get('0', '')
                l1 = full_levels.get('1', '')
                l2 = full_levels.get('2', '')
                l3 = full_levels.get('3', '')
                l4 = full_levels.get('4', '')
                vl0 = generate_vl0(l0, l1, l2, l3, l4)
                paragraph_rendered = add_linebreaks(vl0, LINE_LENGTH)
            paragraph_results[paragraph_id] = {
                'original_text_formatted': paragraph_formatted,
                'rendered_text': paragraph_rendered,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error generating paragraph visualization: {e}")
            paragraph_results[paragraph_id] = {
                'original_text_formatted': format_text_for_comparison(paragraph),
                'rendered_text': f"<span style='color: red;'>Error generating visualization: {str(e)}</span>",
                'timestamp': datetime.now().isoformat()
            }

    # Process test results using paragraph-level levels
    processed_results = {}
    for test_case in test_cases:
        test_id = test_case.name.lower().replace(' ', '_')
        paragraph_idx = TEST_PARAGRAPH_MAP.get(test_id)
        paragraph_id = f"paragraph_{paragraph_idx + 1}" if paragraph_idx is not None else None
        levels = paragraph_levels.get(paragraph_id) if paragraph_id else None

        if not levels:
            processed_results[test_id] = {
                'test_name': test_case.name,
                'category': test_case.category,
                'passed': False,
                'error': 'No paragraph levels available for this test',
                'assertions': [],
                'warnings': 0,
                'original_text': test_case.original_text,
                'original_text_formatted': format_text_for_comparison(test_case.original_text),
                'rendered_text': '',
                'timestamp': datetime.now().isoformat()
            }
            continue

        assertion_results = []
        all_passed = True
        warnings = 0
        for assertion in test_case.assertions:
            passed, message = harness._check_assertion(assertion, levels)
            if not passed:
                if assertion.nice_to_have:
                    warnings += 1
                else:
                    all_passed = False
            assertion_results.append({
                'phrase1': assertion.phrase1,
                'phrase2': assertion.phrase2,
                'relation': assertion.relation.value,
                'passed': passed,
                'message': message,
                'nice_to_have': assertion.nice_to_have
            })

        processed_results[test_id] = {
            'test_name': test_case.name,
            'category': test_case.category,
            'passed': all_passed,
            'error': None,
            'assertions': assertion_results,
            'warnings': warnings,
            'original_text': test_case.original_text,
            'original_text_formatted': format_text_for_comparison(test_case.original_text),
            'rendered_text': '',
            'timestamp': datetime.now().isoformat()
        }

    LATEST_RESULTS["tests"] = processed_results
    LATEST_RESULTS["paragraphs"] = paragraph_results
    
    passed_count = sum(1 for r in processed_results.values() if r.get('passed'))
    failed_count = len(processed_results) - passed_count
    flash(f'Tests completed: {passed_count} passed, {failed_count} failed', 'success' if failed_count == 0 else 'error')
    return redirect(url_for('dashboard'))


@app.route('/save_results', methods=['POST'])
def save_results_endpoint():
    """Save test results via API."""
    test_results = LATEST_RESULTS.get('tests', {})
    paragraph_results = LATEST_RESULTS.get('paragraphs', {})
    if test_results or paragraph_results:
        save_results({
            'tests': test_results,
            'paragraphs': paragraph_results
        })
        flash('Test results saved successfully!', 'success')
    else:
        flash('No test results to save. Please run tests first.', 'error')
    return redirect(url_for('dashboard'))


def load_saved_results():
    """Load saved test results from file."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading saved results: {e}")
            return {}
    return {}


def save_results(results):
    """Save test results to file."""
    try:
        # Merge with existing results
        existing = load_saved_results()
        existing.update(results)
        
        with open(RESULTS_FILE, 'w') as f:
            json.dump(existing, f, indent=2)
        logger.info(f"Saved {len(results)} test results")
    except Exception as e:
        logger.error(f"Error saving results: {e}")


if __name__ == "__main__":
    import os
    port = int(os.environ.get('PORT', 5002))  # Different port from main app
    with app.app_context():
        app.run(debug=True, port=port, host='127.0.0.1')
