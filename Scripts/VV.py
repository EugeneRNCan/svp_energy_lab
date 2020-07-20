"""
Copyright (c) 2018, Sandia National Labs, SunSpec Alliance and CanmetENERGY(Natural Resources Canada)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the names of the Sandia National Labs, SunSpec Alliance and CanmetENERGY(Natural Resources Canada)
nor the names of its contributors may be used to endorse or promote products derived from
this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Questions can be directed to support@sunspec.org
"""

import sys
import os
import traceback
from svpelab import gridsim
from svpelab import loadsim
from svpelab import pvsim
from svpelab import das
from svpelab import der
from svpelab import hil
from svpelab import p1547
import script
from svpelab import result as rslt
from datetime import datetime, timedelta

import numpy as np
import collections
import cmath
import math

VV = 'VV'
V = 'V'
F = 'F'
P = 'P'
Q = 'Q'

def volt_vars_mode(vv_curves, vv_response_time, pwr_lvls, v_ref_value):

    result = script.RESULT_FAIL
    daq = None
    v_nom = None
    grid = None
    pv = None
    eut = None
    chil = None
    result_summary = None
    dataset_filename = None

    try:
        cat = ts.param_value('eut.cat')
        cat2 = ts.param_value('eut.cat2')
        sink_power = ts.param_value('eut.sink_power')
        p_rated = ts.param_value('eut.p_rated')
        p_rated_prime = ts.param_value('eut.p_rated_prime')
        var_rated = ts.param_value('eut.var_rated')
        s_rated = ts.param_value('eut.s_rated')

        #absorb_enable = ts.param_value('eut.abs_enabled')
        # DC voltages
        v_in_nom = ts.param_value('eut.v_in_nom')
        #v_min_in = ts.param_value('eut.v_in_min')
        #v_max_in = ts.param_value('eut.v_in_max')

        # AC voltages
        v_nom = ts.param_value('eut.v_nom')
        v_low = ts.param_value('eut.v_low')
        v_high = ts.param_value('eut.v_high')
        p_min = ts.param_value('eut.p_min')
        p_min_prime = ts.param_value('eut.p_min_prime')
        phases = ts.param_value('eut.phases')

        """
        A separate module has been create for the 1547.1 Standard
        """
        #lib_1547 = p1547.module_1547(ts=ts, aif=VV)
        #ts.log_debug("1547.1 Library configured for %s" % VoltVar.get_test_name())
        VoltVar = p1547.VoltVar(ts=ts, imbalance=False)
        result_summary = VoltVar.get_rslt_sum_col_name()

        # result params
        result_params = VoltVar.get_rslt_param_plot()
        ts.log_debug(result_params)

        '''
        a) Connect the EUT according to the instructions and specifications provided by the manufacturer.
        '''

        # initialize HIL environment, if necessary
        chil = hil.hil_init(ts)
        if chil is not None:
            chil.config()

        # pv simulator is initialized with test parameters and enabled
        pv = pvsim.pvsim_init(ts)
        if pv is not None:
            pv.power_set(p_rated)
            pv.power_on()  # Turn on DC so the EUT can be initialized

        # DAS soft channels
        #das_points = {'sc': ('Q_TARGET', 'Q_TARGET_MIN', 'Q_TARGET_MAX', 'Q_MEAS', 'V_TARGET', 'V_MEAS', 'event')}
        das_points = VoltVar.get_sc_points()
        ts.log(f'scpoints={das_points}')
        txt=das_points['sc']
        ts.log(f'scpoints={txt}')

        # initialize data acquisition system
        daq = das.das_init(ts, sc_points=das_points['sc'], support_interfaces={'pvsim': pv})

        daq.sc['V_TARGET'] = v_nom
        daq.sc['Q_TARGET'] = 100
        daq.sc['Q_TARGET_MIN'] = 100
        daq.sc['Q_TARGET_MAX'] = 100
        daq.sc['event'] = 'None'

        ts.log('DAS device: %s' % daq.info())

        '''
        b) Set all voltage trip parameters to the widest range of adjustability.  Disable all reactive/active power
        control functions.
        '''

        eut = der.der_init(ts)
        if eut is not None:
            eut.config()
            ts.log_debug(eut.measurements())

            #Deactivating all functions on EUT
            #eut.deactivate_all_fct()

            ts.log_debug('Voltage trip parameters set to the widest range: v_min: {0} V, '
                         'v_max: {1} V'.format(v_low, v_high))
            try:
                eut.vrt_stay_connected_high(params={'Ena': True, 'ActCrv': 0, 'Tms1': 3000,
                                                    'V1': v_high, 'Tms2': 0.16, 'V2': v_high})
            except Exception as e:
                ts.log_error('Could not set VRT Stay Connected High curve. %s' % e)
            try:
                eut.vrt_stay_connected_low(params={'Ena': True, 'ActCrv': 0, 'Tms1': 3000,
                                                   'V1': v_low, 'Tms2': 0.16, 'V2': v_low})
            except Exception as e:
                ts.log_error('Could not set VRT Stay Connected Low curve. %s' % e)
        else:
            ts.log_debug('Set L/HVRT and trip parameters set to the widest range of adjustability possible.')

        # Special considerations for CHIL ASGC/Typhoon startup
        if chil is not None:
            inv_power = eut.measurements().get('W')
            timeout = 120.
            if inv_power <= p_rated * 0.85:
                pv.irradiance_set(995)  # Perturb the pv slightly to start the inverter
                ts.sleep(3)
                eut.connect(params={'Conn': True})
            while inv_power <= p_rated * 0.85 and timeout >= 0:
                ts.log('Inverter power is at %0.1f. Waiting up to %s more seconds or until EUT starts...' %
                       (inv_power, timeout))
                ts.sleep(1)
                timeout -= 1
                inv_power = eut.measurements().get('W')
                if timeout == 0:
                    result = script.RESULT_FAIL
                    raise der.DERError('Inverter did not start.')
            ts.log('Waiting for EUT to ramp up')
            ts.sleep(8)
            ts.log_debug('DAS data_read(): %s' % daq.data_read())

        '''
        c) Set all AC test source parameters to the nominal operating voltage and frequency.
        '''
        grid = gridsim.gridsim_init(ts, support_interfaces={'hil': chil})  # Turn on AC so the EUT can be initialized
        if grid is not None:
            grid.voltage(v_nom)

        # open result summary file
        result_summary_filename = 'result_summary.csv'
        result_summary = open(ts.result_file_path(result_summary_filename), 'a+')
        ts.result_file(result_summary_filename)
        result_summary.write(VoltVar.get_rslt_sum_col_name())

        '''
        d) Adjust the EUT's available active power to Prated. For an EUT with an input voltage range, set the input
        voltage to Vin_nom. The EUT may limit active power throughout the test to meet reactive power requirements.
        For an EUT with an input voltage range.
        '''

        if pv is not None:
            pv.iv_curve_config(pmp=p_rated, vmp=v_in_nom)
            pv.irradiance_set(1000.)

        '''
        gg) Repeat steps g) through dd) for characteristics 2 and 3.
        '''
        for vv_curve in vv_curves:
            ts.log('Starting test with characteristic curve %s' % (vv_curve))
            v_pairs = VoltVar.get_params(curve=vv_curve)
            ts.log_debug('v_pairs:%s' % v_pairs)
            ts.log_debug(v_pairs)

            '''
            ff) Repeat test steps d) through ee) at EUT power set at 20% and 66% of rated power.
            '''
            for power in pwr_lvls:
                if pv is not None:
                    pv_power_setting = (p_rated * power)
                    pv.iv_curve_config(pmp=pv_power_setting, vmp=v_in_nom)
                    pv.irradiance_set(1000.)

                VoltVar.reset_param(pwr=power, curve=vv_curve)

                # Special considerations for CHIL ASGC/Typhoon startup #
                if chil is not None:
                    inv_power = eut.measurements().get('W')
                    timeout = 120.
                    if inv_power <= pv_power_setting * 0.85:
                        pv.irradiance_set(995)  # Perturb the pv slightly to start the inverter
                        ts.sleep(3)
                        eut.connect(params={'Conn': True})
                    while inv_power <= pv_power_setting * 0.85 and timeout >= 0:
                        ts.log('Inverter power is at %0.1f. Waiting up to %s more seconds or until EUT starts...' %
                               (inv_power, timeout))
                        ts.sleep(1)
                        timeout -= 1
                        inv_power = eut.measurements().get('W')
                        if timeout == 0:
                            result = script.RESULT_FAIL
                            raise der.DERError('Inverter did not start.')
                    ts.log('Waiting for EUT to ramp up')
                    ts.sleep(8)

                '''
                ee) Repeat test steps e) through dd) with Vref set to 1.05*VN and 0.95*VN, respectively.
                '''
                for v_ref in v_ref_value:

                    ts.log('Setting v_ref at %s %% of v_nom' % (int(v_ref * 100)))

                    #Setting grid to vnom before test
                    if grid is not None:
                        grid.voltage(v_nom)

                    if eut is not None:
                        '''
                        e) Set EUT volt-var parameters to the values specified by Characteristic 1.
                        All other function should be turned off. Turn off the autonomously adjusting reference voltage.
                        '''
                        # Activate volt-var function with following parameters
                        # SunSpec convention is to use percentages for V and Q points.
                        vv_curve_params = {
                            'v': [(v_pairs['V1'] / v_nom) * 100, (v_pairs['V2'] / v_nom) * 100,
                                  (v_pairs['V3'] / v_nom) * 100, (v_pairs['V4'] / v_nom) * 100],
                            'var': [(v_pairs['Q1'] / s_rated) * 100, (v_pairs['Q2'] / s_rated) * 100,
                                    (v_pairs['Q3'] / s_rated) * 100, (v_pairs['Q4'] / s_rated) * 100],
                            'vref': round(v_nom*v_ref,2),
                            'RmpPtTms': vv_response_time[vv_curve]
                        }
                        ts.log_debug('Sending VV points: %s' % vv_curve_params)
                        eut.volt_var(params={'Ena': True, 'ACTCRV': vv_curve, 'curve': vv_curve_params})
                        # TODO autonomous vref adjustment to be included
                        # eut.autonomous_vref_adjustment(params={'Ena': False})
                        '''
                        f) Verify volt-var mode is reported as active and that the correct characteristic is reported.
                        '''
                        ts.log_debug('Initial EUT VV settings are %s' % eut.volt_var())


                    v_steps_dict = collections.OrderedDict()
                    a_v = VoltVar.MRA['V'] * 1.5

                    VoltVar.set_step_label(starting_label='G')

                    # Capacitive test
                    # Starting from step F
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V3'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V3'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = (v_pairs['V3'] + v_pairs['V4']) / 2
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V4'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V4'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_high - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V4'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V4'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = (v_pairs['V3'] + v_pairs['V4']) / 2
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V3'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V3'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_ref*v_nom

                    # Inductive test
                    # Step S
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V2'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V2'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = (v_pairs['V1'] + v_pairs['V2']) / 2
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V1'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V1'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_low + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V1'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V1'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = (v_pairs['V1'] + v_pairs['V2']) / 2
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V2'] - a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_pairs['V2'] + a_v
                    v_steps_dict[VoltVar.get_step_label()] = v_ref*v_nom


                    for step, target in v_steps_dict.items():
                        v_steps_dict.update({step: round(target, 2)})
                        if target > v_high:
                            v_steps_dict.update({step: v_high})
                        elif target < v_low:
                            v_steps_dict.update({step: v_low})

                    #Skips steps when V4 is higher than Vmax of EUT
                    if v_pairs['V4'] > v_high:
                        ts.log_debug('Since V4 is higher than Vmax, Skipping a few steps')
                        del v_steps_dict['Step J']
                        del v_steps_dict['Step K']
                        del v_steps_dict['Step M']
                        del v_steps_dict['Step N']

                    # Skips steps when V1 is lower than Vmin of EUT
                    if v_pairs['V1'] < v_low:
                        ts.log_debug('Since V1 is lower than Vmin, Skipping a few steps')
                        del v_steps_dict['Step V']
                        del v_steps_dict['Step W']
                        del v_steps_dict['Step Y']
                        del v_steps_dict['Step Z']

                    ts.log_debug(v_steps_dict)

                    dataset_filename = 'VV_%s_PWR_%d_vref_%d' % (vv_curve, power * 100, v_ref*100)
                    ts.log('------------{}------------'.format(dataset_filename))
                    # Start the data acquisition systems
                    daq.data_capture(True)

                    for step_label, v_step in v_steps_dict.items():
                        v_step_dict_updated = {V: v_step}
                        ts.log('Voltage step: setting Grid simulator voltage to %s (%s)' % (v_step, step_label))
                        #q_initial = VoltVar.start(daq=daq, step=step_label)
                        #ts.log_debug(q_initial)
                        q_1 = VoltVar.start(daq=daq, step=step_label)
                        tr = VoltVar.record_timeresponse(daq=daq, tr=vv_response_time[vv_curve], n_tr=2, step=step_label)
                        VoltVar.open_loop_resp_criteria(tr=2)

                        ts.log(f'q_1={q_1}')
                        ts.log(f'tr={tr}')
                        if grid is not None:
                            grid.voltage(v_step)
                        '''
                        lib_1547.process_data(
                            daq=daq,
                            tr=vv_response_time[vv_curve],
                            step=step_label,
                            initial_value=q_initial,
                            curve=vv_curve,
                            pwr_lvl=power,
                            x_target=v_step_dict_updated,
                            y_target=None,
                            result_summary=result_summary,
                            filename=dataset_filename
                        )
                        '''
                    ts.log('Sampling complete')
                    dataset_filename = dataset_filename + ".csv"
                    daq.data_capture(False)
                    ds = daq.data_capture_dataset()
                    ts.log('Saving file: %s' % dataset_filename)
                    ds.to_csv(ts.result_file_path(dataset_filename))
                    result_params['plot.title'] = dataset_filename.split('.csv')[0]
                    ts.result_file(dataset_filename, params=result_params)
                    result = script.RESULT_COMPLETE



    except script.ScriptFail as e:
        reason = str(e)
        if reason:
            ts.log_error(reason)

    except Exception as e:
        if dataset_filename is not None:
            dataset_filename = dataset_filename + ".csv"
            daq.data_capture(False)
            ds = daq.data_capture_dataset()
            ts.log('Saving file: %s' % dataset_filename)
            ds.to_csv(ts.result_file_path(dataset_filename))
            result_params['plot.title'] = dataset_filename.split('.csv')[0]
            ts.result_file(dataset_filename, params=result_params)
        ts.log_error('Test script exception: %s' % traceback.format_exc())


    finally:
        if daq is not None:
            daq.close()
        if pv is not None:
            pv.close()
        if grid is not None:
            if v_nom is not None:
                grid.voltage(v_nom)
            grid.close()
        if chil is not None:
            chil.close()
        if eut is not None:
            #eut.volt_var(params={'Ena': False})
            eut.close()
        if result_summary is not None:
            result_summary.close()


    return result


