''' extensions to data structures for encoding psse data files to 
support grg data encoding'''

import inspect, json, math

import warnings

# from grg_mpdata.exception import MPDataValidationError
from grg_psse2grg.exception import PSSE2GRGWarning

import grg_pssedata.struct
# from grg_mpdata.struct import _guard_none

from grg_grgdata.cmd import validate_grg
import grg_grgdata.common as grg_common

grg_description_preamble = 'Translated from PSS/E v33 data by grg-psse2grg.  Source file description:'

default_voltage_angle_difference = 0.5236 # 30 deg. in rad

# TODO data format strings below should come from grg-grgdata project 
class Case(grg_pssedata.struct.Case):

    def to_grg(self, network_id, omit_subtype=False, skip_validation=False):
        '''Returns: an encoding of this data structure as a grg data dictionary'''
        #start = time.time()

        data = {}

        data['grg_version'] = grg_common.grg_version
        data['units'] = grg_common.grg_units

        network = {}
        data['network'] = network

        network['type'] = 'network'
        network['subtype'] = 'bus_breaker'
        network['id'] = network_id
        network['per_unit'] = True
        network['description'] = '%s\n%s\n%s' % (grg_description_preamble, self.record1, self.record2)

        base_mva = self.sbase
        network['ic'] = self.ic

        comp_lookup = self._grg_component_lookup()

        network_components, groups, switch_status = self._grg_components(comp_lookup, base_mva, omit_subtype)
        network['components'] = network_components
        data['groups'] = groups
        data['mappings'] = self._grg_mappings(comp_lookup, switch_status, base_mva)
        data['market'] = self._grg_market(comp_lookup, base_mva)
        data['operation_constraints'] = self._grg_operations(comp_lookup)


        if skip_validation:
            return data

        #return data
        #print(time.time() - start)
        #start = time.time()
        #print('start validation')
        if validate_grg(data):
            #print('VALID ****')
            #print(time.time() - start)
            return data
        else:
            print('incorrect grg data representation.')
            print(json.dumps(data, sort_keys=True, indent=2, \
                                 separators=(',', ': ')))
            print('This is a bug in grg_psse2grg')
            print('')
        return None


    def _grg_component_lookup(self):
        lookup = {
            'voltage':{},
            'bus':{},
            'load':{},
            'fixed_shunt':{},
            'switched_shunt':{},
            'gen':{},
            'branch':{},
            'transformer':{},
            'area':{},
            'zone':{},
            'owner':{}
        }

        zeros = grg_common.calc_zeros(len(self.buses))
        for index, bus in enumerate(self.buses):
            grg_bus_id = grg_common.bus_name_template % str(index+1).zfill(zeros)
            lookup['bus'][bus.i] = grg_bus_id

            grg_voltage_id = grg_common.bus_voltage_name_template % str(index+1).zfill(zeros)
            lookup['voltage'][bus.i] = grg_voltage_id


        zeros = grg_common.calc_zeros(len(self.loads))
        for load in self.loads:
            grg_load_id = grg_common.load_name_template % str(load.index+1).zfill(zeros)
            lookup['load'][load.index] = grg_load_id


        shunt_count = 1
        zeros = grg_common.calc_zeros(len(self.fixed_shunts)+len(self.switched_shunts)) #int(math.ceil(math.log(len(self.fixed_shunts)+len(self.switched_shunts)), 10))
        for fixed_shunt in self.fixed_shunts:
            grg_shunt_id = grg_common.shunt_name_template % str(shunt_count).zfill(zeros)
            lookup['fixed_shunt'][fixed_shunt.index] = grg_shunt_id
            shunt_count += 1


        for switched_shunt in self.switched_shunts:
            grg_shunt_id = grg_common.shunt_name_template % str(shunt_count).zfill(zeros)
            lookup['switched_shunt'][switched_shunt.index] = grg_shunt_id
            shunt_count += 1


        zeros = grg_common.calc_zeros(len(self.areas))
        for i, area in enumerate(self.areas):
            lookup['area'][area.i] = grg_common.area_name_template % str(i+1).zfill(zeros)

        zeros = grg_common.calc_zeros(len(self.zones))
        for i, zone in enumerate(self.zones):
            lookup['zone'][zone.i] = grg_common.zone_name_template % str(i+1).zfill(zeros)

        zeros = grg_common.calc_zeros(len(self.owners))
        for i, owner in enumerate(self.owners):
            lookup['owner'][owner.i] = grg_common.owner_name_template % str(i+1).zfill(zeros)


        gen_count = 1
        sync_cond_count = 1
        zeros = grg_common.calc_zeros(len(self.generators))
        for gen in self.generators:
            if not gen.is_synchronous_condenser():
                grg_gen_id = grg_common.generator_name_template % str(gen_count).zfill(zeros)
                lookup['gen'][gen.index] = grg_gen_id
                gen_count += 1
            else:
                grg_gen_id = grg_common.sync_cond_name_template % str(sync_cond_count).zfill(zeros)
                lookup['gen'][gen.index] = grg_gen_id
                sync_cond_count += 1


        zeros = grg_common.calc_zeros(len(self.branches))
        for branch in self.branches:
            grg_branch_id = grg_common.line_name_template % str(branch.index+1).zfill(zeros)
            lookup['branch'][branch.index] = grg_branch_id


        zeros = grg_common.calc_zeros(len(self.transformers))
        for transformer in self.transformers:
            grg_transformer_id = grg_common.transformer_name_template % str(transformer.index+1).zfill(zeros)
            lookup['transformer'][transformer.index] = grg_transformer_id

        return lookup


    def _grg_components(self, lookup, base_mva, omit_subtype=False):
        components = {}
        groups = {}


        for area in self.areas:
            grg_id = lookup['area'][area.i]
            assert(not grg_id in groups)
            groups[grg_id] = {
                'type': 'area',
                'name': area.arnam,
                'source_id': str(area.i),
                'isw': area.isw,
                'pdes': area.pdes,
                'ptol': area.ptol,
                'component_ids':[]
            }

        for zone in self.zones:
            grg_id = lookup['zone'][zone.i]
            assert(not grg_id in groups)
            groups[grg_id] = {
                'type': 'zone',
                'name': zone.zoname,
                'source_id': str(zone.i),
                'component_ids':[]
            }

        for owner in self.owners:
            grg_id = lookup['owner'][owner.i]
            assert(not grg_id in groups)
            groups[grg_id] = {
                'type': 'owner',
                'name': owner.owname,
                'source_id': str(owner.i),
                'component_ids':[]
            }


        psse_bus_lookup = {bus.i:bus for bus in self.buses}

        switch_count = 1
        switch_zeros = grg_common.calc_zeros(
            len(self.buses)+len(self.loads)+len(self.fixed_shunts)+
            len(self.switched_shunts)+len(self.generators)+
            2*len(self.branches)+2*len(self.transformers)
        )
        switch_status = {}

        lookup['voltage_level'] = {}
        voltage_levels = {}
        zeros = int(math.ceil(math.log(len(self.buses), 10)))
        for index, bus in enumerate(self.buses):
            grg_vl_id = grg_common.voltage_level_name_template % str(index+1).zfill(zeros)
            voltage_levels[grg_vl_id] = {
                'id': grg_vl_id,
                'type': 'voltage_level',
                'voltage':{
                    'lower_limit': bus.nvlo,
                    'upper_limit': bus.nvhi,
                    'nominal_value': bus.basekv
                },
                'voltage_points':[],
                'voltage_level_components':{},
            }
            lookup['voltage_level'][bus.i] = grg_vl_id



        for bus in self.buses:
            bus_data = bus.to_grg_bus(lookup)
            grg_bus_id = lookup['bus'][bus.i]
            grg_vl_id = lookup['voltage_level'][bus.i]
            voltage_levels[grg_vl_id]['voltage_points'].append(lookup['voltage'][bus.i])

            vl_components = voltage_levels[grg_vl_id]['voltage_level_components']
            vl_components[grg_bus_id] = bus_data

            if bus.area in lookup['area']:
                groups[lookup['area'][bus.area]]['component_ids'].append(grg_bus_id)
            else:
                warnings.warn('area id %s in bus %s was found in the areas table.' % (str(bus.area), str(bus.i)), PSSE2GRGWarning)

            if bus.zone in lookup['zone']:
                groups[lookup['zone'][bus.zone]]['component_ids'].append(grg_bus_id)
            else:
                warnings.warn('zone id %s in bus %s was found in the areas table.' % (str(bus.zone), str(bus.i)), PSSE2GRGWarning)

            if bus.owner in lookup['owner']:
                groups[lookup['owner'][bus.owner]]['component_ids'].append(grg_bus_id)
            else:
                warnings.warn('owner id %s in bus %s was found in the owners table.' % (str(bus.owner), str(bus.i)), PSSE2GRGWarning)


        for load in self.loads:
            load_data = load.to_grg_load(lookup, base_mva, omit_subtype)
            grg_load_id = lookup['load'][load.index]
            grg_vl_id = lookup['voltage_level'][load.i]

            switch, switch_voltage_id = self._insert_switch(load_data, switch_count, switch_zeros)
            switch_status[switch['id']] = self._combine_status(load, psse_bus_lookup[load.i])
            switch_count += 1

            voltage_levels[grg_vl_id]['voltage_points'].append(switch_voltage_id)
            vl_components = voltage_levels[grg_vl_id]['voltage_level_components']
            vl_components[grg_load_id] = load_data
            vl_components[switch['id']] = switch

            if load.area in lookup['area']:
                groups[lookup['area'][load.area]]['component_ids'].append(grg_load_id)
            else:
                pass # is given by the bus area

            if load.zone in lookup['zone']:
                groups[lookup['zone'][load.zone]]['component_ids'].append(grg_load_id)
            else:
                pass # is given by the bus zone

            if load.owner in lookup['owner']:
                groups[lookup['owner'][load.owner]]['component_ids'].append(grg_load_id)
            else:
                pass # is given by the bus owner


        for fixed_shunt in self.fixed_shunts:
            shunt_data = fixed_shunt.to_grg_shunt(lookup, base_mva, omit_subtype)
            grg_shunt_id = lookup['fixed_shunt'][fixed_shunt.index]
            grg_vl_id = lookup['voltage_level'][fixed_shunt.i]

            switch, switch_voltage_id = self._insert_switch(shunt_data, switch_count, switch_zeros)
            switch_status[switch['id']] = self._combine_status(fixed_shunt, psse_bus_lookup[fixed_shunt.i])
            switch_count += 1

            voltage_levels[grg_vl_id]['voltage_points'].append(switch_voltage_id)
            vl_components = voltage_levels[grg_vl_id]['voltage_level_components']
            vl_components[grg_shunt_id] = shunt_data
            vl_components[switch['id']] = switch

        for switched_shunt in self.switched_shunts:
            switched_data = switched_shunt.to_grg_shunt(lookup, base_mva, omit_subtype)
            grg_shunt_id = lookup['switched_shunt'][switched_shunt.index]
            grg_vl_id = lookup['voltage_level'][switched_shunt.i]

            switch, switch_voltage_id = self._insert_switch(switched_data, switch_count, switch_zeros)
            switch_status[switch['id']] = self._combine_status(switched_shunt, psse_bus_lookup[switched_shunt.i])
            switch_count += 1

            voltage_levels[grg_vl_id]['voltage_points'].append(switch_voltage_id)
            vl_components = voltage_levels[grg_vl_id]['voltage_level_components']
            vl_components[grg_shunt_id] = switched_data
            vl_components[switch['id']] = switch

        for gen in self.generators:
            gen_data = gen.to_grg_generator(lookup, base_mva, omit_subtype)
            grg_gen_id = lookup['gen'][gen.index]
            grg_vl_id = lookup['voltage_level'][gen.i]

            switch, switch_voltage_id = self._insert_switch(gen_data, switch_count, switch_zeros)
            switch_status[switch['id']] = self._combine_status(gen, psse_bus_lookup[gen.i])
            switch_count += 1

            voltage_levels[grg_vl_id]['voltage_points'].append(switch_voltage_id)
            vl_components = voltage_levels[grg_vl_id]['voltage_level_components']
            vl_components[grg_gen_id] = gen_data
            vl_components[switch['id']] = switch

            self._grg_add_owners(lookup, groups, gen, grg_gen_id)

        # not supported in GRG v1.5
        # if self.dcline is not None:
        #     for dcline in self.dcline:
        #         dcline_data = dcline.to_grg_dcline(lookup, base_mva, omit_subtype)
        #         grg_dcline_id = lookup['dcline'][dcline.index]
        #         components[grg_dcline_id] = dcline_data

        for branch in self.branches:
            branch_data = branch.to_grg_line(lookup, base_mva, omit_subtype)
            grg_branch_id = lookup['branch'][branch.index]

            grg_vl_id_1 = lookup['voltage_level'][branch.i]
            grg_vl_id_2 = lookup['voltage_level'][branch.j]

            switch_1, switch_voltage_id_1, switch_2, switch_voltage_id_2 = self._insert_switches(branch_data, switch_count, switch_zeros)
            switch_status[switch_1['id']] = self._combine_status(branch, psse_bus_lookup[branch.i])
            switch_status[switch_2['id']] = self._combine_status(branch, psse_bus_lookup[branch.j])
            switch_count += 2

            components[grg_branch_id] = branch_data
            voltage_levels[grg_vl_id_1]['voltage_points'].append(switch_voltage_id_1)
            voltage_levels[grg_vl_id_1]['voltage_level_components'][switch_1['id']] = switch_1

            voltage_levels[grg_vl_id_2]['voltage_points'].append(switch_voltage_id_2)
            voltage_levels[grg_vl_id_2]['voltage_level_components'][switch_2['id']] = switch_2

            self._grg_add_owners(lookup, groups, branch, grg_branch_id)


        # cluster buses into substations based on transformers
        bus_sub = {}
        for bus in self.buses:
            bus_id = bus.i
            bus_sub[bus_id] = set([bus_id])

        for transformer in self.transformers:
            if not transformer.is_three_winding():
                bus_id_set = bus_sub[transformer.p1.i] | bus_sub[transformer.p1.j]
            else: # must be three-winding
                bus_id_set = bus_sub[transformer.p1.i] | bus_sub[transformer.p1.j] | bus_sub[transformer.p1.k]

            for bus_id in bus_id_set:
                bus_sub[bus_id] = bus_id_set

        sub_buses = {frozenset(buses) for buses in bus_sub.values()}

        lookup['substation'] = {}
        substations = {}
        zeros = int(math.ceil(math.log(len(self.buses), 10)))
        for index, buses in enumerate(sorted(sub_buses, key=lambda x: min(x))):
            grg_ss_id = grg_common.substation_name_template % str(index+1).zfill(zeros)
            #print(grg_ss_id, buses)
            components[grg_ss_id] = {
                'id': grg_ss_id,
                'type': 'substation',
                'substation_components':{}
            }
            for bus_id in buses:
                lookup['substation'][bus_id] = grg_ss_id


        for bus in self.buses:
            grg_vl_id = lookup['voltage_level'][bus.i]
            grg_ss_id = lookup['substation'][bus.i]
            components[grg_ss_id]['substation_components'][grg_vl_id] = voltage_levels[grg_vl_id]


        for transformer in self.transformers:
            if not transformer.is_three_winding():
                p_grg_ss_id = lookup['substation'][transformer.p1.i]
                s_grg_ss_id = lookup['substation'][transformer.p1.j]
                assert(p_grg_ss_id == s_grg_ss_id) # clustering code failed

                grg_vl_id_1 = lookup['voltage_level'][transformer.p1.i]
                grg_vl_id_2 = lookup['voltage_level'][transformer.p1.j]
                assert(grg_vl_id_1 != grg_vl_id_2) # voltage level setting code failed

                transformer_data = transformer.to_grg_two_winding_transformer(lookup, base_mva, omit_subtype)

                switch_1, switch_voltage_id_1, switch_2, switch_voltage_id_2 = self._insert_switches(transformer_data, switch_count, switch_zeros)
                switch_status[switch_1['id']] = self._combine_status(transformer, psse_bus_lookup[transformer.p1.i])
                switch_status[switch_2['id']] = self._combine_status(transformer, psse_bus_lookup[transformer.p1.j])
                switch_count += 2

                grg_transformer_id = lookup['transformer'][transformer.index]
                components[p_grg_ss_id]['substation_components'][grg_transformer_id] = transformer_data
                voltage_levels[grg_vl_id_1]['voltage_points'].append(switch_voltage_id_1)
                voltage_levels[grg_vl_id_1]['voltage_level_components'][switch_1['id']] = switch_1

                voltage_levels[grg_vl_id_2]['voltage_points'].append(switch_voltage_id_2)
                voltage_levels[grg_vl_id_2]['voltage_level_components'][switch_2['id']] = switch_2

            else: # must be three-winding
                p_grg_ss_id = lookup['substation'][transformer.p1.i]
                s_grg_ss_id = lookup['substation'][transformer.p1.j]
                t_grg_ss_id = lookup['substation'][transformer.p1.k]
                assert(p_grg_ss_id == s_grg_ss_id) # clustering code failed
                assert(p_grg_ss_id == t_grg_ss_id) # clustering code failed
                transformer_data = transformer.to_grg_three_winding_transformer(lookup, base_mva, omit_subtype)

                assert(False) # add breakers

                grg_transformer_id = lookup['transformer'][transformer.index]
                components[p_grg_ss_id]['substation_components'][grg_transformer_id] = transformer_data

            self._grg_add_owners(lookup, groups, transformer.p1, grg_transformer_id)

        return components, groups, switch_status

        # area_lookup = {}
        # zeros = int(math.ceil(math.log(len(self.areas), 10)))
        # for index, area in enumerate(self.areas):
        #     area_data = area.to_grg_area()
        #     area_id = grg_common.area_name_template % str(index + 1).zfill(zeros)
        #     assert(not area_id in components)
        #     components[area_id] = area_data
        #     area_lookup[area.i] = area_id

        # zone_lookup = {}
        # zeros = int(math.ceil(math.log(len(self.zones), 10)))
        # for index, zone in enumerate(self.zones):
        #     zone_data = zone.to_grg_zone()
        #     zone_id = grg_common.zone_name_template % str(index + 1).zfill(zeros)
        #     assert(not zone_id in components)
        #     components[zone_id] = zone_data
        #     zone_lookup[zone.i] = zone_id

        # bus_lookup = {}
        # load_count = 1
        # shunt_count = 1
        # zeros = int(math.ceil(math.log(len(self.buses), 10)))
        # for index, bus in enumerate(self.buses):
        #     bus_data = bus.to_grg_bus(zone_lookup, area_lookup)
        #     bus_id = grg_common.bus_name_template % str(index + 1).zfill(zeros)
        #     assert(not bus_id in components)
        #     components[bus_id] = bus_data
        #     bus_lookup[bus.i] = bus_id

        #     load_data = bus.to_grg_load(bus_lookup, base_mva, omit_subtype)
        #     if load_data != None:
        #         load_id = grg_common.load_name_template % str(load_count).zfill(zeros)
        #         assert(not load_id in components)
        #         components[load_id] = load_data
        #         load_count += 1

        #     shunt_data = bus.to_grg_shunt(bus_lookup, base_mva, omit_subtype)
        #     if shunt_data != None:
        #         shunt_id = grg_common.shunt_name_template % str(shunt_count).zfill(zeros)
        #         assert(not shunt_id in components)
        #         components[shunt_id] = shunt_data
        #         shunt_count += 1

        # gen_lookup = {}
        # gen_count = 1
        # sync_cond_count = 1
        # zeros = int(math.ceil(math.log(len(self.generators), 10)))
        # for index, generator in enumerate(self.generators):
        #     gen_data = generator.to_grg_generator(bus_lookup, base_mva, omit_subtype)
        #     if gen_data['type'] == 'generator':
        #         gen_id = grg_common.generator_name_template % str(gen_count).zfill(zeros)
        #         gen_count += 1
        #     else:
        #         gen_id = grg_common.sync_cond_name_template % str(sync_cond_count).zfill(zeros)
        #         sync_cond_count += 1
        #     assert(not gen_id in components)
        #     components[gen_id] = gen_data
        #     gen_lookup[generator.index] = gen_id

        # line_lookup = {}
        # line_count = 1
        # transformer_count = 1
        # zeros = int(math.ceil(math.log(len(self.branches), 10)))
        # for branch in self.branches:
        #     branch_data = branch.to_grg_line(bus_lookup, base_mva, omit_subtype)
        #     if branch_data['type'] == 'line':
        #         branch_id = grg_common.line_name_template % str(line_count).zfill(zeros)
        #         line_count += 1
        #     else:
        #         branch_id = grg_common.transformer_name_template % str(transformer_count).zfill(zeros)
        #         transformer_count += 1
        #     # this is check on grg data validation
        #     assert(not branch_id in components)
        #     components[branch_id] = branch_data
        #     line_lookup[branch.index] = branch_id


    def _grg_mappings(self, lookup, switch_status, base_mva):
        mappings = {}

        starting_points = {}
        mappings['starting_points'] = starting_points

        for bus in self.buses:
            key, data = bus.get_grg_bus_setpoint(lookup)
            assert(key not in starting_points)
            starting_points[key] = data

        for load in self.loads:
            key, data = load.get_grg_load_setpoint(lookup, base_mva)
            assert(key not in starting_points)
            starting_points[key] = data

        for switched_shunt in self.switched_shunts:
            key, data = switched_shunt.get_grg_shunt_setpoint(lookup, base_mva)
            assert(key not in starting_points)
            starting_points[key] = data

        for gen in self.generators:
            key, data = gen.get_grg_setpoint(lookup, base_mva)
            assert(key not in starting_points)
            starting_points[key] = data

        for transformer in self.transformers:
            if not transformer.is_three_winding():
                key, data = transformer.get_grg_tap_changer_setpoint(lookup)
                assert(key not in starting_points)
                starting_points[key] = data


        breaker_assignment = {}
        mappings['breakers_assignment'] = breaker_assignment
        for switch_id, status_value in switch_status.items():
            switch_pointer = '{}/status'.format(switch_id)
            breaker_assignment[switch_pointer] = status_value


        return mappings


        # network_assignments = {}
        # data['network_assignments'] = network_assignments 

        # ucts_transform = {}
        # #network_assignments.append(ucts_transform)
        # #ucts_transform['name'] = 'ucts' 
        # network_assignments['ucts'] = ucts_transform
        # ucts_transform['type'] = 'refinement'
        # ucts_transform['problem_class'] = 'ac_uc_ots'
        # ucts_transform['network'] = network_id
        # ucts_transform['assignments'] = {}

        # ots_transform = {}
        # #network_assignments.append(ots_transform)
        # #ots_transform['name'] = 'ots' 
        # network_assignments['ots'] = ots_transform
        # ots_transform['type'] = 'refinement'
        # ots_transform['problem_class'] = 'ac_ots'
        # ots_transform['parent'] = 'ucts'

        # ots_assign = {}
        # ots_transform['assignments'] = ots_assign

        # for gen in self.generators:
        #     gen_id = gen_lookup[gen.index]
        #     assignments = gen.get_grg_status()
        #     for attr_pointer, val in assignments.items():
        #         #pointer = '!/' + gen_id + attr_pointer
        #         pointer = grg_common.component_list_pointer(gen_id, attr_pointer)
        #         # this is check on grg data validation
        #         assert(not pointer in ots_assign)
        #         ots_assign[pointer] = val
        #         #gen_status['name'] = gen_id
        #         #ots_assign.append(gen_status)

        # opf_transform = {}
        # #network_assignments.append(opf_transform)
        # #opf_transform['name'] = 'opf'
        # network_assignments['opf'] = opf_transform
        # opf_transform['type'] = 'refinement'
        # opf_transform['problem_class'] = 'ac_opf'
        # opf_transform['parent'] = 'ots'

        # opf_assign = {}
        # opf_transform['assignments'] = opf_assign

        # for branch in self.branches:
        #     line_id = line_lookup[branch.index]
        #     assignments = branch.get_grg_status()
        #     for attr_pointer, val in assignments.items():
        #         #pointer = '!/' + line_id + attr_pointer
        #         pointer = grg_common.component_list_pointer(line_id, attr_pointer)
        #         # this is check on grg data validation
        #         assert(not pointer in opf_assign)
        #         opf_assign[pointer] = val
        #         #status_data['name'] = line_id
        #         #opf_assign.append(status_data)

        # sol_transform = {}
        # #network_assignments.append(sol_transform)
        # #sol_transform['name'] = 'sol'
        # network_assignments['sol'] = sol_transform
        # sol_transform['type'] = 'refinement'
        # sol_transform['parent'] = 'opf'
        # sol_transform['description'] = 'a specific power flow solution'
        # sol_transform['complete_assignment'] = True
        # sol_assign = {}
        # sol_transform['assignments'] = sol_assign

        # for bus in self.buses:
        #     bus_id = bus_lookup[bus.i]
        #     assignments = bus.get_grg_setpoint()
        #     for attr_pointer, val in assignments.items():
        #         #pointer = '!/' + bus_id + attr_pointer
        #         pointer = grg_common.component_list_pointer(bus_id, attr_pointer)
        #         # this is check on grg data validation
        #         assert(not pointer in sol_assign)
        #         sol_assign[pointer] = val
        #         #setpoint_data['name'] = bus_id
        #         #sol_assign.append(setpoint_data)

        # for gen in self.generators:
        #     gen_id = gen_lookup[gen.index]
        #     assignments = gen.get_grg_setpoint(base_mva)
        #     for attr_pointer, val in assignments.items():
        #         #pointer = '!/' + gen_id + attr_pointer
        #         pointer = grg_common.component_list_pointer(gen_id, attr_pointer)
        #         # this is check on grg data validation
        #         assert(not pointer in sol_assign)
        #         sol_assign[pointer] = val
        #         #setpoint_data['name'] = gen_id
        #         #sol_assign.append(setpoint_data)

        # for branch in self.branches:
        #     line_id = line_lookup[branch.index]
        #     assignments = {}

        #     # TODO only need to do this if the branch had bounds on voltage differences 
        #     from_bus = components[line_id]['from_link']
        #     to_bus = components[line_id]['to_link']
        #     angle_difference = sol_assign[from_bus+'/voltage/angle'] - sol_assign[to_bus+'/voltage/angle']
        #     angle_difference_pointer = '!/'+line_id+'/'+'angle_difference'

        #     # this is check on grg data validation
        #     assert(not angle_difference_pointer in sol_assign)
        #     sol_assign[angle_difference_pointer] = angle_difference
        #     #setpoint_data['name'] = line_id
        #     #sol_assign.append(setpoint_data)


    def _grg_add_owners(self, lookup, groups, comp, grg_id):
        if comp.o1 in lookup['owner'] and comp.f1 != 0.0:
            groups[lookup['owner'][comp.o1]]['component_ids'].append(grg_id)
        else:
            pass # is given by the bus owner

        if comp.o2 in lookup['owner'] and comp.f2 != 0.0:
            groups[lookup['owner'][comp.o2]]['component_ids'].append(grg_id)
        if comp.o3 in lookup['owner'] and comp.f3 != 0.0:
            groups[lookup['owner'][comp.o3]]['component_ids'].append(grg_id)
        if comp.o4 in lookup['owner'] and comp.f4 != 0.0:
            groups[lookup['owner'][comp.o4]]['component_ids'].append(grg_id)


    def _grg_market(self, lookup, base_mva):
        market = {}
        costs = {}
        market['operational_costs'] = costs
        for gen in self.generators:
            if not gen.is_synchronous_condenser():
                key, value = gen.get_grg_cost_model(lookup, base_mva)
                assert(key not in costs)
                costs[key] = value

        return market


    def _grg_operations(self, lookup):
        operations = {}

        for branch in self.branches:
            key, data = branch.get_grg_operations(lookup)
            assert(key not in operations)
            operations[key] = data

        return operations


    def _combine_status(self, *mp_comps):
        for mp_comp in mp_comps:
            grg_status = mp_comp.get_grg_status()
            if grg_status == 'off':
                return 'off'
        return 'on'


    def _insert_switch(self, grg_comp, switch_count, switch_zeros):
        assert('link' in grg_comp)

        grg_switch_id = grg_common.switch_name_template % str(switch_count).zfill(switch_zeros)
        grg_switch_voltage_id = grg_common.switch_voltage_name_template % str(switch_count).zfill(switch_zeros)

        comp_voltage_id = grg_comp['link']
        grg_comp['link'] = grg_switch_voltage_id

        switch = {
            'id': grg_switch_id,
            'type': 'switch',
            'subtype': 'breaker',
            'link_1': comp_voltage_id,
            'link_2': grg_switch_voltage_id,
            'status': {'var': ['off','on']}
        }

        return switch, grg_switch_voltage_id


    def _insert_switches(self, grg_comp, switch_count, switch_zeros):
        assert('link_1' in grg_comp)
        assert('link_2' in grg_comp)

        grg_switch_id_1 = grg_common.switch_name_template % str(switch_count).zfill(switch_zeros)
        grg_switch_voltage_id_1 = grg_common.switch_voltage_name_template % str(switch_count).zfill(switch_zeros)

        grg_switch_id_2 = grg_common.switch_name_template % str(switch_count+1).zfill(switch_zeros)
        grg_switch_voltage_id_2 = grg_common.switch_voltage_name_template % str(switch_count+1).zfill(switch_zeros)

        comp_voltage_id_1 = grg_comp['link_1']
        grg_comp['link_1'] = grg_switch_voltage_id_1

        comp_voltage_id_2 = grg_comp['link_2']
        grg_comp['link_2'] = grg_switch_voltage_id_2

        switch_1 = {
            'id': grg_switch_id_1,
            'type': 'switch',
            'subtype': 'breaker',
            'link_1': comp_voltage_id_1,
            'link_2': grg_switch_voltage_id_1,
            'status': {'var': ['off','on']}
        }

        switch_2 = {
            'id': grg_switch_id_2,
            'type': 'switch',
            'subtype': 'breaker',
            'link_1': comp_voltage_id_2,
            'link_2': grg_switch_voltage_id_2,
            'status': {'var': ['off','on']}
        }

        return switch_1, grg_switch_voltage_id_1, switch_2, grg_switch_voltage_id_2


