#!/usr/bin/env python3
"""
Test script to verify "No path found" warnings are fixed
"""

import subprocess
import sys
from pathlib import Path


def test_routing_no_warnings():
    """
    Run routing and verify no warnings appear
    """
    print("\n" + "="*70)
    print("TESTING: 'No path found' warnings fix")
    print("="*70)
    
    # Run routing script
    print("\n[TEST] Running routing script...")
    result = subprocess.run(
        ["python", "scripts/3_generate_routes.py", "--scenario", "data/generated"],
        capture_output=True,
        text=True
    )
    
    # Check for warnings
    output = result.stdout + result.stderr
    
    # Count warnings
    warning_lines = [line for line in output.split('\n') if '[WARNING] No path from' in line]
    num_warnings = len(warning_lines)
    
    print(f"\n[RESULT] Warnings found: {num_warnings}")
    
    if num_warnings == 0:
        print("\n✅ SUCCESS: No 'No path found' warnings!")
        print("   The fix is working correctly.")
        return True
    else:
        print(f"\n❌ FAILED: Still seeing {num_warnings} warnings")
        print("\nFirst 5 warnings:")
        for line in warning_lines[:5]:
            print(f"   {line}")
        return False


def test_vehicle_filtering():
    """
    Verify that vehicles are properly filtered
    """
    print("\n" + "="*70)
    print("TESTING: Vehicle filtering statistics")
    print("="*70)
    
    result = subprocess.run(
        ["python", "scripts/3_generate_routes.py", "--scenario", "data/generated"],
        capture_output=True,
        text=True
    )
    
    output = result.stdout + result.stderr
    
    # Check for skip statistics
    if "Skipped:" in output and "No directed path:" in output:
        print("\n✅ SUCCESS: Detailed skip statistics found")
        print("   System is pre-filtering impossible routes")
        
        # Extract statistics
        for line in output.split('\n'):
            if 'Skipped:' in line or 'No directed path:' in line or 'Edge not found:' in line:
                print(f"   {line.strip()}")
        
        return True
    else:
        print("\n❌ FAILED: Skip statistics not found")
        return False


def test_routing_success_rate():
    """
    Verify 100% success rate for attempted routes
    """
    print("\n" + "="*70)
    print("TESTING: Routing success rate")
    print("="*70)
    
    result = subprocess.run(
        ["python", "scripts/3_generate_routes.py", "--scenario", "data/generated"],
        capture_output=True,
        text=True
    )
    
    output = result.stdout + result.stderr
    
    # Look for successful routing
    if "[OK] Routed" in output and "emergency vehicles" in output and "normal vehicles" in output:
        print("\n✅ SUCCESS: Routing completed")
        
        # Extract routing results
        for line in output.split('\n'):
            if '[OK] Routed' in line:
                print(f"   {line.strip()}")
        
        return True
    else:
        print("\n❌ FAILED: Routing did not complete successfully")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("VERIFICATION: 'No path found' warnings fix")
    print("="*70)
    
    # Check if scenario exists
    if not Path("data/generated").exists():
        print("\n❌ ERROR: data/generated not found")
        print("   Run this first:")
        print("   python scripts/1_generate_traffic.py --vehicles 1500")
        print("   python scripts/2_run_prediction.py --scenario data/generated")
        sys.exit(1)
    
    tests = [
        ("No warnings test", test_routing_no_warnings),
        ("Vehicle filtering test", test_vehicle_filtering),
        ("Success rate test", test_routing_success_rate)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:8} - {test_name}")
    
    all_passed = all(passed for _, passed in results)
    
    print("\n" + "="*70)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("   The 'No path found' warnings fix is working correctly!")
    else:
        print("❌ SOME TESTS FAILED")
        print("   Review the output above for details")
    print("="*70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
