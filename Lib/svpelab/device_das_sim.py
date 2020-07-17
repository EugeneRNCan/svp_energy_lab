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
import time
import pandas as pd


class DeviceError(Exception):
    """
    Exception to wrap all das generated exceptions.
    """
    pass


class Device(object):

    def __init__(self, params=None):
        self.ts = params['ts']
        self.points = params['points']
        self.sample_interval = params.get('sample_interval')
        self.data_points = []
        self.data_files_path = params['data_files_path']
        f = open(os.path.join(self.data_files_path, 'CSV_ORDER_NAMES.txt'), 'r')
        self.data_files_names = f.readlines()
        self.use_timestamp = params['use_timestamp']
        self.test = -1
        self.index = 0
        self.df = pd.DataFrame
        self.dfs = {'TR1': pd.DataFrame, 'TR2': pd.DataFrame, 'INIT': pd.DataFrame}
        self.last_TR2 = pd.Series
        self.start_new_csv = False

        if self.data_files_path:
            pass
            # for i in self.ds.points:
            #     if 'AC' in i:
            #         self.data_points.append(i)
        else:
            raise DeviceError('No data file specified')

    def info(self):
        return 'DAS Simulator - 1.0'

    def open(self):
        pass

    def close(self):
        pass

    def data_capture(self, enable=True):
        if enable is True:
            self.test += 1
            self.new_csv_dfs()
            self.start_new_csv = True
            self.index = 0
        pass

    def new_csv_dfs(self):
        self.df = pd.read_csv(os.path.join(self.data_files_path, self.data_files_names[self.test].replace('\n', '')))
        self.dfs['TR1'] = self.df[self.df[' EVENT'].str.contains("TR_1", regex=True)].drop_duplicates(subset=' EVENT',
                                                                                                keep='last',
                                                                                                inplace=False).reset_index(drop=True)
        self.dfs['TR2'] = self.df[self.df[' EVENT'].str.contains("TR_2", regex=True)].drop_duplicates(subset=' EVENT',
                                                                                                keep='last',
                                                                                                inplace=False).reset_index(drop=True)
        self.dfs['INIT'] = self.df.iloc[1]
    def data_read(self, type=''):
        data = pd.Series
        if type == 'init':
            if self.start_new_csv is True:
                data = self.dfs['INIT']
            else:
                data = self.last_TR2
        elif type == 'TR2':
            data = self.dfs['TR2'].iloc[self.index]
            self.index += 1
            self.last_TR2 = data
        elif type == 'TR1':
            data = self.dfs['TR1'].iloc[self.index]
        # total = len(self.ds.points)
        # data = []
        # #while self.index != len(self.ds.data) - 1:
        # if self.data_lenght == 0:
        #     for i in self.ds.points:
        #         if 'AC' not in i and 'TIME' not in i:
        #             total -= 1
        #     self.data_lenght = total
        # j = 0
        # while j != self.data_lenght - 1:
        #     data.append(self.ds.data[self.index][j])
        #     j += 1
        # self.index += 1
        # if self.index == len(self.ds.data):
        #     self.test += 1
        return data

    def waveform_config(self, params):
        pass

    def waveform_capture(self, enable=True, sleep=None):
        """
        Enable/disable waveform capture.
        """
        pass

    def waveform_status(self):
        # mm-dd-yyyy hh_mm_ss waveform trigger.txt
        # mm-dd-yyyy hh_mm_ss.wfm
        # return INACTIVE, ACTIVE, COMPLETE
        return 'COMPLETE'

    def waveform_force_trigger(self):
        pass

    def waveform_capture_dataset(self):
        return self.ds

if __name__ == "__main__":

    pass