class Bus(grg_pssedata.struct.Bus):
    def to_grg_bus(self, lookup, omit_subtype=False):
        '''Returns: a grg data bus name and data as a dictionary'''

        if omit_subtype:
            warnings.warn('attempted to omit subtype on bus \'%s\', but this is not allowed.' % str(self.i), PSSE2GRGWarning)

        data = {
            'source_id': str(self.i),
            'id': lookup['bus'][self.i],
            'psse_name': self.name,
            'type':'bus',
            'link': lookup['voltage'][self.i],
            #'subtype':'bus',
            'voltage': {
                'magnitude': grg_common.build_range_variable(self.nvlo, self.nvhi),
                'angle' : grg_common.build_range_variable('-Inf', 'Inf'),
            },
        }

        if self.ide == 3:
           data['reference'] = True

        return data

    # def get_grg_setpoint(self):
    #     '''Returns: a grg data voltage set point as a dictionary'''
    #     assignments = {
    #         '@/voltage/magnitude':self.vm,
    #         '@/voltage/angle':math.radians(self.va),
    #         '@/psse_bus_type': self.ide
    #     }

    #     return assignments

    def get_grg_bus_setpoint(self, lookup):
        '''Returns: a grg data voltage set point as a dictionary'''
        key = lookup['bus'][self.i]+'/voltage'
        value = {
            'magnitude': self.vm,
            'angle': math.radians(self.va)
        }

        return key, value

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.ide != 4:
            return 'on'
        else:
            return 'off'


