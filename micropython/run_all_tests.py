import subprocess
import sys
import os
import re

# Use process-level isolation for host-side unit tests
test_modules = [
    'tests.test_drivewire',
    'tests.test_resilience',
    'tests.test_web_api',
    'tests.test_os9_disk'
]

def run_tests():
    total_passed = 0
    total_failed = 0
    
    env = os.environ.copy()
    root_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(root_dir, 'tests')
    env['PYTHONPATH'] = root_dir + os.pathsep + tests_dir + os.pathsep + env.get('PYTHONPATH', '')
    
    print("=" * 60)
    print("DRIVEWIRE MASTER TEST RUNNER (ASCII Mode)")
    print("=" * 60)
    
    for module in test_modules:
        print(f"\n[{module}] Running...")
        result = subprocess.run([sys.executable, '-m', 'unittest', module], 
                               capture_output=True, text=True, env=env)
        
        print(result.stderr)
        
        if result.returncode == 0 and "OK" in result.stderr:
            print(f"RESULT: {module} PASSED")
            match = re.search(r"Ran (\d+) tests", result.stderr)
            if match:
                total_passed += int(match.group(1))
        else:
            print(f"RESULT: {module} FAILED")
            match = re.search(r"Ran (\d+) tests", result.stderr)
            if match:
                total_failed += int(match.group(1))
            else:
                total_failed += 1

    print("\n" + "=" * 60)
    print(f"FINAL CONSOLIDATED SUMMARY:")
    print(f"Total Tests Passed: {total_passed}")
    print(f"Total Tests Failed: {total_failed}")
    print("=" * 60)
    
    if total_failed == 0 and total_passed > 0:
        print(f"STATUS: ABSOLUTE GREEN ({total_passed}/{total_passed})")
        sys.exit(0)
    else:
        print("STATUS: RED (Failing or incomplete)")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