def volt_vars_mode_vref_test():
    return 1

def volt_var_mode_imbalanced_grid(imbalance_resp, vv_curves, vv_response_time):

    result = script.RESULT_FAIL
    daq = None
    v_nom = None
    p_rated = None
    grid = None
    pv = None
    eut = None
    chil = None
    result_summary = None
    dataset_filename = None

    try:
        #cat = ts.param_value('eut.cat')
        #cat2 = ts.param_value('eut.cat2')
        #sink_power = ts.param_value('eut.sink_power')
        p_rated = ts.param_value('eut.p_rated')
        #p_rated_prime = ts.param_value('eut.p_rated_prime')
        var_rated = ts.param_value('eut.var_rated')
        s_rated = ts.param_value('eut.s_rated')

        #absorb_enable = ts.param_value('eut.abs_enabled')

        # DC voltages
        v_in_nom = ts.param_value('eut.v_in_nom')
        #v_min_in = ts.param_value('eut.v_in_min')
        #v_max_in = ts.param_value('eut.v_in_max')

        # AC voltages
        v_nom = ts.param_value('eut.v_nom')
        v_min = ts.param_value('eut.v_low')
        v_max = ts.param_value('eut.v_high')
        p_min = ts.param_value('eut.p_min')
        p_min_prime = ts.param_value('eut.p_min_prime')
        phases = ts.param_value('eut.phases')
        pf_response_time = ts.param_value('vv.test_imbalanced_t_r')

        # Pass/fail accuracies
        pf_msa = ts.param_value('eut.pf_msa')
        # According to Table 3-Minimum requirements for manufacturers stated measured and calculated accuracy
        MSA_Q = 0.05 * s_rated
        MSA_P = 0.05 * s_rated
        MSA_V = 0.01 * v_nom

        imbalance_fix = ts.param_value('vv.imbalance_fix')

        """
        A separate module has been create for the 1547.1 Standard
        """
        #lib_1547 = p1547.module_1547(ts=ts, aif='VV', imbalance_angle_fix=imbalance_fix)
        VoltVar = p1547.VoltVar(ts=ts, imbalance=True)
        ts.log_debug('1547.1 Library configured for %s' % VoltVar.get_test_name())

        # Get the rslt parameters for plot
        result_params = VoltVar.get_rslt_param_plot()

        '''
        a) Connect the EUT according to the instructions and specifications provided by the manufacturer.
        '''
        # initialize HIL environment, if necessary
        chil = hil.hil_init(ts)
        if chil is not None:
            chil.config()

        # grid simulator is initialized with test parameters and enabled
        grid = gridsim.gridsim_init(ts)  # Turn on AC so the EUT can be initialized
        if grid is not None:
            grid.voltage(v_nom)

        # pv simulator is initialized with test parameters and enabled
        pv = pvsim.pvsim_init(ts)
        pv.power_set(p_rated)
        pv.power_on()  # Turn on DC so the EUT can be initialized

        # DAS soft channels
        das_points = VoltVar.get_sc_points()

        # initialize data acquisition system
        daq = das.das_init(ts, sc_points=das_points['sc'])
        if daq is not None:
            daq.sc['Q_TARGET'] = 100
            daq.sc['Q_TARGET_MIN'] = 100
            daq.sc['Q_TARGET_MAX'] = 100
            daq.sc['V_TARGET'] = v_nom
            daq.sc['event'] = 'None'
            ts.log('DAS device: %s' % daq.info())

        '''
        b) Set all voltage trip parameters to the widest range of adjustability. Disable all reactive/active power
        control functions.
        '''

        '''
        c) Set all AC test source parameters to the nominal operating voltage and frequency.
        '''
        if grid is not None:
            grid.voltage(v_nom)

        # open result summary file
        result_summary_filename = 'result_summary.csv'
        result_summary = open(ts.result_file_path(result_summary_filename), 'a+')
        ts.result_file(result_summary_filename)

        result_summary.write(VoltVar.get_rslt_sum_col_name())

        '''
         d) Adjust the EUT's available active power to Prated. For an EUT with an input voltage range, set the input
        voltage to Vin_nom.
        '''

        if pv is not None:
            pv.iv_curve_config(pmp=p_rated, vmp=v_in_nom)
            pv.irradiance_set(1000.)

        '''
        h) Once steady state is reached, begin the adjustment of phase voltages.
        '''

        """
        Test start
        """

        for imbalance_response in imbalance_resp:
            for vv_curve in vv_curves:

                '''
                 e) Set EUT volt-watt parameters to the values specified by Characteristic 1. All other function be turned off.
                 '''
                #Setting up v_pairs value corresponding to desired curve
                v_pairs = VoltVar.get_params(curve=vv_curve)
                ts.log_debug('v_pairs:%s' % v_pairs)
                #Setting up step label
                lib_1547.set_step_label(starting_label='G')


                # it is assumed the EUT is on
                eut = der.der_init(ts)
                if eut is not None:
                    vv_curve_params = {'v': [v_pairs['V1']*(100/v_nom), v_pairs['V2']*(100/v_nom),
                                             v_pairs['V3']*(100/v_nom), v_pairs['V4']*(100/v_nom)],
                                       'q': [v_pairs['Q1']*(100/var_rated), v_pairs['Q2']*(100/var_rated),
                                             v_pairs['Q3']*(100/var_rated), v_pairs['Q4']*(100/var_rated)],
                                       'DeptRef': 'Q_MAX_PCT'}
                    ts.log_debug('Sending VV points: %s' % vv_curve_params)
                    eut.volt_var(params={'Ena': True, 'curve': vv_curve_params})

                '''
                f) Verify volt-var mode is reported as active and that the correct characteristic is reported.
                '''
                if eut is not None:
                    ts.log_debug('Initial EUT VV settings are %s' % eut.volt_var())
                ts.log_debug('curve points:  %s' % v_pairs)

                '''
                g) Wait for steady state to be reached.
    
                Every time a parameter is stepped or ramped, measure and record the time domain current and voltage
                response for at least 4 times the maximum expected response time after the stimulus, and measure or
                derive, active power, apparent power, reactive power, and power factor.
                '''

                step = VoltVar.get_step_label()

                daq.sc['event'] = step
                daq.data_sample()
                ts.log('Wait for steady state to be reached')
                ts.sleep(2 * vv_response_time[vv_curve])
                ts.log(imbalance_resp)

                ts.log('Starting imbalance test with VV mode at %s' % (imbalance_response))

                if imbalance_fix == "Yes":
                    dataset_filename = 'VV_IMB_%s_FIX' % (imbalance_response)
                else:
                    dataset_filename = 'VV_IMB_%s' % (imbalance_response)
                ts.log('------------{}------------'.format(dataset_filename))
                # Start the data acquisition systems
                daq.data_capture(True)

                '''
                h) For multiphase units, step the AC test source voltage to Case A from Table 24.
                '''
                if grid is not None:
                    step_label = VoltVar.get_step_label()
                    ts.log('Voltage step: setting Grid simulator to case A (IEEE 1547.1-Table 24)(%s)' % step)
                    q_initial = VoltVar.get_initial_value(daq=daq, step=step_label)
                    lib_1547.set_grid_asymmetric(grid=grid, case='case_a')

                    lib_1547.process_data(
                        daq=daq,
                        tr=vv_response_time[vv_curve],
                        step=step_label,
                        initial_value=q_initial,
                        curve=vv_curve,
                        pwr_lvl=1.0,
                        #x_target=v_step,
                        #y_target=None,
                        result_summary=result_summary,
                        filename=dataset_filename
                    )

                '''
                i) For multiphase units, step the AC test source voltage to VN.
                '''
                if grid is not None:
                    step_label = VoltVar.get_step_label()
                    ts.log('Voltage step: setting Grid simulator voltage to %s (%s)' % (v_nom, step))
                    q_initial = VoltVar.get_initial_value(daq=daq, step=step_label)
                    grid.voltage(v_nom)
                    lib_1547.process_data(
                        daq=daq,
                        tr=vv_response_time[vv_curve],
                        step=step_label,
                        initial_value=q_initial,
                        curve=vv_curve,
                        pwr_lvl=1.0,
                        #x_target=v_nom,
                        #y_target=None,
                        result_summary=result_summary,
                        filename=dataset_filename
                    )

                """
                j) For multiphase units, step the AC test source voltage to Case B from Table 24.
                """
                if grid is not None:
                    step_label = VoltVar.get_step_label()
                    ts.log('Voltage step: setting Grid simulator to case B (IEEE 1547.1-Table 24)(%s)' % step)
                    q_initial = VoltVar.get_initial_value(daq=daq, step=step)
                    lib_1547.set_grid_asymmetric(grid=grid, case='case_b')
                    lib_1547.process_data(
                        daq=daq,
                        tr=vv_response_time[vv_curve],
                        step=step_label,
                        initial_value=q_initial,
                        curve=vv_curve,
                        pwr_lvl=1.0,
                        #x_target=v_nom,
                        #y_target=None,
                        result_summary=result_summary,
                        filename=dataset_filename
                    )
                """
                k) For multiphase units, step the AC test source voltage to VN
                """
                if grid is not None:
                    step_label = VoltVar.get_step_label()
                    ts.log('Voltage step: setting Grid simulator voltage to %s (%s)' % (v_nom, step))
                    q_initial = VoltVar.get_initial_value(daq=daq, step=step)
                    grid.voltage(v_nom)
                    lib_1547.process_data(
                        daq=daq,
                        tr=vv_response_time[vv_curve],
                        step=step_label,
                        initial_value=q_initial,
                        curve=vv_curve,
                        pwr_lvl=1.0,
                        #x_target=v_nom,
                        #y_target=None,
                        result_summary=result_summary,
                        filename=dataset_filename
                    )

                ts.log('Sampling complete')
                dataset_filename = dataset_filename + ".csv"
                daq.data_capture(False)
                ds = daq.data_capture_dataset()
                ts.log('Saving file: %s' % dataset_filename)
                ds.to_csv(ts.result_file_path(dataset_filename))
                result_params['plot.title'] = dataset_filename.split('.csv')[0]
                ts.result_file(dataset_filename, params=result_params)
                result = script.RESULT_COMPLETE

    except script.ScriptFail as e:
        reason = str(e)
        if reason:
            ts.log_error(reason)


    except Exception as e:

        if dataset_filename is not None:
            dataset_filename = dataset_filename + ".csv"
            daq.data_capture(False)
            ds = daq.data_capture_dataset()
            ts.log('Saving file: %s' % dataset_filename)
            ds.to_csv(ts.result_file_path(dataset_filename))
            result_params['plot.title'] = dataset_filename.split('.csv')[0]
            ts.result_file(dataset_filename, params=result_params)

        raise

    finally:
        if daq is not None:
            daq.close()
        if pv is not None:
            if p_rated is not None:
                pv.power_set(p_rated)
            pv.close()
        if grid is not None:
            if v_nom is not None:
                grid.voltage(v_nom)
            grid.close()
        if chil is not None:
            chil.close()
        if eut is not None:
            #eut.volt_var(params={'Ena': False})
            #eut.volt_watt(params={'Ena': False})
            eut.close()
        if result_summary is not None:
            result_summary.close()

    return result