class Load(grg_pssedata.struct.Load):
    def to_grg_load(self, lookup, base_mva, omit_subtype=False):
        '''Returns: a grg data load name and data as a dictionary'''
        data = {
            'source_id': str(self.index),
            'id':lookup['load'][self.index],
            'psse_id': self.id,
            'type':'load',
            'link':lookup['voltage'][self.i],
            'demand':{
                'active': self.pl/base_mva,
                'reactive': self.ql/base_mva
            }
        }

        if not omit_subtype:
            data['subtype'] = 'withdrawal'

        return data

    def get_grg_load_setpoint(self, lookup, base_mva):
        key = lookup['load'][self.index]+'/demand'
        value = {
            'active': self.pl/base_mva,
            'reactive': self.ql/base_mva
        }
        return key, value

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.status == 1:
            return 'on'
        else:
            return 'off'


class FixedShunt(grg_pssedata.struct.FixedShunt):
    def to_grg_shunt(self, lookup, base_mva, omit_subtype=False):
        '''Returns: a grg data shunt name and data as a dictionary'''

        #TODO confirm scaling is correct on gl bl values, or not
        data = {
            'id':lookup['fixed_shunt'][self.index],
            'type':'shunt',
            'psse_id': self.id,
            'link':lookup['voltage'][self.i],
            #'status': 'on',
            'shunt':{
                'conductance': self.gl/base_mva,
                'susceptance': self.bl/base_mva
            }
        }

        if not omit_subtype:
            if self.bl >= 0:
                data['subtype'] = 'inductor'
            else:
                data['subtype'] = 'capacitor'

        return data

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.status == 1:
            return 'on'
        else:
            return 'off'


