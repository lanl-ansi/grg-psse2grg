import os, pytest

import grg_psse2grg
import grg_pssedata

import warnings
#warnings.filterwarnings('error')

from test_common import idempotent_files

#@pytest.mark.filterwarnings('error')
warnings.simplefilter('always')
@pytest.mark.parametrize('input_data', idempotent_files)
def test_001(input_data):
    case, case_2 = grg_psse2grg.io.test_idempotent(input_data, 'test-network')
    #assert case == case_2 # checks full data structure
    #assert not case != case_2
    #assert str(case) == str(case_2) # checks string representation of data structure

    diff_count = grg_pssedata.cmd.diff(case, case_2)
    assert diff_count <= 0

