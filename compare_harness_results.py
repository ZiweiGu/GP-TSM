#!/usr/bin/env python3
import sys
import llm
from test_harness import TestHarness, load_legal_test_cases

def run_tests(api_key, system_message, label):
    print(f"\nRunning {label} Tests...")
    harness = TestHarness(api_key, system_message=system_message)
    # Load only legal test cases
    legal_tests = load_legal_test_cases()
    for test_case in legal_tests:
        harness.add_test_case(test_case)
    
    summary = harness.run_all_tests()
    return summary

def print_comparison(baseline, experimental):
    print(f"\n{'='*80}")
    print("COMPARISON RESULTS: Baseline vs. UK Law System Message")
    print(f"{'='*80}")
    
    header = f"{ 'Test Name':<15} | {'Baseline':<10} | {'UK Law':<10} | {'Diff'}"
    print(header)
    print("-" * len(header))
    
    baseline_results = {r['test_name']: r for r in baseline['results']}
    experimental_results = {r['test_name']: r for r in experimental['results']}
    
    for name, base_res in baseline_results.items():
        exp_res = experimental_results.get(name)
        if not exp_res:
            continue
            
        base_pass = "PASS" if base_res['passed'] else "FAIL"
        exp_pass = "PASS" if exp_res['passed'] else "FAIL"
        
        diff = ""
        if base_pass != exp_pass:
            diff = "Mismatch!"
            
        # Count assertions
        base_asserts = sum(1 for a in base_res['assertions'] if a['passed'])
        base_total = len(base_res['assertions'])
        exp_asserts = sum(1 for a in exp_res['assertions'] if a['passed'])
        exp_total = len(exp_res['assertions'])
        
        # Add assertion counts to status
        base_str = f"{base_pass} ({base_asserts}/{base_total})"
        exp_str = f"{exp_pass} ({exp_asserts}/{exp_total})"
        
        print(f"{name:<15} | {base_str:<10} | {exp_str:<10} | {diff}")

    print(f"{'='*80}")
    print("Interpretation:")
    print("- PASS/FAIL indicates if all assertions (excluding 'nice-to-have') were met.")
    print("- Numbers (X/Y) indicate how many individual assertions passed out of total.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 compare_harness_results.py API_KEY")
        sys.exit(1)
        
    api_key = sys.argv[1]
    
    print(">>> Starting Baseline Run (No System Message)...")
    baseline_summary = run_tests(api_key, None, "Baseline")
    
    print("\n>>> Starting Experimental Run (UK Law System Message)...")
    experimental_summary = run_tests(api_key, llm.UK_LAW_SYSTEM_MESSAGE, "UK Law")
    
    print_comparison(baseline_summary, experimental_summary)

if __name__ == "__main__":
    main()