class SwitchedShunt(grg_pssedata.struct.SwitchedShunt):
    def to_grg_shunt(self, lookup, base_mva, omit_subtype=False):
        '''Returns: a grg data shunt name and data as a dictionary'''

        #TODO correctly implement general form of this
        assert(self.n1 == 1)
        if self.b1 <= 0:
            susceptance = grg_common.build_set_variable([self.b1/base_mva, 0.0])
        else:
            susceptance = grg_common.build_set_variable([0.0, self.b1/base_mva])

        data = {
            'id':lookup['switched_shunt'][self.index],
            'type':'shunt',
            'link':lookup['voltage'][self.i],
            #'status': 'on',
            'shunt':{
                'conductance': 0.0,
                'susceptance': susceptance
            }
        }

        # if not omit_subtype:
        #     if self.bs >= 0:
        #         data['subtype'] = 'inductor'
        #     else:
        #         data['subtype'] = 'capacitor'

        return data

    def get_grg_shunt_setpoint(self, lookup, base_mva):
        key = lookup['switched_shunt'][self.index]+'/shunt/susceptance'
        value = self.b1/base_mva
        return key, value

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.stat == 1:
            return 'on'
        else:
            return 'off'


class Generator(grg_pssedata.struct.Generator):
    def is_synchronous_condenser(self):
        # NOTE self.pg == 0 is needed for bad data cases, where pg is out of bounds. in time, may be able to remove this.
        return self.pb == 0 and self.pt == 0 and self.pg == 0

    def to_grg_generator(self, lookup, base_mva, omit_subtype=False):
        '''Returns: a grg data gen name and data as a dictionary'''

        data = {
            'source_id': str(self.index),
            'id': lookup['gen'][self.index],
            'link': lookup['voltage'][self.i],
            'psse_id': self.id,
            #'status': grg_common.build_status_variable(),
            # not part of the offical spec, but left in for idempotentce
            'mbase':self.mbase,
        }

        if self.is_synchronous_condenser():
            # TODO throw warning that this gen is becoming a synchronous_condenser
            data.update({
                'type': 'synchronous_condenser',
                'output': {
                    'reactive': grg_common.build_range_variable(self.qb/base_mva, self.qt/base_mva),
                }
            })
        else:
            data.update({
                'type': 'generator',
                'output': {
                    'active': grg_common.build_range_variable(self.pb/base_mva, self.pt/base_mva),
                    'reactive': grg_common.build_range_variable(self.qb/base_mva, self.qt/base_mva),
                }
            })
            #if not omit_subtype:
            #    data['subtype'] = 'injection'

        #extra_data_names = ['ireg', 'zr','zx', 'rt', 'xt', 'gtap', 'rmpct'] 
        #grg_common.add_extra_data(self, extra_data_names, data)

        return data

    # def get_grg_setpoint(self, base_mva):
    #     '''Returns: a grg data power output set point as a dictionary'''
    #     assignments = {
    #         '@/output/reactive':self.qg/base_mva, 
    #         # not part of the offical spec, but left in for idempotentce
    #         '@/vs':self.vs, 
    #     }

    #     if not self.is_synchronous_condenser():
    #         assignments.update({'@/output/active':self.pg/base_mva}) 

    #     return assignments

    def get_grg_setpoint(self, lookup, base_mva):
        '''Returns: a grg data power output set point as a dictionary'''

        key = lookup['gen'][self.index]+'/output'
        if self.is_synchronous_condenser():
            value = {
                'reactive': self.qg/base_mva
            }
        else:
            value = {
                'active': self.pg/base_mva,
                'reactive': self.qg/base_mva
            }
        return key, value

    def get_grg_cost_model(self, lookup, base_mva):
        '''Returns: a grg data encoding of this data structure as a dictionary'''

        if self.is_synchronous_condenser():
            assert(False) #unable to generate for sync cond
            return None, None

        grg_id = lookup['gen'][self.index]
        #key = grg_id+'_active_cost'
        key = grg_id
        argument = grg_id+'/output/active'

        data = {
            'type':'polynomial', 
            'input':argument, 
            'coefficients': [0, base_mva*1, 0]
        }

        return key, data


    # def get_grg_status(self):
    #     '''Returns: a grg data status assignment as a dictionary'''
    #     return {'@/status': 'on' if self.stat == 1 else 'off'}

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.stat == 1:
            return 'on'
        else:
            return 'off'



