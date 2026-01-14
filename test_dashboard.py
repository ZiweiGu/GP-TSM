from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, session
import llm
import logging
import warnings
import json
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
    
    # Check for results in session first, then saved results
    session_results = session.get('test_results', {})
    saved_results = load_saved_results() if not session_results else {}
    
    # Use session results if available, otherwise use saved results
    active_results = session_results if session_results else saved_results
    
    # Prepare test data for display
    test_data = []
    for test_case in test_cases:
        test_id = test_case.name.lower().replace(' ', '_')
        result = active_results.get(test_id)
        
        test_data.append({
            'id': test_id,
            'name': test_case.name,
            'original_text': test_case.original_text,
            'assertions': test_case.assertions,
            'category': test_case.category,
            'has_results': result is not None,
            'result': result
        })
    
    has_results = bool(session_results)
    
    return render_template('test_dashboard.html', test_data=test_data, has_results=has_results)


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
    
    # Run all tests
    summary = harness.run_all_tests()
    
    # Store results in session (don't auto-save)
    # Process results for display
    processed_results = {}
    for result in summary['results']:
        # Extract test number from name (e.g., "Test 1" -> "test_1")
        test_id = result['test_name'].lower().replace(' ', '_')
        
        # Get the test case to get original text
        test_case = next((tc for tc in test_cases if tc.name == result['test_name']), None)
        if not test_case:
            continue
        
        # Generate visualization if we have levels
        rendered_text = ''
        original_text_formatted = format_text_for_comparison(test_case.original_text)
        
        if not result.get('error'):
            try:
                # Use full levels from test harness results (no need for additional API call)
                full_levels = result.get('full_levels', {})
                if full_levels:
                    l0 = full_levels.get('0', '')
                    l1 = full_levels.get('1', '')
                    l2 = full_levels.get('2', '')
                    l3 = full_levels.get('3', '')
                    l4 = full_levels.get('4', '')
                    vl0 = generate_vl0(l0, l1, l2, l3, l4)
                    rendered_text = add_linebreaks(vl0, LINE_LENGTH)
            except Exception as e:
                logger.error(f"Error generating visualization: {e}")
                rendered_text = f"<span style='color: red;'>Error generating visualization: {str(e)}</span>"
        
        processed_results[test_id] = {
            'test_name': result['test_name'],
            'category': result.get('category', 'legal'),
            'passed': result['passed'],
            'error': result.get('error'),
            'assertions': result['assertions'],
            'warnings': result.get('warnings', 0),
            'original_text': test_case.original_text,
            'original_text_formatted': original_text_formatted,
            'rendered_text': rendered_text,
            'timestamp': datetime.now().isoformat()
        }
    
    # Store results in session for saving later
    from flask import session
    session['test_results'] = processed_results
    
    flash(f'Tests completed: {summary["passed"]} passed, {summary["failed"]} failed', 'success' if summary['failed'] == 0 else 'error')
    return redirect(url_for('dashboard'))


@app.route('/save_results', methods=['POST'])
def save_results_endpoint():
    """Save test results via API."""
    results = session.get('test_results', {})
    if results:
        save_results(results)
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