def test_run():

    result = script.RESULT_FAIL

    try:
        """
        Configuration
        """

        mode = ts.param_value('vv.mode')

        """
        Test Configuration
        """
        # list of active tests
        vv_curves = []
        vv_response_time = [0, 0, 0, 0]

        if mode == 'Vref-test':
            vv_curves['characteristic 1'] = 1
            vv_response_time[1] = ts.param_value('vv.test_1_t_r')
            irr = '100%'
            vref = '100%'
            result = volt_vars_mode_vref_test(vv_curves=vv_curves, vv_response_time=vv_response_time, pwr_lvls=pwr_lvls)

        # Section 5.14.6
        if mode == 'Imbalanced grid':
            if ts.param_value('eut.imbalance_resp') == 'EUT response to the individual phase voltages':
                imbalance_resp = ['INDIVIDUAL_PHASES_VOLTAGES']
            elif ts.param_value('eut.imbalance_resp') == 'EUT response to the average of the three-phase effective (RMS)':
                imbalance_resp = ['AVG_3PH_RMS']
            else:  # 'EUT response to the positive sequence of voltages'
                imbalance_resp = ['POSITIVE_SEQUENCE_VOLTAGES']

            vv_curves.append(1)
            vv_response_time[1] = ts.param_value('vv.test_1_t_r')

            result = volt_var_mode_imbalanced_grid(imbalance_resp=imbalance_resp,
                                                   vv_curves=vv_curves,
                                                   vv_response_time=vv_response_time )

        # Normal volt-var test (Section 5.14.4)
        else:
            irr = ts.param_value('vv.irr')
            vref = ts.param_value('vv.vref')
            v_nom = ts.param_value('eut.v_nom')
            if ts.param_value('vv.test_1') == 'Enabled':
                vv_curves.append(1)
                vv_response_time[1] = ts.param_value('vv.test_1_t_r')
            if ts.param_value('vv.test_2') == 'Enabled':
                vv_curves.append(2)
                vv_response_time[2] = ts.param_value('vv.test_2_t_r')
            if ts.param_value('vv.test_3') == 'Enabled':
                vv_curves.append(3)
                vv_response_time[3] = ts.param_value('vv.test_3_t_r')

            # List of power level for tests
            if irr == '20%':
                pwr_lvls = [0.20]
            elif irr == '66%':
                pwr_lvls = [0.66]
            elif irr == '100%':
                pwr_lvls = [1.]
            else:
                pwr_lvls = [1., 0.66, 0.20]

            if vref == '95%':
                v_ref_value = [0.95]
            elif vref == '105%':
                v_ref_value = [1.05]
            elif vref == '100%':
                v_ref_value = [1.0]
            else:
                v_ref_value = [1.0, 0.95, 1.05]

            result = volt_vars_mode(vv_curves=vv_curves, vv_response_time=vv_response_time,
                                    pwr_lvls=pwr_lvls, v_ref_value=v_ref_value)

    except script.ScriptFail as e:
        reason = str(e)
        if reason:
            ts.log_error(reason)

    finally:
        # create result workbook
        excelfile = ts.config_name() + '.xlsx'
        rslt.result_workbook(excelfile, ts.results_dir(), ts.result_dir())
        ts.result_file(excelfile)

    return result