class Branch(grg_pssedata.struct.Branch):
    def to_grg_line(self, lookup, base_mva, omit_subtype=False):
        '''Returns: a grg data line name and data as a dictionary'''

        data = {
            'id': lookup['branch'][self.index],
            'source_id': str(self.index),
            'link_1': lookup['voltage'][self.i],
            'link_2': lookup['voltage'][self.j],
            'type': 'ac_line',

            #'current_limits_1': self._grg_current_limit(self.ratea/base_mva),
            #'current_limits_2': self._grg_current_limit(self.ratea/base_mva),
            'thermal_limits_1': self._grg_thermal_limit(self.ratea/base_mva, self.rateb/base_mva, self.ratec/base_mva),
            'thermal_limits_2': self._grg_thermal_limit(self.ratea/base_mva, self.rateb/base_mva, self.ratec/base_mva),

            'impedance':{
                'resistance':self.r,
                'reactance':self.x,
            },
            #'status': grg_common.build_status_variable(),
            #'angle_difference': grg_common.build_range_variable('-Inf', 'Inf'),
            #'meter_side': 'from' if self.from_meter else 'to',
            'circuit_id': self.ckt
        }

        #if any([not grg_common.is_default_value(self, x) for x in ['b', 'gi', 'bi', 'gj', 'bj']]):
        data.update({
            'psse_line_charge': self.b,
            'shunt_1':{
                'conductance': self.gi,
                'susceptance': self.bi + self.b/2.0
            },
            'shunt_2':{
                'conductance': self.gj,
                'susceptance': self.bj + self.b/2.0
            }
        })

        if not omit_subtype:
            data['subtype'] = 'overhead'

        #extra_data_names = ['ratea', 'rateb', 'ratec']
        #grg_extra_data_names = ['rate_a', 'rate_b', 'rate_c']
        #grg_common.add_extra_data_remap(self, extra_data_names, data, grg_extra_data_names, 1/base_mva)

        return data

    def _grg_thermal_limit(self, rate_a, rate_b, rate_c):
        limits = [
            {'duration': 'Inf', 'min': 0.0, 'max':rate_a, 'report':'off'}
        ]

        if rate_b != 0.0 and rate_b > rate_a:
            limits.append({'duration': 14400, 'min': 0.0, 'max':rate_b, 'report':'off'})
        if rate_c != 0.0 and rate_c > rate_a:
            if len(limits) == 1 or rate_c > rate_b:
                limits.append({'duration': 900, 'min': 0.0, 'max':rate_c, 'report':'off'})

        return limits

    # def _grg_current_limit(self, rate):
    #     return {
    #         'arguments': ['duration', 'min', 'max', 'report'],
    #         'values': [
    #             ['Inf', 0.0, rate, 'off']
    #         ]
    #     }

    # def get_grg_status(self):
    #     '''Returns: a grg data status assignment as a dictionary'''
    #     return {'@/status': 'on' if self.st == 1 else 'off'}

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.st == 1:
            return 'on'
        else:
            return 'off'

    # def get_grg_setpoint(self, base_mva):
    #     '''Returns: a grg data power flow set point as a dictionary'''
    #     assignments = {}
    #     return assignments


    def get_grg_operations(self, lookup):
        key = lookup['branch'][self.index]+'/angle_difference'
        value = grg_common.build_range_variable(-default_voltage_angle_difference, default_voltage_angle_difference)
        return key, value


