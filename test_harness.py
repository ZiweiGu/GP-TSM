#!/usr/bin/env python3
"""
Test harness for GP-TSM algorithm.
Tests the algorithm on various test cases and validates assertions about salience relationships.
"""

import sys
import os
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Add parent directory to path to import llm module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm


class AssertionType(Enum):
    """Types of salience assertions."""
    LESS_THAN = "<"  # First phrase has lower salience than second
    GREATER_THAN = ">"  # First phrase has higher salience than second
    EQUAL = "=="  # First phrase has same max salience as second
    GREATER_EQUAL = ">="  # First phrase has salience >= second


@dataclass
class SalienceAssertion:
    """Represents a salience assertion to test."""
    phrase1: str
    phrase2: str
    relation: AssertionType
    nice_to_have: bool = False  # If True, failure is a warning, not an error


@dataclass
class TestCase:
    """Represents a test case."""
    name: str
    original_text: str
    assertions: List[SalienceAssertion]
    category: str = "legal"  # Category of test (legal, general, etc.)


class TestHarness:
    """Test harness for GP-TSM algorithm."""
    
    def __init__(self, api_key: str, system_message: Optional[str] = None):
        """Initialize test harness with API key."""
        self.api_key = api_key
        self.system_message = system_message
        self.test_cases: List[TestCase] = []
        self.results: List[Dict] = []
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case to the harness."""
        self.test_cases.append(test_case)
    
    def _get_word_salience(self, word: str, levels: Dict[str, str]) -> Optional[int]:
        """
        Get the salience level of a single word.
        Salience is determined by the highest (deepest) level where the word appears.
        - Level 0: Word cut in first round (appears in level 0 but not level 1)
        - Level 1: Word cut in second round (appears in level 1 but not level 2)
        - Level 2: Word cut in third round (appears in level 2 but not level 3)
        - Level 3: Word cut in fourth round (appears in level 3 but not level 4)
        - Level 4: Word kept through all rounds (appears in level 4)
        
        Returns the level number (0-4) or None if word not found.
        """
        import re
        
        # Normalize word: lowercase, strip punctuation for matching
        word_clean = re.sub(r'[^\w\s]', '', word.lower().strip())
        if not word_clean:
            return None
        
        # Create word pattern with word boundaries
        word_pattern = r'\b' + re.escape(word_clean) + r'\b'
        
        # Check each level from deepest (4) to shallowest (0)
        # We want the HIGHEST level where the word appears
        # The highest level where a word appears is its salience
        highest_level = None
        for level in ['4', '3', '2', '1', '0']:
            if level in levels:
                level_text = levels[level].lower()
                # Check if word appears in this level
                if re.search(word_pattern, level_text):
                    highest_level = int(level)
                    break  # Found the highest level, no need to check lower levels
        
        return highest_level

    def _normalize_word(self, word: str) -> str:
        """Normalize a word for sequential matching (lowercase, strip trailing punctuation)."""
        import re
        word = word.lower().strip()
        # Remove trailing punctuation but keep internal apostrophes/hyphens
        return re.sub(r"[^\w]+$", "", word)

    def _words_equal(self, w1: str, w2: str) -> bool:
        """Compare words using the same normalization used for sequential matching."""
        return self._normalize_word(w1) == self._normalize_word(w2)

    def _get_l0_word_saliences(self, levels: Dict[str, str]) -> List[Tuple[str, int]]:
        """
        Compute per-word salience for level 0 words using sequential matching across levels.
        Returns a list of (word, salience) in l0 order.
        """
        l0_lst = levels.get('0', '').split()
        l1_lst = levels.get('1', '').split()
        l2_lst = levels.get('2', '').split()
        l3_lst = levels.get('3', '').split()
        l4_lst = levels.get('4', '').split()

        p1 = 0
        p2 = 0
        p3 = 0
        p4 = 0

        results: List[Tuple[str, int]] = []

        for w in l0_lst:
            matched_l1 = p1 < len(l1_lst) and self._words_equal(w, l1_lst[p1])
            if not matched_l1:
                results.append((w, 0))
                continue

            p1 += 1

            if p4 < len(l4_lst) and self._words_equal(w, l4_lst[p4]):
                p4 += 1
                results.append((w, 4))
            elif p3 < len(l3_lst) and self._words_equal(w, l3_lst[p3]):
                p3 += 1
                results.append((w, 3))
            elif p2 < len(l2_lst) and self._words_equal(w, l2_lst[p2]):
                p2 += 1
                results.append((w, 2))
            else:
                results.append((w, 1))

        return results

    def _find_phrase_indices(self, l0_words: List[str], phrase_words: List[str]) -> Optional[int]:
        """Find the start index of the first phrase match in l0 words."""
        if not phrase_words:
            return None
        for i in range(len(l0_words) - len(phrase_words) + 1):
            matched = True
            for j, pw in enumerate(phrase_words):
                if not self._words_equal(l0_words[i + j], pw):
                    matched = False
                    break
            if matched:
                return i
        return None
    
    def _get_phrase_salience(self, phrase: str, levels: Dict[str, str]) -> Optional[int]:
        """
        Get the salience of a phrase by finding the minimum salience among all words in the phrase.
        The salience of a phrase is the lowest word salience within that phrase.
        
        Returns the level number (0-4) or None if phrase not found.
        """
        stats = self._get_phrase_salience_stats(phrase, levels)
        if stats is None:
            return None
        min_salience, _, _ = stats
        return min_salience

    def _get_phrase_salience_stats(self, phrase: str, levels: Dict[str, str]) -> Optional[Tuple[int, float, int]]:
        """
        Get phrase salience stats:
        - min_salience: lowest word salience within the phrase
        - pct_lowest: percentage of words at that lowest salience
        - total_words: total word count in phrase

        Returns (min_salience, pct_lowest, total_words) or None if phrase not found.
        """
        phrase_words = phrase.split()
        if not phrase_words:
            return None

        l0_word_saliences = self._get_l0_word_saliences(levels)
        l0_words = [w for w, _ in l0_word_saliences]

        start_idx = self._find_phrase_indices(l0_words, phrase_words)
        if start_idx is None:
            return None

        slice_saliences = [s for _, s in l0_word_saliences[start_idx:start_idx + len(phrase_words)]]
        if not slice_saliences:
            return None

        min_salience = min(slice_saliences)
        lowest_count = sum(1 for s in slice_saliences if s == min_salience)
        total_words = len(slice_saliences)
        pct_lowest = lowest_count / total_words if total_words > 0 else 0.0

        return min_salience, pct_lowest, total_words
    
    def _get_max_salience(self, phrase: str, levels: Dict[str, str]) -> Optional[int]:
        """
        Get the salience of a phrase (minimum salience among words in the phrase).
        This is an alias for _get_phrase_salience for backward compatibility.
        """
        return self._get_phrase_salience(phrase, levels)
    
    def _check_assertion(self, assertion: SalienceAssertion, levels: Dict[str, str]) -> Tuple[bool, str]:
        """
        Check if an assertion holds given the salience levels.
        Returns (passed, message).
        """
        stats1 = self._get_phrase_salience_stats(assertion.phrase1, levels)
        stats2 = self._get_phrase_salience_stats(assertion.phrase2, levels)

        if stats1 is None:
            return False, f"Phrase 1 '{assertion.phrase1}' not found in output"
        if stats2 is None:
            return False, f"Phrase 2 '{assertion.phrase2}' not found in output"

        salience1, pct_lowest1, total1 = stats1
        salience2, pct_lowest2, total2 = stats2

        # Higher number = higher salience (deeper level = kept longer)
        # Tie-breaker: higher percentage of lowest-level words = lower salience
        if assertion.relation == AssertionType.LESS_THAN:
            # phrase1 < phrase2 means phrase1 has lower salience
            if salience1 < salience2:
                passed = True
            elif salience1 > salience2:
                passed = False
            else:
                passed = pct_lowest1 > pct_lowest2
            message = (
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"< Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✓)"
                if passed else
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"NOT < Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✗)"
            )
        elif assertion.relation == AssertionType.GREATER_THAN:
            # phrase1 > phrase2 means phrase1 has higher salience
            if salience1 > salience2:
                passed = True
            elif salience1 < salience2:
                passed = False
            else:
                passed = pct_lowest1 < pct_lowest2
            message = (
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"> Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✓)"
                if passed else
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"NOT > Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✗)"
            )
        elif assertion.relation == AssertionType.EQUAL:
            passed = salience1 == salience2 and pct_lowest1 == pct_lowest2
            message = (
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"== Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✓)"
                if passed else
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"!= Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✗)"
            )
        elif assertion.relation == AssertionType.GREATER_EQUAL:
            # phrase1 >= phrase2 means phrase1 has equal or higher salience
            if salience1 > salience2:
                passed = True
            elif salience1 < salience2:
                passed = False
            else:
                passed = pct_lowest1 <= pct_lowest2
            message = (
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f">= Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✓)"
                if passed else
                f"Salience({assertion.phrase1})={salience1} ({pct_lowest1:.2%} of {total1} words at level {salience1}) "
                f"NOT >= Salience({assertion.phrase2})={salience2} ({pct_lowest2:.2%} of {total2} words at level {salience2}) (✗)"
            )
        else:
            return False, f"Unknown assertion type: {assertion.relation}"

        # Message already includes pass/fail indicator
        return passed, message
    
    def run_test_case(self, test_case: TestCase) -> Dict:
        """Run a single test case and return results."""
        print(f"\n{'='*80}")
        print(f"Running test: {test_case.name}")
        print(f"Category: {test_case.category}")
        print(f"{'='*80}")
        print(f"Original text ({len(test_case.original_text.split())} words):")
        print(f"  {test_case.original_text[:200]}..." if len(test_case.original_text) > 200 else f"  {test_case.original_text}")
        
        try:
            # Run GP-TSM algorithm
            print("\nRunning GP-TSM algorithm...")
            result = llm.get_shortened_paragraph(test_case.original_text, self.api_key, system_message=self.system_message)
            
            # Extract levels (result is a list with one dict containing levels '0' through '4')
            if not result or len(result) == 0:
                return {
                    'test_name': test_case.name,
                    'passed': False,
                    'error': 'No output from algorithm',
                    'assertions': []
                }
            
            levels = result[0]  # Get the first (and only) dict
            
            # Check each assertion
            assertion_results = []
            all_passed = True
            warnings = []
            
            print(f"\nChecking {len(test_case.assertions)} assertions...")
            for i, assertion in enumerate(test_case.assertions, 1):
                passed, message = self._check_assertion(assertion, levels)
                
                if not passed:
                    if assertion.nice_to_have:
                        warnings.append(f"  Assertion {i} (nice-to-have): {message}")
                    else:
                        all_passed = False
                        print(f"  ✗ Assertion {i}: {message}")
                else:
                    print(f"  ✓ Assertion {i}: {message}")
                
                assertion_results.append({
                    'phrase1': assertion.phrase1,
                    'phrase2': assertion.phrase2,
                    'relation': assertion.relation.value,
                    'passed': passed,
                    'message': message,
                    'nice_to_have': assertion.nice_to_have
                })
            
            if warnings:
                print("\nWarnings (nice-to-have assertions):")
                for warning in warnings:
                    print(warning)
            
            # Print salience levels summary
            print("\nSalience levels summary:")
            for level in ['0', '1', '2', '3', '4']:
                if level in levels:
                    level_text = levels[level]
                    word_count = len(level_text.split())
                    print(f"  Level {level} ({word_count} words): {level_text[:100]}..." if len(level_text) > 100 else f"  Level {level} ({word_count} words): {level_text}")
            
            return {
                'test_name': test_case.name,
                'category': test_case.category,
                'passed': all_passed,
                'assertions': assertion_results,
                'warnings': len(warnings),
                'levels': {k: v[:200] + '...' if len(v) > 200 else v for k, v in levels.items()},  # Truncate for display
                'full_levels': levels,  # Store full levels for visualization (not truncated)
                'error': None
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"\n✗ ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                'test_name': test_case.name,
                'category': test_case.category,
                'passed': False,
                'error': error_msg,
                'assertions': [],
                'full_levels': None
            }
    
    def run_all_tests(self) -> Dict:
        """Run all test cases and return summary."""
        print(f"\n{'='*80}")
        print(f"GP-TSM Test Harness")
        print(f"Running {len(self.test_cases)} test case(s)")
        print(f"{'='*80}")
        
        self.results = []
        for test_case in self.test_cases:
            result = self.run_test_case(test_case)
            self.results.append(result)
        
        # Print summary
        self.print_summary()
        
        return {
            'total_tests': len(self.test_cases),
            'passed': sum(1 for r in self.results if r['passed']),
            'failed': sum(1 for r in self.results if not r['passed']),
            'results': self.results
        }
    
    def print_summary(self):
        """Print test summary."""
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        
        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed
        total_warnings = sum(r.get('warnings', 0) for r in self.results)
        
        print(f"Total tests: {total}")
        print(f"Passed: {passed} ✓")
        print(f"Failed: {failed} ✗")
        if total_warnings > 0:
            print(f"Warnings (nice-to-have): {total_warnings}")
        
        if failed > 0:
            print("\nFailed tests:")
            for result in self.results:
                if not result['passed']:
                    print(f"  ✗ {result['test_name']}")
                    if result.get('error'):
                        print(f"    Error: {result['error']}")
                    else:
                        failed_assertions = [a for a in result['assertions'] if not a['passed'] and not a['nice_to_have']]
                        print(f"    Failed assertions: {len(failed_assertions)}")
        
        print(f"{'='*80}")
    
    def save_results(self, filename: str = "test_results.json"):
        """Save test results to JSON file."""
        with open(filename, 'w') as f:
            json.dump({
                'summary': {
                    'total_tests': len(self.results),
                    'passed': sum(1 for r in self.results if r['passed']),
                    'failed': sum(1 for r in self.results if not r['passed'])
                },
                'results': self.results
            }, f, indent=2)
        print(f"\nResults saved to {filename}")


def load_legal_test_cases() -> List[TestCase]:
    """Load test cases from README (UK legal texts)."""
    test_cases = []
    
    # Test Case 1
    test_cases.append(TestCase(
        name="Test 1",
        original_text="This is because the impetus which may lead S to seek to be registered as the owner of adjacent land which S formerly thought was already his (or hers) will often be the raising by his neighbour O of a dispute as to his ownership, backed up by evidence in support, which destroys S's belief that it belongs to him, or at least makes his continuing belief unreasonable.",
        category="legal",
        assertions=[
            SalienceAssertion(
                phrase1="This is because",
                phrase2="the impetus",
                relation=AssertionType.LESS_THAN
            ),
            SalienceAssertion(
                phrase1="S's belief",
                phrase2="or at least makes his continuing belief unreasonable",
                relation=AssertionType.GREATER_THAN
            )
        ]
    ))
    
    # Test Case 2
    test_cases.append(TestCase(
        name="Test 2",
        original_text="The question of construction to be decided on this appeal arises because it is common ground that, as a matter of pure grammar, the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways, which I will call constructions A and B.",
        category="legal",
        assertions=[
            SalienceAssertion(
                phrase1="The question of construction to be decided on this appeal arises because",
                phrase2="it is common ground",
                relation=AssertionType.LESS_THAN
            ),
            SalienceAssertion(
                phrase1="the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways",
                phrase2="which I will call constructions A and B.",
                relation=AssertionType.GREATER_THAN
            )
        ]
    ))
    
    # Test Case 3
    test_cases.append(TestCase(
        name="Test 3",
        original_text="On 20 September 2002 the respondent Mr Brown was registered as proprietor of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham (\"the Brown land\").",
        category="legal",
        assertions=[
            SalienceAssertion(
                phrase1="On 20 September 2002",
                phrase2="the respondent Mr Brown was registered as proprietor",
                relation=AssertionType.LESS_THAN
            ),
            SalienceAssertion(
                phrase1="the respondent Mr Brown was registered as proprietor",
                phrase2="of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham",
                relation=AssertionType.GREATER_THAN
            ),
            SalienceAssertion(
                phrase1="the Brown land",
                phrase2="a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham",
                relation=AssertionType.GREATER_THAN,
                nice_to_have=True
            )
        ]
    ))
    
    # Test Case 4
    test_cases.append(TestCase(
        name="Test 4",
        original_text="On 8 July 2004 the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land to the North East of it, and also lying to the West of the Promenade, including a dwelling house known as Valley View.",
        category="legal",
        assertions=[
            SalienceAssertion(
                phrase1="On 8 July 2004",
                phrase2="the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land",
                relation=AssertionType.LESS_THAN
            )
        ]
    ))
    
    # Test Case 5: Cross-sentence assertion (would need special handling)
    # This is more complex and would require running both sentences together
    # For now, we'll note it but not implement it fully
    
    return test_cases


def main():
    """Main function to run test harness."""
    if len(sys.argv) < 2:
        print("Usage: python3 test_harness.py YOUR_API_KEY [test_name]")
        print("\nAvailable test categories:")
        print("  - legal: UK legal text test cases")
        print("\nTo run a specific test, provide the test name as second argument")
        sys.exit(1)
    
    api_key = sys.argv[1]
    test_name_filter = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Create test harness
    harness = TestHarness(api_key)
    
    # Load test cases
    print("Loading test cases...")
    legal_tests = load_legal_test_cases()
    
    # Add test cases to harness
    for test_case in legal_tests:
        if test_name_filter is None or test_name_filter.lower() in test_case.name.lower():
            harness.add_test_case(test_case)
    
    if len(harness.test_cases) == 0:
        print(f"No test cases found matching filter: {test_name_filter}")
        sys.exit(1)
    
    # Run tests
    summary = harness.run_all_tests()
    
    # Save results
    harness.save_results()
    
    # Exit with appropriate code
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == "__main__":
    main()
