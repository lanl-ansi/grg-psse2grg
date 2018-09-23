import os, pytest, re

import grg_psse2grg

import warnings
#warnings.filterwarnings('error')

from test_common import correct_files

#warnings.simplefilter('always')
@pytest.mark.parametrize('input_data', correct_files)
def test_001(input_data):
    case, case_2 = grg_psse2grg.io.test_idempotent(input_data, 'test-network')

    assert len(case.buses) == len(case_2.buses)
    # assert len(case.gen) == len(case_2.gen)
    # assert len(case.branch) == len(case_2.branch)

    # if case.gencost != None:
    #     assert len(case.gencost) == len(case_2.gencost)
    # else:
    #     assert case_2.gencost == None

    # if case.dcline != None:
    #     assert len(case.dcline) == len(case_2.dcline)
    # else:
    #     assert case_2.dcline == None

    # if case.dclinecost != None:
    #     assert len(case.dclinecost) == len(case_2.dclinecost)
    # else:
    #     assert case_2.dclinecost == None

    # if case.busname != None:
    #     assert len(case.busname) == len(case_2.busname)
    # else:
    #     assert case_2.busname == None