def run(test_script):
    try:
        global ts
        ts = test_script
        rc = 0
        result = script.RESULT_COMPLETE

        ts.log_debug('')
        ts.log_debug('**************  Starting %s  **************' % (ts.config_name()))
        ts.log_debug('Script: %s %s' % (ts.name, ts.info.version))
        ts.log_active_params()

        # ts.svp_version(required='1.5.3')
        ts.svp_version(required='1.5.8')

        result = test_run()
        ts.result(result)
        if result == script.RESULT_FAIL:
            rc = 1

    except Exception as e:
        ts.log_error('Test script exception: %s' % traceback.format_exc())
        rc = 1

    sys.exit(rc)


info = script.ScriptInfo(name=os.path.basename(__file__), run=run, version='1.3.0')

# VV test parameters
info.param_group('vv', label='Test Parameters')
info.param('vv.mode', label='Volt-Var mode', default='Normal', values=['Normal', 'Vref-test', 'Imbalanced grid'])
info.param('vv.test_1', label='Characteristic 1 curve', default='Enabled', values=['Disabled', 'Enabled'],
           active='vv.mode', active_value=['Normal', 'Imbalanced grid'])
info.param('vv.test_1_t_r', label='Response time (s) for curve 1', default=10.0,
           active='vv.test_1', active_value=['Enabled'])
