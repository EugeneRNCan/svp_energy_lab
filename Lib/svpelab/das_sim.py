"""
Copyright (c) 2017, Sandia National Labs and SunSpec Alliance
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this
list of conditions and the following disclaimer.

Redistributions in binary form must reproduce the above copyright notice, this
list of conditions and the following disclaimer in the documentation and/or
other materials provided with the distribution.

Neither the names of the Sandia National Labs and SunSpec Alliance nor the names of its
contributors may be used to endorse or promote products derived from
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

import os
from . import device_das_sim_random
from . import device_das_sim_csv
from . import dataset
from . import das

import pandas as pd
import numpy as np
MINIMUM_SAMPLE_PERIOD = 50

sim_info = {
    'name': os.path.splitext(os.path.basename(__file__))[0],
    'mode': 'DAS Simulation'
}

def das_info():
    return sim_info

def params(info, group_name=None):
    gname = lambda name: group_name + '.' + name
    pname = lambda name: group_name + '.' + GROUP_NAME + '.' + name
    mode = sim_info['mode']
    info.param_add_value(gname('mode'), mode)
    info.param_group(gname(GROUP_NAME), label='%s Parameters' % mode,
                     active=gname('mode'),  active_value=mode)
    info.param(pname('Sim_mode'), label='Simulation mode', default='Disabled', values=['Disabled', 'Random', 'csv'])
    # Random mode parameters
    info.param(pname('sample_interval'), label='Sample Interval (ms)', default=1000, active=pname('Sim_mode'),
               active_value='Random')
    info.param(pname('chan_1'), label='Channel 1', default='AC', values=['AC', 'DC', 'Unused'],
               active=pname('Sim_mode'), active_value='Random')
    info.param(pname('chan_1_label'), label='Channel 1 Label', default='1', active=pname('chan_1'),
               active_value=['AC', 'DC'])
    info.param(pname('chan_2'), label='Channel 2', default='Unused', values=['AC', 'DC', 'Unused'],
               active=pname('Sim_mode'), active_value='Random')
    info.param(pname('chan_2_label'), label='Channel 2 Label', default='2', active=pname('chan_2'),
               active_value=['AC', 'DC'])
    info.param(pname('chan_3'), label='Channel 3', default='Unused', values=['AC', 'DC', 'Unused'],
               active=pname('Sim_mode'), active_value='Random')
    info.param(pname('chan_3_label'), label='Channel 3 Label', default='3', active=pname('chan_3'),
               active_value=['AC', 'DC'])
    #csv mode parameters
    info.param(pname('Base_data_folder_name'), label='Base data folder name', default='Results_dir',
               active=pname('Sim_mode'), active_value=['csv'])
    info.param(pname('use_previous_rand_factors'), label='Use previous random factors', default='Disabled',
               values=['Enabled', 'Disabled'], active=pname('Sim_mode'), active_value=['csv'])
    info.param(pname('Result_folder_name'), label='Previous Results folder name', default='Results_dir',
               active=pname('use_previous_rand_factors'), active_value=['Enabled'])


GROUP_NAME = 'sim'


class DASError(Exception):
    """
    Exception to wrap all das generated exceptions.
    """
    pass


class DAS(das.DAS):
    def __init__(self, ts, group_name, points=None, sc_points=None, support_interfaces=None):
        das.DAS.__init__(self, ts, group_name, points=points, sc_points=sc_points, support_interfaces=support_interfaces)
        # create channel info for each channel from parameters
        self.params['Sim_mode'] = self._param_value('Sim_mode')
        self.params['ts'] = self.ts

        if self.params['Sim_mode'] == 'Random':
            self.params['sample_interval'] = self._param_value('sample_interval')
            channels = [None]
            for i in range(1, 8):
                chan_type = self._param_value('chan_%d' % (i))
                chan_label = self._param_value('chan_%d_label' % (i))
                chan_ratio = self._param_value('chan_%d_i_ratio' % (i))
                if chan_label == 'None':
                    chan_label = ''
                chan = {'type': chan_type, 'points': self.points.get(chan_type), 'label': chan_label, 'ratio': chan_ratio}
                channels.append(chan)

            self.params['channels'] = channels

            ts.log('In the Report :')
            ts.log('Voltage = 123')
            ts.log('Current = 12')
            ts.log('Active Power (P) = 12345')
            ts.log('Reactive Power (Q) = 11111')
            ts.log('Apparent Power (S) = 16609')
            ts.log('Frequency = 67')
            ts.log('Power Factor = 0.12')
            ts.log('unassigned = 9991 (go to device_das_sim.py to add the missing measurement type)')

            self.device = device_das_sim_random.Device(self.params)

        elif self.params['Sim_mode'] == 'csv':
            self.params['use_previous_rand_factors'] = self._param_value('use_previous_rand_factors')
            self.params['Result_folder_name'] = self._param_value('Result_folder_name')
            self.params['Base_data_folder_name'] = self._param_value('Base_data_folder_name')
            self.params['sample_interval'] = 50
            self.device = device_das_sim_csv.Device(self.params)

        else:
            raise DASError('You need to select Random as the Simulation mode')


        self.data_points = self.device.data_points
        # initialize soft channel points
        self._init_sc_points()

    def _param_value(self, name):
        return self.ts.param_value(self.group_name + '.' + GROUP_NAME + '.' + name)

    def data_capture(self, enable=True, channels=None):
        """
        Enable/disable data capture.

        If sample_interval == 0, there will be no autonomous data captures and self.data_sample should be used to add
        data points to the capture
        """
        if self.params['Sim_mode'] == 'Random':

            if self.device is not None:
                self.sample_interval = self.device.sample_interval
            if enable is True:
                if self._capture is False:
                    self._ds = dataset.Dataset(self.data_points, ts=self.ts)
                    self._ds2 = pd.DataFrame()
                    self.start_time = None
                    self._last_datarec = []
                    if self.sample_interval > 0:
                        if self.sample_interval < MINIMUM_SAMPLE_PERIOD:
                            raise DASError('Sample period too small: %s' % (self.sample_interval))
                        self._timer = self.ts.timer_start(float(self.sample_interval)/1000, self._timer_timeout,
                                                          repeating=True)
                    self._capture = True
            elif enable is False:
                if self._capture is True:
                    if self._timer is not None:
                        self.ts.timer_cancel(self._timer)
                    self._timer = None
                    self._capture = False
            self.device.data_capture(enable)

        elif self.params['Sim_mode'] == 'csv':

            if self.device is not None:
                self.sample_interval = 50
            if enable is True:
                if self._capture is False:
                    self._ds = dataset.Dataset(self.data_points, ts=self.ts)
                    self._last_datarec = []
                    if self.sample_interval > 0:
                        if self.sample_interval < MINIMUM_SAMPLE_PERIOD:
                            raise DASError('Sample period too small: %s' % (self.sample_interval))
                        self._timer = self.ts.timer_start(float(self.sample_interval)/1000, self._timer_timeout,
                                                          repeating=True)
                    self._capture = True
            elif enable is False:
                if self._capture is True:
                    if self._timer is not None:
                        self.ts.timer_cancel(self._timer)
                    self._timer = None
                    self._capture = False
            self.device.data_capture(enable)

    def data_capture_read(self):
        """
        Return the last data sample from the data capture in expanded format.
        """
        if self.params['Sim_mode'] == 'Random':
            rec = []
            if len(self._last_datarec) > 0:
                rec = self._data_expand(self._last_datarec)
            else:
                rec = self.data_read()
            return rec

        elif self.params['Sim_mode'] == 'csv':
            if self._capture is True:
                last_datarec = self.device.data_read()
                self._last_datarec = last_datarec.values.tolist()
                self._ds.append(self._last_datarec)

                if self.device.start_new_csv is True:
                    self._ds.df['data'] = last_datarec.to_frame().T
                    self._ds.df['rand_factors'] = self.device.get_rand_factors_df()
                    self.device.start_new_csv = False
                else:
                    self._ds.df['data'] = self._ds.df['data'].append(last_datarec, ignore_index=True)
            return self._data_expand(self._last_datarec)


    def data_sample(self):
        """
        Read the current data values directly from the DAS and place in the current dataset.
        """
        if self.params['Sim_mode'] == 'Random':
            if self._capture is True:
                self._last_datarec = self.device_data_read()
                if self.start_time is None:
                    self.start_time = [self.device.start_time]
                    self._ds2 = pd.DataFrame(np.column_stack(self._last_datarec[1:]), index=self.start_time,
                                             columns=self.data_points[1:])
                    self.ts.run_conn.send({'name': self.ts.name, 'phases': self.ts.param_value('eut.phases')})
                else:
                    self._ds2 = self._ds2.append(pd.Series(self._last_datarec[1:], index=self.data_points[1:],
                                                           name=self.device.current_time))
                self.ts.run_conn.send(self._ds2.tail(1))
                self._ds.append(self._last_datarec)

        elif self.params['Sim_mode'] == 'csv':
            if self._capture is True:
               self._last_datarec = None

        return self._last_datarec


if __name__ == "__main__":

    pass


