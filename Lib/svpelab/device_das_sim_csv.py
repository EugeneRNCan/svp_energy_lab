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

import os
import random
import pandas as pd
import glob


class DeviceError(Exception):
    """
    Exception to wrap all das generated exceptions.
    """
    pass


class Device(object):

    def __init__(self, params=None):
        self.params = params
        self.sample_interval = params.get('sample_interval')
        self.data_points = ['TIME']
        self.ts = params['ts']

        # Finding the standard used with the script and initiate the event suffix to find
        f = open(self.ts.env['results_dir'].split('Results')[0] + 'Scripts\\' + self.ts.name, 'r')
        lines = f.readlines()
        for line in lines:
            if 'pAus4777' in line:
                self.Time_Event_suffix = 'T_COM'
                break
            elif 'p1547' in line:
                self.Time_Event_suffix = 'TR'
                break

        self.use_rand_factors = params['use_rand_factors'] # option to have random data or not
        self.Base_data_folder_name = params['Base_data_folder_name'] # Result folder name to replicate
        self.Base_data_directory = os.path.join(self.ts._results_dir.split('Results\\')[0] + 'Results',
                                              self.Base_data_folder_name) # Result folder path to replicate

        # Find and ordering the different csv files needed
        self.data_files_name_order = []
        self.data_files_name = {}
        self.find_data_files_name()

        # Ordering variables
        self.test = -1
        self.index = 0

        # Initialisation of the first csv file into a pandas Dataframe
        self.df = pd.read_csv(os.path.join(self.Base_data_directory,
                                           self.data_files_name[self.data_files_name_order[0]].replace('\n', '')))
        self.dfs = {} # Dictionnary with the different Dataframe containing specific event related data
        self.TR_names = [] # List of the specific events
        self.start_new_csv = False # Indicator that a new csv need to be open, therefore overwrite the Dataframes
        self.rand_factors_df = pd.DataFrame # Random factor Dataframe that is applied to initial Dataframe self.df

        # Initialising the sc points for the das
        for i in list(self.df.columns):
            if 'AC' in i:
                self.data_points.append(i.strip())

        if self.Base_data_folder_name:
            self.ts.log(f'the base data folder used is {self.Base_data_folder_name}')
            pass
        else:
            raise DeviceError('No base data folder specified')

    def dfs_initialization(self, event_col_name):
        """
                Function to know how many Time-response there is to report from the csv file and therefore the
                appriopriate Dataframes.
                :param event_col_name: string that represent the name of the event column used in self.df dataframe

                :return: nothing
        """

        j = None
        self.TR_names = []
        self.dfs['INIT'] = self.df
        for i in self.df[event_col_name]:
            if self.Time_Event_suffix in i and j is None:
                j = 0
                self.TR_names.append(self.Time_Event_suffix + i.split(self.Time_Event_suffix)[-1])
                self.dfs[self.TR_names[j]] = self.df[self.df[event_col_name].str.contains(self.TR_names[j], regex=True)]
                self.dfs['INIT'] = pd.concat(
                    [self.dfs['INIT'], self.dfs[self.TR_names[j]], self.dfs[self.TR_names[j]]]).drop_duplicates(
                    keep=False)
            elif self.Time_Event_suffix in i and self.Time_Event_suffix + i.split(self.Time_Event_suffix)[-1] not in self.TR_names:
                self.TR_names.append(self.Time_Event_suffix + i.split(self.Time_Event_suffix)[-1])
                j += 1
                self.dfs[self.TR_names[j]] = self.df[self.df[event_col_name].str.contains(self.TR_names[j], regex=True)]
                self.dfs['INIT'] = pd.concat(
                    [self.dfs['INIT'], self.dfs[self.TR_names[j]], self.dfs[self.TR_names[j]]]).drop_duplicates(keep=False)





    def find_data_files_name(self):
        """
        Find the result csv files based on the Base_data_directory. Moreover, it sort the csv files based on the first
        time of the first row of the file
        :return: nothing
        """
        os.chdir(self.Base_data_directory)
        for file in glob.glob("**\*.csv", recursive= True):
            if file.endswith('.csv') and file.endswith('result_summary.csv') is False:
                f = open(os.path.join(file), 'r')
                lines = f.readlines()
                first_time = float(lines[1].split(',')[0])
                self.data_files_name_order.append(first_time)
                self.data_files_name[first_time] = file.split('/')[-1]
                f.close()
        self.data_files_name_order.sort()

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
        self.dfs[self.Time_Event_suffix] : Dataframe that contains the values of a specific time event
        self.dfs['INIT'] : Series that contains the first initial values of each step
        self.df: Dataframe of the entire csv file and then modified by self.rand_factors_df
        self.rand_factors_df : Dataframe full of random factors
        :return: nothing
        """
        self.df = pd.read_csv(os.path.join(self.Base_data_directory, self.data_files_name[self.data_files_name_order[self.test]]
                                           .replace('\n', '')))
        for i in list(self.df.columns):
            if 'AC' not in i and 'TIME' not in i and i != list(self.df.columns)[-1]:
                self.df = self.df.drop(columns=i)

        if self.use_rand_factors == 'Enabled':
            self.rand_factors_df = self.generate_rand_factors_df()
            for i in list(self.rand_factors_df.columns):
                self.df[i] = self.df[i] * self.rand_factors_df[i]
        event_col_name = list(self.df.columns)[-1]

        while self.Time_Event_suffix in self.df.iloc[0][event_col_name]:
            self.df = self.df[1:].reset_index(drop=True)

        self.dfs_initialization(event_col_name)


        for TR_names in self.TR_names:
            self.dfs[TR_names] = self.dfs[TR_names].drop_duplicates(subset=event_col_name, keep='first',
                                                          inplace=False).reset_index(drop=True)
            self.dfs[TR_names] = self.dfs[TR_names].drop(columns=event_col_name)

        self.dfs['INIT'] = self.dfs['INIT'][self.dfs['INIT'][event_col_name].str.contains("Step", regex=True)]\
            .drop_duplicates(subset=event_col_name, keep='first', inplace=False).reset_index(drop=True)

        self.dfs['INIT'] = self.dfs['INIT'].drop(columns=event_col_name)

        for key in list(self.dfs.keys()):
            if self.dfs[key].empty:
                self.dfs.pop(key)

    def get_rand_factors_df(self):
        """
        Get the dataframe full of random values

        :return: the Dataframe full of random values
        """
        return self.rand_factors_df

    def data_read(self, event):
        """
        Generate a pandas Series that contains the values corresponding the type of data demanded

        :return: returns series corresponding on the type of data asked
        """
        data = pd.Series
        if self.Time_Event_suffix in event:
            event_tr_name = self.Time_Event_suffix + event.split(self.Time_Event_suffix)[-1]
            data = self.dfs[event_tr_name].iloc[0]
            self.dfs[event_tr_name] = self.dfs[event_tr_name][1:].reset_index(drop=True)
        else:
            data = self.dfs['INIT'].iloc[0]
            self.dfs['INIT'] = self.dfs['INIT'][1:].reset_index(drop=True)

        return data




