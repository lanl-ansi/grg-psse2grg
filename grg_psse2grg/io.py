from __future__ import print_function

import argparse
import shlex
import math
import json
import functools
import sys

import warnings

from grg_psse2grg.exception import PSSE2GRGWarning

from grg_pssedata.struct import quote_string

from grg_pssedata.io import psse_table_terminus
from grg_pssedata.io import psse_record_terminus
from grg_pssedata.io import psse_terminuses
from grg_pssedata.io import expand_commas
from grg_pssedata.io import parse_line

from grg_pssedata.cmd import diff

from grg_grgdata.cmd import flatten_network
from grg_grgdata.cmd import components_by_type
from grg_grgdata.cmd import collapse_voltage_points
from grg_grgdata.cmd import active_voltage_points
from grg_grgdata.cmd import isolated_voltage_points
from grg_grgdata.cmd import voltage_level_by_voltage_point

from grg_pssedata.struct import TransformerParametersFirstLine
from grg_pssedata.struct import TransformerParametersSecondLine
from grg_pssedata.struct import TransformerParametersSecondLineShort
from grg_pssedata.struct import TransformerWinding
from grg_pssedata.struct import TransformerWindingShort

from grg_psse2grg.struct import Bus
from grg_psse2grg.struct import Load
from grg_psse2grg.struct import FixedShunt
from grg_psse2grg.struct import Generator
from grg_psse2grg.struct import Branch
from grg_psse2grg.struct import TwoWindingTransformer
from grg_psse2grg.struct import ThreeWindingTransformer

from grg_psse2grg.struct import Area
from grg_psse2grg.struct import Zone
from grg_psse2grg.struct import Owner
from grg_psse2grg.struct import SwitchedShunt
from grg_psse2grg.struct import Case

from grg_psse2grg.struct import grg_description_preamble

from grg_grgdata.cmd import flatten_network
import grg_grgdata.common as grg_common

print_err = functools.partial(print, file=sys.stderr)

def parse_psse_case_file(psse_file_name):
    '''opens the given path and parses it as pss/e data

    Args:
        psse_file_name(str): path to the a psse data file
    Returns:
        Case: a grg_pssedata case
    '''

    with open(psse_file_name, 'r') as psse_file:
        lines = psse_file.readlines()
    return parse_psse_case_lines(lines)