info.param('vv.test_2', label='Characteristic 2 curve', default='Enabled', values=['Disabled', 'Enabled'],
           active='vv.mode', active_value=['Normal'])
info.param('vv.test_2_t_r', label='Settling time min (t) for curve 2', default=1.0,
           active='vv.test_2', active_value=['Enabled'])
info.param('vv.test_3', label='Characteristic 3 curve', default='Enabled', values=['Disabled', 'Enabled'],
           active='vv.mode', active_value=['Normal'])
info.param('vv.test_3_t_r', label='Settling time max (t) for curve 3', default=90.0,
           active='vv.test_3', active_value=['Enabled'])
info.param('vv.irr', label='Power Levels iteration', default='All', values=['100%', '66%', '20%', 'All'],
           active='vv.mode', active_value=['Normal'])
info.param('vv.vref', label='Voltage reference iteration', default='All', values=['100%', '95%', '105%', 'All'],
           active='vv.mode', active_value=['Normal'])
info.param('vv.imbalance_fix', label='Use minimum fix requirements from table 24 ?',
           default='not_fix', values=['not_fix', 'fix_ang', 'fix_mag', 'std'], active='vv.mode', active_value=['Imbalanced grid'])

# EUT general parameters
info.param_group('eut', label='EUT Parameters', glob=True)
info.param('eut.phases', label='Phases', default='Single Phase', values=['Single phase', 'Split phase', 'Three phase'])
info.param('eut.s_rated', label='Apparent power rating (VA)', default=10000.0)
info.param('eut.p_rated', label='Output power rating (W)', default=8000.0)
info.param('eut.p_min', label='Minimum Power Rating(W)', default=1000.)
info.param('eut.var_rated', label='Output var rating (vars)', default=2000.0)
info.param('eut.v_nom', label='Nominal AC voltage (V)', default=120.0, desc='Nominal voltage for the AC simulator.')
info.param('eut.v_low', label='Minimum AC voltage (V)', default=116.0)
info.param('eut.v_high', label='Maximum AC voltage (V)', default=132.0)
info.param('eut.v_in_nom', label='V_in_nom: Nominal input voltage (Vdc)', default=400)
info.param('eut.f_nom', label='Nominal AC frequency (Hz)', default=60.0)
info.param('eut.f_max', label='Maximum frequency in the continuous operating region (Hz)', default=66.)
info.param('eut.f_min', label='Minimum frequency in the continuous operating region (Hz)', default=56.)
info.param('eut.imbalance_resp', label='EUT response to phase imbalance is calculated by:',
           default='EUT response to the average of the three-phase effective (RMS)',
           values=['EUT response to the individual phase voltages',
                   'EUT response to the average of the three-phase effective (RMS)',
                   'EUT response to the positive sequence of voltages'])



# Other equipment parameters
der.params(info)
gridsim.params(info)
pvsim.params(info)
das.params(info)
hil.params(info)

# Add the SIRFN logo
info.logo('sirfn.png')

def script_info():
    return info


if __name__ == "__main__":

    # stand alone invocation
    config_file = None
    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    params = None

    test_script = script.Script(info=script_info(), config_file=config_file, params=params)
    test_script.log('log it')

    run(test_script)
