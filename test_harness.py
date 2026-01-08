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
    description: str = ""
    nice_to_have: bool = False  # If True, failure is a warning, not an error


@dataclass
class TestCase:
    """Represents a test case."""
    name: str
    original_text: str
    assertions: List[SalienceAssertion]
    category: str = "legal"  # Category of test (legal, general, etc.)
    description: str = ""


class TestHarness:
    """Test harness for GP-TSM algorithm."""
    
    def __init__(self, api_key: str):
        """Initialize test harness with API key."""
        self.api_key = api_key
        self.test_cases: List[TestCase] = []
        self.results: List[Dict] = []
    
    def add_test_case(self, test_case: TestCase):
        """Add a test case to the harness."""
        self.test_cases.append(test_case)
    
    def _find_phrase_in_levels(self, phrase: str, levels: Dict[str, str]) -> Optional[int]:
        """
        Find the deepest level (highest number) where a phrase appears.
        In GP-TSM, deeper levels = higher salience (words kept through more shortenings).
        Level 4 = highest salience (kept in all shortenings, darkest in visualization)
        Level 0 = lowest salience (deleted early, lightest in visualization)
        
        Returns the level number (0-4) or None if not found.
        """
        import re
        
        phrase_lower = phrase.lower().strip()
        # Create a pattern that matches the phrase as a sequence of words
        # This handles punctuation and spacing variations
        phrase_pattern = r'\b' + re.escape(phrase_lower) + r'\b'
        # Also try without word boundaries for flexibility
        phrase_pattern_loose = phrase_lower.replace(' ', r'\s+')
        
        # Check each level from deepest (4) to shallowest (0)
        # We want the DEEPEST level where the phrase appears
        for level in ['4', '3', '2', '1', '0']:
            if level in levels:
                level_text = levels[level].lower()
                
                # Try strict word boundary match first
                if re.search(phrase_pattern, level_text):
                    return int(level)
                # Fall back to loose matching (allows spacing variations)
                elif re.search(phrase_pattern_loose, level_text):
                    return int(level)
                # Fall back to simple substring match (for robustness)
                elif phrase_lower in level_text:
                    return int(level)
        
        return None
    
    def _get_max_salience(self, phrase: str, levels: Dict[str, str]) -> Optional[int]:
        """
        Get the maximum salience (deepest level number) for a phrase.
        Higher number = higher salience (phrase kept through more shortenings).
        Returns the level number (0-4) or None if not found.
        """
        return self._find_phrase_in_levels(phrase, levels)
    
    def _check_assertion(self, assertion: SalienceAssertion, levels: Dict[str, str]) -> Tuple[bool, str]:
        """
        Check if an assertion holds given the salience levels.
        Returns (passed, message).
        """
        salience1 = self._get_max_salience(assertion.phrase1, levels)
        salience2 = self._get_max_salience(assertion.phrase2, levels)
        
        if salience1 is None:
            return False, f"Phrase 1 '{assertion.phrase1}' not found in output"
        if salience2 is None:
            return False, f"Phrase 2 '{assertion.phrase2}' not found in output"
        
        # Higher number = higher salience (deeper level = kept longer)
        # So if phrase1 has lower salience than phrase2, phrase1's level number is smaller
        if assertion.relation == AssertionType.LESS_THAN:
            # phrase1 < phrase2 means phrase1 has lower salience (smaller level number)
            passed = salience1 < salience2
            message = f"Salience({assertion.phrase1})={salience1} < Salience({assertion.phrase2})={salience2} (✓)" if passed else f"Salience({assertion.phrase1})={salience1} NOT < Salience({assertion.phrase2})={salience2} (✗)"
        elif assertion.relation == AssertionType.GREATER_THAN:
            # phrase1 > phrase2 means phrase1 has higher salience (larger level number)
            passed = salience1 > salience2
            message = f"Salience({assertion.phrase1})={salience1} > Salience({assertion.phrase2})={salience2} (✓)" if passed else f"Salience({assertion.phrase1})={salience1} NOT > Salience({assertion.phrase2})={salience2} (✗)"
        elif assertion.relation == AssertionType.EQUAL:
            passed = salience1 == salience2
            message = f"Salience({assertion.phrase1})={salience1} == Salience({assertion.phrase2})={salience2} (✓)" if passed else f"Salience({assertion.phrase1})={salience1} != Salience({assertion.phrase2})={salience2} (✗)"
        elif assertion.relation == AssertionType.GREATER_EQUAL:
            # phrase1 >= phrase2 means phrase1 has equal or higher salience (larger or equal level number)
            passed = salience1 >= salience2
            message = f"Salience({assertion.phrase1})={salience1} >= Salience({assertion.phrase2})={salience2} (✓)" if passed else f"Salience({assertion.phrase1})={salience1} NOT >= Salience({assertion.phrase2})={salience2} (✗)"
        else:
            return False, f"Unknown assertion type: {assertion.relation}"
        
        # Message already includes pass/fail indicator
        return passed, message
    
    def run_test_case(self, test_case: TestCase) -> Dict:
        """Run a single test case and return results."""
        print(f"\n{'='*80}")
        print(f"Running test: {test_case.name}")
        print(f"Category: {test_case.category}")
        if test_case.description:
            print(f"Description: {test_case.description}")
        print(f"{'='*80}")
        print(f"Original text ({len(test_case.original_text.split())} words):")
        print(f"  {test_case.original_text[:200]}..." if len(test_case.original_text) > 200 else f"  {test_case.original_text}")
        
        try:
            # Run GP-TSM algorithm
            print("\nRunning GP-TSM algorithm...")
            result = llm.get_shortened_paragraph(test_case.original_text, self.api_key)
            
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
                'levels': {k: v[:200] + '...' if len(v) > 200 else v for k, v in levels.items()},  # Truncate for storage
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
                'assertions': []
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
        name="Legal Test 1: Impetus and ownership dispute",
        original_text="This is because the impetus which may lead S to seek to be registered as the owner of adjacent land which S formerly thought was already his (or hers) will often be the raising by his neighbour O of a dispute as to his ownership, backed up by evidence in support, which destroys S's belief that it belongs to him, or at least makes his continuing belief unreasonable.",
        category="legal",
        description="Complex legal sentence about land ownership disputes",
        assertions=[
            SalienceAssertion(
                phrase1="This is because",
                phrase2="the impetus",
                relation=AssertionType.LESS_THAN,
                description="Opening phrase should have lower salience than main subject"
            ),
            SalienceAssertion(
                phrase1="S's belief",
                phrase2="or at least makes his continuing belief unreasonable",
                relation=AssertionType.GREATER_THAN,
                description="Core concept should have higher salience than elaboration"
            )
        ]
    ))
    
    # Test Case 2
    test_cases.append(TestCase(
        name="Legal Test 2: Question of construction",
        original_text="The question of construction to be decided on this appeal arises because it is common ground that, as a matter of pure grammar, the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways, which I will call constructions A and B.",
        category="legal",
        description="Legal sentence about construction interpretation",
        assertions=[
            SalienceAssertion(
                phrase1="The question of construction to be decided on this appeal arises because",
                phrase2="it is common ground",
                relation=AssertionType.LESS_THAN,
                description="Background should have lower salience than main point"
            ),
            SalienceAssertion(
                phrase1="the italicised passage in paragraph 5(4)(c) of Schedule 6 can be read in two ways",
                phrase2="which I will call constructions A and B.",
                relation=AssertionType.GREATER_THAN,
                description="Main content should have higher salience than naming"
            )
        ]
    ))
    
    # Test Case 3
    test_cases.append(TestCase(
        name="Legal Test 3: Land registration (Mr Brown)",
        original_text="On 20 September 2002 the respondent Mr Brown was registered as proprietor of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham (\"the Brown land\").",
        category="legal",
        description="Land registration record",
        assertions=[
            SalienceAssertion(
                phrase1="On 20 September 2002",
                phrase2="the respondent Mr Brown was registered as proprietor",
                relation=AssertionType.LESS_THAN,
                description="Date should have lower salience than main action"
            ),
            SalienceAssertion(
                phrase1="the respondent Mr Brown was registered as proprietor",
                phrase2="of a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham",
                relation=AssertionType.GREATER_THAN,
                description="Main action should have higher salience than location details"
            ),
            SalienceAssertion(
                phrase1="the Brown land",
                phrase2="a substantial piece of rough, undeveloped land lying to the West of The Promenade, Consett, County Durham",
                relation=AssertionType.GREATER_THAN,
                description="Short reference should have higher salience than full description",
                nice_to_have=True
            )
        ]
    ))
    
    # Test Case 4
    test_cases.append(TestCase(
        name="Legal Test 4: Land registration (Mr and Mrs Ridley)",
        original_text="On 8 July 2004 the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land to the North East of it, and also lying to the West of the Promenade, including a dwelling house known as Valley View.",
        category="legal",
        description="Land registration record for second party",
        assertions=[
            SalienceAssertion(
                phrase1="On 8 July 2004",
                phrase2="the appellants Mr and Mrs Ridley were registered as proprietors of land adjoining part of the Brown land",
                relation=AssertionType.LESS_THAN,
                description="Date should have lower salience than main action"
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