def parse_psse_case_lines(lines):
    assert(len(lines) > 3) # need at base values and record

    (ic, sbase, rev, xfrrat, nxfrat, basefrq), comment = parse_line(lines[0])
    assert(int(ic) == 0) # validity checks may fail on "change data"
    print_err('case data: {} {} {} {} {} {}'.format(ic, sbase, rev, xfrrat, nxfrat, basefrq))

    record1 = lines[1].strip('\n')
    record2 = lines[2].strip('\n')
    print_err('record 1: {}'.format(record1))
    print_err('record 2: {}'.format(record2))

    buses = []
    loads = []
    fixed_shunts = []
    generators = []
    branches = []
    transformers = []
    areas = []
    tt_dc_lines = []
    vsc_dc_lines = []
    transformer_corrections = []
    mt_dc_lines = []
    line_groupings = []
    zones = []
    transfers = []
    owners = []
    facts = []
    switched_shunts = []
    gnes = []
    induction_machines = []


    line_index = 3
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        buses.append(Bus(*line_parts))
        line_index += 1
    print_err('parsed {} buses'.format(len(buses)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    load_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        loads.append(Load(line_index - load_index_offset, *line_parts))
        line_index += 1
    print_err('parsed {} loads'.format(len(loads)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    fixed_shunt_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        fixed_shunts.append(FixedShunt(line_index - fixed_shunt_index_offset, *line_parts))
        line_index += 1
    print_err('parsed {} fixed shunts'.format(len(fixed_shunts)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    gen_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        generators.append(Generator(line_index - gen_index_offset, *line_parts))
        line_index += 1
    print_err('parsed {} generators'.format(len(generators)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    branch_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        #line = shlex.split(lines[line_index].strip())
        #line = expand_commas(line)
        line_parts, comment = parse_line(lines[line_index])
        #print(line_parts)
        branches.append(Branch(line_index - branch_index_offset, *line_parts))
        line_index += 1
    print_err('parsed {} branches'.format(len(branches)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    transformer_index = 0
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts_1, comment_1 = parse_line(lines[line_index])
        parameters_1 = TransformerParametersFirstLine(*line_parts_1)
        #print(parameters_1)

        if parameters_1.k == 0: # two winding case
            line_parts_2, comment_2 = parse_line(lines[line_index+1])
            line_parts_3, comment_3 = parse_line(lines[line_index+2])
            line_parts_4, comment_4 = parse_line(lines[line_index+3])

            parameters_2 = TransformerParametersSecondLineShort(*line_parts_2)
            winding_1 = TransformerWinding(1, *line_parts_3)
            winding_2 = TransformerWindingShort(2, *line_parts_4)

            t = TwoWindingTransformer(transformer_index, parameters_1, parameters_2, winding_1, winding_2)

            line_index += 4
        else: # three winding case
            line_parts_2, comment_2 = parse_line(lines[line_index+1])
            line_parts_3, comment_3 = parse_line(lines[line_index+2])
            line_parts_4, comment_4 = parse_line(lines[line_index+3])
            line_parts_5, comment_5 = parse_line(lines[line_index+4])

            parameters_2 = TransformerParametersSecondLine(*line_parts_2)
            winding_1 = TransformerWinding(1, *line_parts_3)
            winding_2 = TransformerWinding(2, *line_parts_4)
            winding_3 = TransformerWinding(3, *line_parts_5)

            t = ThreeWindingTransformer(transformer_index, parameters_1, parameters_2, winding_1, winding_2, winding_3)

            line_index += 5

        #print(t)
        transformers.append(t)
        transformer_index += 1
    print_err('parsed {} transformers'.format(len(transformers)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        areas.append(Area(*line_parts))
        line_index += 1
    print_err('parsed {} areas'.format(len(areas)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    #two terminal dc line data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} two terminal dc lines'.format(len(tt_dc_lines)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    #vsc dc line data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} two terminal dc lines'.format(len(vsc_dc_lines)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    trans_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} transformer corrections'.format(len(transformer_corrections)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    #multi-terminal dc line data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} multi-terminal dc lines'.format(len(mt_dc_lines)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    #multi-section line grouping data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} multi-section lines'.format(len(line_groupings)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        zones.append(Zone(*line_parts))
        line_index += 1
    print_err('parsed {} zones'.format(len(zones)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    # inter area transfer data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} inter area transfers'.format(len(transfers)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        owners.append(Owner(*line_parts))
        line_index += 1
    print_err('parsed {} owners'.format(len(owners)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    # facts device data block 
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} facts devices'.format(len(facts)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    # switched shunt data block 
    swithced_shunt_index_offset = line_index
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        line_parts, comment = parse_line(lines[line_index])
        switched_shunts.append(SwitchedShunt(line_index - swithced_shunt_index_offset, *line_parts))
        line_index += 1
    print_err('parsed {} switched shunts'.format(len(switched_shunts)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    # GNE device data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} generic network elements'.format(len(gnes)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    # induction machine data
    while parse_line(lines[line_index])[0][0].strip() not in psse_terminuses:
        assert(False) # implement me!
    print_err('parsed {} induction machines'.format(len(induction_machines)))

    if parse_line(lines[line_index])[0][0].strip() != psse_record_terminus:
        line_index += 1

    print_err('un-parsed lines:')
    while line_index < len(lines):
        #print(parse_line(lines[line_index]))
        print_err('  '+lines[line_index])
        line_index += 1

    case = Case(ic, sbase, rev, xfrrat, nxfrat, basefrq, record1, record2,
        buses, loads, fixed_shunts, generators, branches, transformers, areas, 
        tt_dc_lines, vsc_dc_lines, transformer_corrections, mt_dc_lines, 
        line_groupings, zones, transfers, owners, facts, switched_shunts, 
        gnes, induction_machines)

    #print(case)
    #print(case.to_psse())
    return case



# def build_psse_case_network(grg_data):
#     network = grg_data['network']
#     network_id = network['id']
#     base_mva = network['base_mva']
#     root_components = network['components']

#     return build_psse_case(network_id, base_mva, root_components, root_components)


# def build_psse_case_transform(grg_data, transformation_id):
#     network_id, network, flat_network_id, flat_network = flatten_network(grg_data, transformation_id)

#     root_components = network['components']
#     flat_components = flat_network['components']

#     return build_psse_case(flat_network_id, network, root_components, flat_components)


def build_psse_case(grg_data, starting_point_map_id, switch_assignment_map_id):
    # TODO see if this grg_mp2grg case is ok, and should not be grg_mpdata

    #print(json.dumps(flat_components, sort_keys=True, indent=2, separators=(',', ': ')))

    # TODO this functionality should be in grg data structure (components-by-type)
    float_precision = grg_common.default_float_precision

    network = grg_data['network']
    starting_point_map = grg_data['mappings'][starting_point_map_id]
    operations = grg_data['operation_constraints']
    market = grg_data['market']

    if not network['per_unit']:
        print_err('network data not given in per unit')
        return

    base_mva = 100.0
    if 'sbase' in network:
        base_mva = network['sbase']

    cbt = components_by_type(grg_data)
    #print_err('comps: {}'.format(cbt.keys()))

    switch_assignment = {}
    if switch_assignment_map_id in grg_data['mappings']:
        switch_assignment_map = grg_data['mappings'][switch_assignment_map_id]
        
        for key, value in switch_assignment_map.items():
            if key.count('/') == 1 and key.endswith('/status'):
                switch_assignment[key.split('/')[0]] = value

    vp2int = collapse_voltage_points(grg_data, switch_assignment)
    # print_err('voltage points to int:')
    # print_err(vp2int)

    avps = active_voltage_points(grg_data, switch_assignment)
    # print_err('active voltage points:')
    # print_err(avps)

    ivps = isolated_voltage_points(grg_data, switch_assignment)
    # print_err('isolated voltage points:')
    # print_err(ivps)

    vlbvp = voltage_level_by_voltage_point(grg_data)
    #print_err(vlbvp)


    if all('source_id' in bus for bus in cbt['bus']):
        # TODO check for clashes with other voltage point ints
        number_update = {}
        for bus in cbt['bus']:
            number_update[vp2int[bus['link']]] = int(bus['source_id'])
            #vp2int[bus['link']] = int(bus['source_id'])

        for k,v in vp2int.items():
            if v in number_update:
                vp2int[k] = number_update[v]


    buses_by_bid = {}
    for bus in cbt['bus']:
        bid = vp2int[bus['link']]
        if not bid in buses_by_bid:
            buses_by_bid[bid] = []
        buses_by_bid[bid].append(bus)

    bid_with_active_gen = set()
    for gen in cbt['generator']:
        if gen['link'] in avps:
            bid_with_active_gen.add(vp2int[gen['link']])

    for sc in cbt['synchronous_condenser']:
        if sc['link'] in avps:
            bid_with_active_gen.add(vp2int[sc['link']])


    psse_buses = []
    psse_loads = []
    psse_fixed_shunts = []
    psse_switched_shunts = []
    psse_gens = []
    psse_branches = []
    psse_transformers = []
    psse_areas = []
    psse_zones = []
    psse_owners = []


    areas = {k:grp for k,grp in grg_data['groups'].items() if grp['type'] == 'area'}
    zones = {k:grp for k,grp in grg_data['groups'].items() if grp['type'] == 'zone'}
    owners = {k:grp for k,grp in grg_data['groups'].items() if grp['type'] == 'owner'}

    area_index_lookup = {}
    area_id_lookup = {}
    if all('source_id' in area for k,area in areas.items()):
        for k,area in areas.items():
            area_id_lookup[k] = int(area['source_id'])
            for comp_id in area['component_ids']:
                if not comp_id in area_index_lookup:
                    area_index_lookup[comp_id] = int(area['source_id'])
                else:
                    warnings.warn('component %s is in multiple areas only %s will be used.' % (comp_id, area_index_lookup[comp_id]), PSSE2GRGWarning)
    else:
        idx = 1
        for k,area in areas.items():
            area_id_lookup[k] = idx
            for comp_id in area['component_ids']:
                if not comp_id in area_index_lookup:
                    area_index_lookup[comp_id] = idx
                else:
                    warnings.warn('component %s is in multiple areas only %s will be used.' % (comp_id, area_index_lookup[comp_id]), PSSE2GRGWarning)
            idx += 1

    for name, area in areas.items():
        area_id = area_id_lookup[name]

        area_args = {
            'i': area_id,
            'arnam': quote_string(psse_name(area, '', length=12))
        }
        grg_common.map_to_dict(area_args, area, 'isw')
        grg_common.map_to_dict(area_args, area, 'pdes')
        grg_common.map_to_dict(area_args, area, 'ptol')

        psse_area = Area(**area_args)

        psse_areas.append(psse_area)

        #print(psse_area)
        del area
    psse_areas.sort(key=lambda x: x.i)


    zone_index_lookup = {}
    zone_id_lookup = {}
    if all('source_id' in zone for k,zone in zones.items()):
        for k,zone in zones.items():
            zone_id_lookup[k] = int(zone['source_id'])
            for comp_id in zone['component_ids']:
                if not comp_id in zone_index_lookup:
                    zone_index_lookup[comp_id] = int(zone['source_id'])
                else:
                    warnings.warn('component %s is in multiple zones only %s will be used.' % (comp_id, zone_index_lookup[comp_id]), PSSE2GRGWarning)
    else:
        idx = 1
        for k,zone in zones.items():
            zone_id_lookup[k] = idx
            for comp_id in zone['component_ids']:
                if not comp_id in zone_index_lookup:
                    zone_index_lookup[comp_id] = idx
                else:
                    warnings.warn('component %s is in multiple zones only %s will be used.' % (comp_id, zone_index_lookup[comp_id]), PSSE2GRGWarning)
            idx += 1

    for name, zone in zones.items():
        zone_id = zone_id_lookup[name]

        zone_args = {
            'i': zone_id, 
            'zoname': quote_string(psse_name(zone, '', length=12))
        }

        psse_zone = Zone(**zone_args)

        psse_zones.append(psse_zone)

        #print(psse_zone)
        del zone
    psse_zones.sort(key=lambda x: x.i)



    owner_index_lookup = {}
    owner_id_lookup = {}
    if all('source_id' in owner for k,owner in owners.items()):
        for k,owner in owners.items():
            owner_id_lookup[k] = int(owner['source_id'])
            for comp_id in owner['component_ids']:
                if not comp_id in owner_index_lookup:
                    owner_index_lookup[comp_id] = []
                if len(owner_index_lookup[comp_id]) < 4:
                    owner_index_lookup[comp_id].append(int(owner['source_id']))
                else:
                    warnings.warn('component %s has multiple owners only %s will be used.' % (comp_id, owner_index_lookup[comp_id]), PSSE2GRGWarning)
    else:
        idx = 1
        for k,owner in owners.items():
            owner_id_lookup[k] = idx
            for comp_id in zone['component_ids']:
                if not comp_id in owner_index_lookup:
                    owner_index_lookup[comp_id] = []
                if len(owner_index_lookup[comp_id]) < 4:
                    owner_index_lookup[comp_id].append(idx)
                else:
                    warnings.warn('component %s has multiple owners only %s will be used.' % (comp_id, owner_index_lookup[comp_id]), PSSE2GRGWarning)
            idx += 1

    for name, owner in owners.items():
        owner_id = owner_id_lookup[name]

        owner_args = {
            'i': owner_id, 
            'owname': quote_string(psse_name(owner, '', length=12))
        }

        psse_owner = Owner(**owner_args)

        psse_owners.append(psse_owner)

        #print(psse_zone)
        del owner
    psse_owners.sort(key=lambda x: x.i)



    psse_bus_lookup = {}
    for bid, buses in buses_by_bid.items():
        if len(buses) > 1:
            print_err('warning: merging buses {} into 1'.format(len(buses)))

        bus_names = [bus['psse_name'] if 'psse_name' in bus else bus['id'] for bus in buses]
        bus_name = ' & '.join(bus_names)
        bus_name = '\'{}\''.format(bus_name)

        bus_type = None

        if bid in bid_with_active_gen:
            bus_type = 2

        if any(bus['link'] in ivps for bus in buses):
            bus_type = 4

        if any('reference' in bus for bus in buses):
            bus_type = 3

        if bus_type == None:
            bus_type = 1

        for bus in buses:
            if 'psse_bus_type' in bus:
                if bus['psse_bus_type'] != bus_type:
                    # TODO print warning about inconsistent mp data!
                    bus_type = bus['psse_bus_type']

        area = 1
        for bus in buses:
            if bus['id'] in area_index_lookup:
                bus_area = area_index_lookup[bus['id']]
                if area != 1 and bus_area != area:
                    print_err('warning: inconsistent bus areas found')
                else:
                    area = bus_area

        zone = 1
        for bus in buses:
            if bus['id'] in zone_index_lookup:
                bus_zone = zone_index_lookup[bus['id']]
                if zone != 1 and bus_zone != zone:
                    print_err('warning: inconsistent bus zones found')
                else:
                    zone = bus_zone

        owner = 1
        for bus in buses:
            if bus['id'] in owner_index_lookup:
                bus_owners = owner_index_lookup[bus['id']]
                if len(bus_owners) > 1:
                    print_err('warning: multiple bus owners found, using the first one')
                bus_owner = bus_owners[0]
                if owner != 1 and bus_owner != owner:
                    print_err('warning: inconsistent bus owners found')
                else:
                    owner = bus_owner

        base_kv = 1.0
        for bus in buses:
            vl = vlbvp[bus['link']]
            nv = vl['voltage']['nominal_value']
            if 'mp_base_kv' in vl['voltage']:
                nv = vl['voltage']['mp_base_kv']
            if base_kv != 1.0 and nv != base_kv:
                print_err('warning: inconsistent bus base_kv values found')
            else:
                base_kv = nv

        vmax = float('inf')
        vmin = float('-inf')
        for bus in buses:
            vmin = max(vmin, grg_common.min_value(bus['voltage']['magnitude']))
            vmax = min(vmax, grg_common.max_value(bus['voltage']['magnitude']))

        vm_values = []
        va_values = []
        for bus in buses:
            key = '{}/voltage'.format(bus['id'])
            if key in starting_point_map:
                voltage = starting_point_map[key]
                if 'magnitude' in voltage:
                    vm_values.append(voltage['magnitude'])
                if 'angle' in voltage:
                    va_values.append(voltage['angle'])

        va = 0.0
        vm = 1.0
        if len(vm_values) > 0:
            vm = sum(vm_values, 0.0) / len(vm_values)
        if len(va_values) > 0:
            va = sum(va_values, 0.0) / len(va_values)

        bus_args = {
            'i': bid, 
            'ide': bus_type, 
            'area': area, 
            'zone': zone,
            'owner': owner,
            'vm': vm, 
            'va': round(math.degrees(va), float_precision), 
            'name': bus_name,
            'basekv': base_kv,
            'zone': zone,
            'nvhi': vmax,
            'nvlo': vmin,
            'evhi': vmax,
            'evlo': vmin,
        }

        psse_bus = Bus(**bus_args)

        psse_buses.append(psse_bus)
        psse_bus_lookup[bid] = psse_bus

        #print(psse_bus)
        del bus
    psse_buses.sort(key=lambda x: x.i)



    load_index_lookup = {}
    if all('source_id' in load for load in cbt['load']):
        for load in cbt['load']:
            load_index_lookup[load['id']] = int(load['source_id'])
    else:
        for i,k in enumerate(sorted(cbt['load'], key=lambda x: x['id'])):
            load_index_lookup[k['id']] = i

    for load in cbt['load']:
        bus_id = vp2int[load['link']]

        load_status = 1
        if load['link'] not in avps:
            load_status = 0

        area = 1
        if load['id'] in area_index_lookup:
            area = area_index_lookup[load['id']]

        zone = 1
        if load['id'] in zone_index_lookup:
            zone = zone_index_lookup[load['id']]

        owner = 1
        if load['id'] in owner_index_lookup:
            load_owners = owner_index_lookup[load['id']]
            if len(bus_owners) > 1:
                print_err('warning: multiple load owners found, using the first one')
            owner = load_owners[0]

        load_args = {
            'index': load_index_lookup[load['id']],
            'i': bus_id,
            'id': '\'{}\''.format(load.get('psse_id', '')),
            'status': load_status,
            'area': area, 
            'zone': zone,
            'pl': round(base_mva*load['demand']['active'], float_precision),
            'ql': round(base_mva*load['demand']['reactive'], float_precision),
            'ip': round(base_mva*load.get('ip', 0.0), float_precision),
            'iq': round(base_mva*load.get('iq', 0.0), float_precision),
            'yp': round(base_mva*load.get('yp', 0.0), float_precision),
            'yq': round(base_mva*load.get('yq', 0.0), float_precision),
            'owner': owner,
            'scale': load.get('scale', 1),
        }

        psse_load = Load(**load_args)

        psse_loads.append(psse_load)

        #print(psse_load)
        del load
    psse_loads.sort(key=lambda x: x.index)


    shunt_index_lookup = {}
    if all('source_id' in shunt for shunt in cbt['shunt']):
        for shunt in cbt['shunt']:
            shunt_index_lookup[shunt['id']] = int(shunt['source_id'])
    else:
        for i,k in enumerate(sorted(cbt['shunt'], key=lambda x: x['id'])):
            shunt_index_lookup[k['id']] = i

    for shunt in cbt['shunt']:
        bus_id = vp2int[shunt['link']]

        shunt_status = 1
        if shunt['link'] not in avps:
            shunt_status = 0

        if isinstance(shunt['shunt']['conductance'], dict) or \
            isinstance(shunt['shunt']['susceptance'], dict):
            print_err('warning: skipping shunt with variable admittance values')
            continue

        shunt_args = {
            'index': shunt_index_lookup[shunt['id']],
            'i': bus_id,
            'id': '\'{}\''.format(shunt.get('psse_id', '')),
            'status': shunt_status,
            'gl': round(base_mva*shunt['shunt']['conductance'], float_precision),
            'bl': round(base_mva*shunt['shunt']['susceptance'], float_precision),
        }

        psse_shunt = FixedShunt(**shunt_args)

        psse_fixed_shunts.append(psse_shunt)

        #print(psse_shunt)
        del shunt
    psse_fixed_shunts.sort(key=lambda x: x.index)



    branch_index_lookup = {}
    if all('source_id' in line for line in cbt['ac_line']):
        for line in cbt['ac_line']:
            branch_index_lookup[line['id']] = int(line['source_id'])
    else:
        for i,k in enumerate(sorted(cbt['ac_line'], key=lambda x: x['id'])):
            branch_index_lookup[k['id']] = i

    for line in cbt['ac_line']:
        from_bus_id = vp2int[line['link_1']]
        to_bus_id = vp2int[line['link_2']]

        br_status = 1
        if line['link_1'] not in avps or line['link_2'] not in avps:
            br_status = 0

        rate_a, rate_b, rate_c = grg_common.get_thermal_rates(line)

        gi = 0.0
        bi = 0.0
        if 'shunt_1' in line:
            gi = line['shunt_1']['conductance']
            bi = line['shunt_1']['susceptance']

        gj = 0.0
        bj = 0.0
        if 'shunt_2' in line:
            gj = line['shunt_2']['conductance']
            bj = line['shunt_2']['susceptance']

        b = 0.0
        psse_line_charge = 0
        if 'psse_line_charge' in line:
            psse_line_charge = line['psse_line_charge']
            b = psse_line_charge
            bi = bi - b/2.0
            bj = bj - b/2.0

        owners = {
            'o1':1, 'f1':1.0,
            'o2':0, 'f2':1.0,
            'o3':0, 'f3':1.0,
            'o4':0, 'f4':1.0,
        }

        if line['id'] in owner_index_lookup:
            line_owners = owner_index_lookup[line['id']]
            if len(line_owners) > 4:
                print_err('warning: more than 4 line owners found, using the first 4')
            for i,oid in enumerate(line_owners):
                k = 'o{}'.format(i+1)
                owners[k] = oid

        branch_args = {
            'index': branch_index_lookup[line['id']],
            'i': from_bus_id,
            'j': to_bus_id,
            'ckt': '\'{}\''.format(line.get('circuit_id', '')),
            'r': line['impedance']['resistance'],
            'x': line['impedance']['reactance'],
            'b': b,
            'ratea': round(base_mva*rate_a, float_precision),
            'rateb': round(base_mva*rate_b, float_precision),
            'ratec': round(base_mva*rate_c, float_precision),
            'gi': gi,
            'bi': bi,
            'gj': gj,
            'bj': bj,
            'st': br_status,
            'met': line.get('met', 1),
            'len': line.get('len', 0.0),
        }

        branch_args.update(owners)

        psse_branch = Branch(**branch_args)

        psse_branches.append(psse_branch)

        #print(psse_branch)
        del line
    psse_branches.sort(key=lambda x: x.index)



    xfer_index_lookup = {}
    if all('source_id' in xfer for xfer in cbt['two_winding_transformer']):
        for xfer in cbt['two_winding_transformer']:
            xfer_index_lookup[xfer['id']] = int(xfer['source_id'])
    else:
        for i,k in enumerate(sorted(cbt['two_winding_transformer'], key=lambda x: x['id'])):
            xfer_index_lookup[k['id']] = i

    for xfer in cbt['two_winding_transformer']:
        from_bus_id = vp2int[xfer['link_1']]
        to_bus_id = vp2int[xfer['link_2']]

        from_bus = psse_bus_lookup[from_bus_id]
        to_bus = psse_bus_lookup[to_bus_id]


        xfer_status = 1
        if xfer['link_1'] not in avps or xfer['link_2'] not in avps:
            xfer_status = 0

        key = '{}/tap_changer/position'.format(xfer['id'])
        if key in starting_point_map:
            tap_position = starting_point_map[key]
        else:
            print_err('warning: skipping transformer {} due to missing tap position setting'.format(xfer['id']))
            continue

        transform = xfer['tap_changer']['transform']

        tap_value = grg_common.tap_setting(xfer['tap_changer'], tap_position)
        if tap_value == None:
            print_err('warning: skipping transformer {} due to missing tap position values'.format(xfer['id']))

        rate_a, rate_b, rate_c = grg_common.get_thermal_rates(xfer)

        owners = {
            'o1':1, 'f1':1.0,
            'o2':0, 'f2':1.0,
            'o3':0, 'f3':1.0,
            'o4':0, 'f4':1.0,
        }

        if xfer['id'] in owner_index_lookup:
            xfer_owners = owner_index_lookup[xfer['id']]
            if len(xfer_owners) > 4:
                print_err('warning: more than 4 transformer owners found, using the first 4')
            for i,oid in enumerate(xfer_owners):
                k = 'o{}'.format(i+1)
                owners[k] = oid


        xfer_fl_args = {
            'i': from_bus_id,
            'j': to_bus_id,
            'k': 0,
            'ckt': '\'{}\''.format(xfer.get('circuit_id', '')),
            'cw': xfer.get('cw', 1),
            'cz': xfer.get('cz', 1),
            'cm': xfer.get('cm', 1),
            'mag1': tap_value['shunt']['conductance'],
            'mag2': tap_value['shunt']['susceptance'],
            'nmetr': xfer.get('nmetr', 2),
            'name': '\'{}\''.format(xfer.get('psse_name', '')),
            'stat': xfer_status,
            'vecgrp': '\'{}\''.format(xfer.get('vecgrp', '            ')),
        }
        xfer_fl_args.update(owners)

        xfer_fl = TransformerParametersFirstLine(**xfer_fl_args)


        xfer_sls_args = {
            'r12': tap_value['impedance']['resistance'],
            'x12': tap_value['impedance']['reactance'],
            'sbase12': base_mva,
        }
        xfer_sls = TransformerParametersSecondLineShort(**xfer_sls_args)


        xfer_w1_args = {
            'index': 1,
            'windv': tap_value['transform']['tap_ratio'],
            'nomv': from_bus.basekv,
            'ang': round(math.degrees(tap_value['transform']['angle_shift']), float_precision),
            'rata': round(base_mva*rate_a, float_precision),
            'ratb': round(base_mva*rate_b, float_precision),
            'ratc': round(base_mva*rate_c, float_precision),
            'cod': xfer.get('cod', -1),
            'cont': xfer.get('cont', 0),
            'rma': xfer.get('rma', grg_common.max_value(transform['tap_ratio'])),
            'rmi': xfer.get('rmi', grg_common.min_value(transform['tap_ratio'])),
            'vma': xfer.get('vma', grg_common.max_value(transform['tap_ratio'])),
            'vmi': xfer.get('vmi', grg_common.min_value(transform['tap_ratio'])),
            'ntp': xfer['tap_changer'].get('ntp', 2),
            'tab': xfer.get('tab', 0),
            'cr': xfer.get('cr', 0.0),
            'cx': xfer.get('cx', 0.0),
            'cnxa': xfer.get('cnxa', 0.0),
        }
        xfer_w1 = TransformerWinding(**xfer_w1_args)

        xfer_w2s_args = {
            'index': 2,
            'windv': xfer.get('windv_2', 1.0),
            'nomv': to_bus.basekv,
        }
        xfer_w2s = TransformerWindingShort(**xfer_w2s_args)

        psse_xfer = TwoWindingTransformer(xfer_index_lookup[xfer['id']], xfer_fl, xfer_sls, xfer_w1, xfer_w2s)

        psse_transformers.append(psse_xfer)

        #print(psse_xfer)
        del xfer
    psse_transformers.sort(key=lambda x: x.index)


    gen_index_lookup = {}
    if all('source_id' in gen for gen in cbt['generator']) and \
        all('source_id' in syn_cond for syn_cond in cbt['synchronous_condenser']):
        for gen in cbt['generator']:
            gen_index_lookup[gen['id']] = int(gen['source_id'])
        for syn_cond in cbt['synchronous_condenser']:
            gen_index_lookup[syn_cond['id']] = int(syn_cond['source_id'])
    else:
        offset = 0
        for i, k in enumerate(sorted(cbt['generator'], key=lambda x: x['id'])):
            gen_index_lookup[k['id']] = i+offset 

        offset = len(cbt['generator'])
        for i, k in enumerate(sorted(cbt['synchronous_condenser'], key=lambda x: x['id'])):
            gen_index_lookup[k['id']] = i+offset 


    for gen in cbt['generator']:
        bus_id = vp2int[gen['link']]

        pg = 0.0
        qg = 0.0
        key = '{}/output'.format(gen['id'])
        if key in starting_point_map:
            output = starting_point_map[key]
            if 'active' in output:
                pg = output['active']
            if 'reactive' in output:
                qg = output['reactive']

        vs = 1.0
        if 'vs' in gen:
            vs = gen['vs']

        mbase = base_mva
        if 'mbase' in gen:
            mbase = gen['mbase']

        gen_status = 1
        if gen['link'] not in avps:
            gen_status = 0


        owners = {
            'o1':1, 'f1':1.0,
            'o2':0, 'f2':1.0,
            'o3':0, 'f3':1.0,
            'o4':0, 'f4':1.0,
        }

        if gen['id'] in owner_index_lookup:
            gen_owners = owner_index_lookup[gen['id']]
            if len(gen_owners) > 4:
                print_err('warning: more than 4 generator owners found, using the first 4')
            for i,oid in enumerate(gen_owners):
                k = 'o{}'.format(i+1)
                owners[k] = oid

        gen_args = {
            'index': gen_index_lookup[gen['id']],
            'i': bus_id,
            'id': '\'{}\''.format(gen.get('psse_id', '')),
            'pg': round(base_mva*pg, float_precision),
            'qg': round(base_mva*qg, float_precision),
            'qt': round(base_mva*grg_common.max_value(gen['output']['reactive']), float_precision),
            'qb': round(base_mva*grg_common.min_value(gen['output']['reactive']), float_precision),
            'vs': vs,
            'ireg': gen.get('ireg', 0),
            'mbase' : mbase,
            'zr': gen.get('zr', 0.0), 
            'zx': gen.get('zx', 1.0),
            'rt': gen.get('rt', 0.0),
            'xt': gen.get('xt', 0.0),
            'gtap': gen.get('gtap', 1.0),
            'stat': gen_status,
            'rmpct': gen.get('rmpct', 100.0),
            'pt': round(base_mva*grg_common.max_value(gen['output']['active']), float_precision),
            'pb': round(base_mva*grg_common.min_value(gen['output']['active']), float_precision),
            'wmod': gen.get('wmod', 0),
            'wpf': gen.get('wpf', 1.0),
        }
        gen_args.update(owners)

        psse_gen = Generator(**gen_args)

        psse_gens.append(psse_gen)

        #print(psse_gen)
        del gen


    for syn_cond in cbt['synchronous_condenser']:
        bus_id = vp2int[syn_cond['link']]

        qg = 0.0
        key = '{}/output'.format(syn_cond['id'])
        if key in starting_point_map:
            output = starting_point_map[key]
            if 'reactive' in output:
                qg = output['reactive']

        vs = 1.0
        if 'vs' in syn_cond:
            vs = syn_cond['vs']

        mbase = base_mva
        if 'mbase' in syn_cond:
            mbase = syn_cond['mbase']

        gen_status = 1
        if syn_cond['link'] not in avps:
            gen_status = 0

        owners = {
            'o1':1, 'f1':1.0,
            'o2':0, 'f2':1.0,
            'o3':0, 'f3':1.0,
            'o4':0, 'f4':1.0,
        }

        if syn_cond['id'] in owner_index_lookup:
            gen_owners = owner_index_lookup[syn_cond['id']]
            if len(gen_owners) > 4:
                print_err('warning: more than 4 generator owners found, using the first 4')
            for i,oid in enumerate(gen_owners):
                k = 'o{}'.format(i+1)
                owners[k] = oid

        gen_args = {
            'index': gen_index_lookup[syn_cond['id']],
            'i': bus_id,
            'id': syn_cond.get('psse_id', ''),
            'pg': 0.0,
            'qg': round(base_mva*qg, float_precision),
            'qt': round(base_mva*grg_common.max_value(syn_cond['output']['reactive']), float_precision),
            'qb': round(base_mva*grg_common.min_value(syn_cond['output']['reactive']), float_precision),
            'vs': vs,
            'ireg': syn_cond.get('ireg', 0),
            'mbase' : mbase,
            'zr': syn_cond.get('zr', 0.0), 
            'zx': syn_cond.get('zx', 1.0),
            'rt': syn_cond.get('rt', 0.0),
            'xt': syn_cond.get('xt', 0.0),
            'gtap': syn_cond.get('gtap', 1.0),
            'stat': gen_status,
            'rmpct': syn_cond.get('rmpct', 100.0),
            'pt': 0.0,
            'pb': 0.0,
            'o1': syn_cond.get('o1', 1),
            'f1': syn_cond.get('f1', 1.0),
            'o2': syn_cond.get('o2', 0),
            'f2': syn_cond.get('f2', 1.0),
            'o3': syn_cond.get('o3', 0),
            'f3': syn_cond.get('f3', 1.0),
            'o4': syn_cond.get('o4', 0),
            'f4': syn_cond.get('f4', 1.0),
            'wmod': syn_cond.get('wmod', 0),
            'wpf': syn_cond.get('wpf', 0.0),
        }
        gen_args.update(owners)

        psse_gen = Generator(**gen_args)

        psse_gens.append(psse_gen)

        #print(psse_gen)
        del syn_cond
    psse_gens.sort(key=lambda x: x.index)

    psse_ic = 0
    if 'ic' in network:
        psse_ic = network['ic']

    record1 = ''
    record2 = ''
    if 'description' in network:
        description = network['description']
        if not grg_description_preamble in description:
            if len(description) <= 60:
                record1 = description
            else:
                record1 = description[:60]
                record2 = description[60:]
        else:
            description_parts = description.split('\n')
            assert(len(description_parts) >= 3)
            record1 = description_parts[1]
            record2 = description_parts[2]
    record1 = record1[:60]
    record2 = record2[:60]

    case_args = {
        'ic': network.get('ic', 0),
        'sbase': network.get('sbase', base_mva),
        'rev': network.get('rev', 33),
        'xfrrat': network.get('xfrrat', 0),
        'nxfrat': network.get('nxfrat', 0),
        'basfrq': network.get('basfrq', 60.0),
        'record1': record1,
        'record2': record1,
        'buses': psse_buses,
        'loads': psse_loads,
        'fixed_shunts': psse_fixed_shunts,
        'generators': psse_gens,
        'branches': psse_branches,
        'transformers': psse_transformers,
        'areas': psse_areas,
        'tt_dc_lines': [],
        'vsc_dc_lines': [],
        'transformer_corrections': [],
        'mt_dc_lines': [],
        'line_groupings': [],
        'zones': psse_zones,
        'transfers': [],
        'owners': psse_owners,
        'facts': [],
        'switched_shunts': psse_switched_shunts,
        'gnes': [],
        'induction_machines': [],
    }
    case = Case(**case_args)

    return case


def psse_name(data, default_name, name_key = 'name', length=8):
    psse_name = default_name
    if name_key in data:
        psse_name = data[name_key]
    return psse_name[:length]

def test_idempotent(input_data_file, name):
    case1 = parse_psse_case_file(input_data_file)
    grg_data = case1.to_grg(name)
    case2 = build_psse_case(grg_data, 'starting_points', 'breakers_assignment')
    return case1, case2


# Note main(args) used here instead of main(), to enable easy unit testing
def main(args):
    '''reads a psse or grg case files and processes them based on command 
    line arguments.

    Args:
        args: an argparse data structure
    '''

    #start = time.time()

    if args.file.endswith('.raw'):
        name = args.file[:-4]

        if not args.idempotent:
            case = parse_psse_case_file(args.file)
            #print('internal PSSE representation:')
            #print(case)
            #print(time.time() - start)
            #start = time.time()
            print_err('')

            print_err('inferred network name: %s' % name)
            grg_data = case.to_grg(name, args.omit_subtypes, args.skip_validation)
            if grg_data != None:
                print_err('grg data representation:')
                print(json.dumps(grg_data, sort_keys=True, indent=2, \
                                 separators=(',', ': ')))
                #print(time.time() - start)
                print_err('')
            return
        else:
            case1, case2 = test_idempotent(args.file, name)
            if case1 != case2:
                diff(case1, case2)
                #print(case1)
                #print(case2)
            print('idempotent test: '+str(case1 == case2))
            return


    if args.file.endswith('.json'):
        if args.idempotent:
            print('idempotent test only supported on PSSE files.')
            return

        grg_data = parse_grg_case_file(args.file)
        #print('internal grg data representation:')
        #print(grg_data)
        #print('')

        print_err('working with starting point: {}'.format(args.starting_point_mapping))
        print_err('working with switch assignment: {}'.format(args.switch_assignment_mapping))

        # if args.transform != None:
        #     case = build_psse_case_transform(grg_data, args.transform)
        # elif args.network != None:
        #     case = build_psse_case_network(grg_data, args.network)
        # else:
        #     network_name = grg_data['network'].keys()[0]
        #     case = build_psse_case_network(grg_data, network_name)

        case = build_psse_case(grg_data, args.starting_point_mapping, args.switch_assignment_mapping)

        print('PSSE representation:')
        print(case.to_psse())

        print('')
        return

    print('file extension not recognized!')


def build_cli_parser():
    parser = argparse.ArgumentParser(
        description='''grg_psse2grg.%(prog)s is a tool for converting power 
            network dataset between the PSSE and GRG formats.
            The converted file is printed to standard out''',

        epilog='''Please file bugs at...''',
    )
    parser.add_argument('file', help='the data file to operate on (.raw|.json)')
    parser.add_argument('-spm', '--starting-point-mapping', help='a grg starting point mapping to be use as a basis for the psse case', default='starting_points')
    parser.add_argument('-sam', '--switch-assignment-mapping', help='a grg switch mapping to be use as a basis for the psse case', default='breakers_assignment')
    parser.add_argument('-i', '--idempotent', help='tests the translation of a given psse file is idempotent', action='store_true')
    parser.add_argument('-os', '--omit-subtypes', help='ommits optional component subtypes when translating from psse to grg', default=False, action='store_true')
    parser.add_argument('-sv', '--skip-validation', help='skips the grg validation step when translating from psse to grg', default=False, action='store_true')

    #parser.add_argument('--foo', help='foo help')
    version = __import__('grg_psse2grg').__version__
    parser.add_argument('-v', '--version', action='version', \
        version='grg_psse2grg.%(prog)s (version '+version+')')

    return parser


if __name__ == '__main__':
    parser = build_cli_parser()
    main(parser.parse_args())
