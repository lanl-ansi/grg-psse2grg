import os, pytest

import collections
import warnings
warnings.filterwarnings('error')

from grg_grgdata.cmd import components_by_type

import grg_psse2grg

class Test5Bus:
    def setup_method(self, _):
        """Parse a real network file"""
        self.psse_case = grg_psse2grg.io.parse_psse_case_file(os.path.dirname(os.path.realpath(__file__))+'/data/correct/case5_000.raw')

    def test_001(self):
        #print(self.psse_case.to_grg())
        grg_case = self.psse_case.to_grg('case name')
        components = components_by_type(grg_case)
        assert len(components['bus']) == 5

    def test_002(self):
        grg_case = self.psse_case.to_grg('case name')
        components = components_by_type(grg_case)

        line_count = len(components['ac_line'])
        transformer_count = len(components['two_winding_transformer'])
        assert line_count + transformer_count == 7


class TestGRGVariants:
    def test_no_operations(self):
        grg_case = grg_psse2grg.io.parse_psse_case_file(os.path.dirname(os.path.realpath(__file__))+'/data/correct/case5_000.raw').to_grg('case name')
        del grg_case['operation_constraints']

        psse_case = grg_psse2grg.io.build_psse_case(grg_case, 'starting_points', 'breakers_assignment')

        assert len(psse_case.buses) == 5
        assert len(psse_case.branches) == 6
        assert len(psse_case.generators) == 5

    def test_no_market(self):
        grg_case = grg_psse2grg.io.parse_psse_case_file(os.path.dirname(os.path.realpath(__file__))+'/data/correct/case5_000.raw').to_grg('case name')
        del grg_case['market']

        psse_case = grg_psse2grg.io.build_psse_case(grg_case, 'starting_points', 'breakers_assignment')

        assert len(psse_case.buses) == 5
        assert len(psse_case.branches) == 6
        assert len(psse_case.generators) == 5

    def test_no_groups(self):
        grg_case = grg_psse2grg.io.parse_psse_case_file(os.path.dirname(os.path.realpath(__file__))+'/data/correct/case5_000.raw').to_grg('case name')
        del grg_case['groups']

        psse_case = grg_psse2grg.io.build_psse_case(grg_case, 'starting_points', 'breakers_assignment')

        assert len(psse_case.buses) == 5
        assert len(psse_case.branches) == 6
        assert len(psse_case.generators) == 5

