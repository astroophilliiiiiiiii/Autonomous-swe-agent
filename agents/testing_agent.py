from tools.test_tools import run_tests


def testing_agent(repo_path):

    result = run_tests(repo_path)

    if result.returncode == 0:  # return failed testcases 
        return "PASS ✅\n" + result.stdout   # if 0 failed then PASS \n result.stdout => itne passed 

    return "FAIL ❌\n" + result.stdout + result.stderr # else FAIL  5 FAILED 1 PASSED err ( jo v tha )