class TwoWindingTransformer(grg_pssedata.struct.TwoWindingTransformer):
    def to_grg_two_winding_transformer(self, lookup, base_mva, omit_subtype=False):
        '''Returns: grg transformer data as a dictionary'''
        data = {
            'id': lookup['transformer'][self.index],
            'source_id': str(self.index),
            'link_1': lookup['voltage'][self.p1.i],
            'link_2': lookup['voltage'][self.p1.j],
            'type': 'two_winding_transformer',
            'subtype': 'PI_model',

            #'current_limits_1': self._grg_current_limit(self.w1.rata/base_mva),
            #'current_limits_2': self._grg_current_limit(self.w1.rata/base_mva),
            'thermal_limits_1': self._grg_thermal_limit(self.w1.rata/base_mva, self.w1.ratb/base_mva, self.w1.ratc/base_mva),
            'thermal_limits_2': self._grg_thermal_limit(self.w1.rata/base_mva, self.w1.ratb/base_mva, self.w1.ratc/base_mva),

            #'status': grg_common.build_status_variable(),
            #'angle_difference': grg_common.build_range_variable('-Inf', 'Inf'),
            #'meter_side': 'from' if self.from_meter else 'to',
            'circuit_id': self.p1.ckt,
            'psse_name': self.p1.name,

            'tap_changer': self._grg_tap_changer(base_mva)
        }

        return data

    def _grg_thermal_limit(self, rate_a, rate_b, rate_c):
        limits = [
            {'duration': 'Inf', 'min': 0.0, 'max':rate_a, 'report':'off'}
        ]

        if rate_b != 0.0 and rate_b > rate_a:
            limits.append({'duration': 14400, 'min': 0.0, 'max':rate_b, 'report':'off'})
        if rate_c != 0.0 and rate_c > rate_a:
            if len(limits) == 1 or rate_c > rate_b:
                limits.append({'duration': 900, 'min': 0.0, 'max':rate_c, 'report':'off'})

        return limits

    # def _grg_current_limit(self, rate):
    #     return {
    #         'arguments': ['duration', 'min', 'max', 'report'],
    #         'values': [
    #             ['Inf', 0.0, rate, 'off']
    #         ]
    #     }

    def _grg_tap_changer(self, base_mva):
        assert(grg_common.isclose(base_mva, self.p2.sbase12)) # otherwise unit conversion needed
        assert(grg_common.isclose(1.000000, self.w2.windv)) # otherwise unit conversion needed

        return {
            'position': grg_common.build_range_variable(0, 0),
            'impedance': {
                'resistance': grg_common.build_range_variable(self.p2.r12, self.p2.r12),
                'reactance': grg_common.build_range_variable(self.p2.x12, self.p2.x12)
            },
            'shunt': {
                'conductance': grg_common.build_range_variable(0, 0),
                'susceptance': grg_common.build_range_variable(0, 0),
            },
            'transform': {
                'tap_ratio': grg_common.build_range_variable(self.w1.rmi, self.w1.rma),
                'angle_shift': grg_common.build_range_variable(math.radians(self.w1.ang), math.radians(self.w1.ang)),
            },
            'steps': [
                {
                    'position':0 ,
                    'impedance': {'resistance': self.p2.r12, 'reactance': self.p2.x12},
                    'shunt': {'conductance': 0.0, 'susceptance': 0.0},
                    'transform': {'tap_ratio': self.w1.windv, 'angle_shift':math.radians(self.w1.ang)}
                }
            ],
            'ntp': self.w1.ntp # psse paramter
        }


    def get_grg_tap_changer_setpoint(self, lookup):
        key = lookup['transformer'][self.index]+'/tap_changer/position'
        value = 0
        return key, value

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.p1.stat == 1:
            return 'on'
        else:
            return 'off'


class ThreeWindingTransformer(grg_pssedata.struct.ThreeWindingTransformer):
    def to_grg_three_winding_transformer(self, bus_lookup, base_mva, omit_subtype=False):
        assert(False)

    def get_grg_status(self):
        '''Returns: a grg data status assignment as a dictionary'''
        if self.p1.stat == 1:
            return 'on'
        else:
            return 'off'


class Zone(grg_pssedata.struct.Zone):
    def to_grg_zone(self):
        '''Returns: a grg zone data dictionary'''
        data = {
            'status':'on',
            'type': 'zone',
            'source_id': str(self.i),
            'name': self.zoname
        }

        return data


class Area(grg_pssedata.struct.Area):
    def to_grg_area(self):
        '''Returns: a grg area data dictionary'''
        data = {
            'status':'on',
            'type': 'area',
            'source_id': str(self.i),
            'name': self.arnam
        }

        extra_data_names = ['isw', 'pdes', 'ptol'] 
        grg_common.add_extra_data(self, extra_data_names, data)

        return data


class Owner(grg_pssedata.struct.Owner):
    def to_grg_owner(self):
        assert(False)

