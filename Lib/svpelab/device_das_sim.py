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
import random
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
        self.df = pd.read_csv(os.path.join(self.data_files_path, self.data_files_names[0].replace('\n', '')))
        self.dfs = {'TR1': pd.DataFrame, 'TR2': pd.DataFrame, 'INIT': pd.DataFrame}
        self.last_TR2 = pd.Series
        self.start_new_csv = False
        self.data_points = ['TIME']
        self.rand_factors_df = pd.DataFrame
        self.use_previous_rand_factors = params['use_previous_rand_factors']
        self.Result_folder_name = params['Result_folder_name']
        for i in list(self.df.columns):
            if 'AC' in i:
                self.data_points.append(i.strip())





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
        """
        Indicate each time the daq needs to capture new data, which means the needs to access a new csv
        :param enable: Bool which indicates if the device can capture data or not

        :return: nothing
        """
        if enable is True:
            self.test += 1
            self.new_csv_dfs()
            self.start_new_csv = True
            self.index = 0
        pass

    def generate_rand_factors_df(self):
        """
        Generate a pandas dataframe the same size as the data frame of the csv and full of random factors

        :return: a pandas dataframe with random values factors
        """
        df = self.df.copy()
        for i in list(df.columns):
            dt = []
            remove_columns = False
            for j in df.index:
                if 'AC' in i and 'INC' not in i:
                    delta = random.uniform(-0.1, 0.1)
                    dt.append(1.00 + delta)
                else:
                    remove_columns = True
            if remove_columns:
                df = df.drop(columns=i)
            else:
                df[i] = dt
        return df

    def new_csv_dfs(self):
        """
        Set the pandas Dataframes each time a new csv is accessed to produce new results.
        self.dfs['TR1'] : Dataframe that contains the values for the first Time Response
        self.dfs['TR2'] : Dataframe that contains the values for the second Time Response
        self.dfs['INIT'] : Series that contains the first initiale values of the csv file
        self.df: Dataframe of the entire csv file and then modified by self.rand_factors_df
        self.rand_factors_df : Dataframe full of random factors
        :return: nothing
        """
        self.df = pd.read_csv(os.path.join(self.data_files_path, self.data_files_names[self.test].replace('\n', '')))

        if self.use_previous_rand_factors == 'Enabled':
            self.rand_factors_df = pd.read_csv(os.path.join(os.path.join(
                os.path.join(os.path.join(self.ts._results_dir.split('Results\\')[0] + 'Results',
                                          self.Result_folder_name),
                             self.ts._result_dir),
                'Random_csv'),
                self.data_files_names[self.test].replace('\n', '')))
        else:
            self.rand_factors_df = self.generate_rand_factors_df()

        for i in list(self.rand_factors_df.columns):
            self.df[i] = self.df[i]*self.rand_factors_df[i]
        self.dfs['TR1'] = self.df[self.df[' EVENT'].str.contains("TR_1", regex=True)].drop_duplicates(subset=' EVENT',
                                                                                                      keep='last',
                                                                                                      inplace=False).reset_index(drop=True)
        self.dfs['TR2'] = self.df[self.df[' EVENT'].str.contains("TR_2", regex=True)].drop_duplicates(subset=' EVENT',
                                                                                                      keep='last',
                                                                                                      inplace=False).reset_index(drop=True)
        self.dfs['INIT'] = self.df.iloc[1]




    def get_rand_factors_df(self):
        """
        Get the dataframe full of random values

        :return: the Dataframe full of random values
        """
        return self.rand_factors_df

    def data_read(self, type=''):
        """
        Generate a pandas Series that contains the values corresponding the type of data demanded
        :param type:        string with the type of data needed ('INIT', 'TR2', 'TR1')

        :return: returns series corresponding on the type of data asked
        """
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


