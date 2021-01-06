# -*- coding: utf-8 -*-
"""VTP_1.10_LSTM Models for a large dataset.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1RYWQTjOmU3_P4Zr7Nd4utDTJjvokoXcM

# Developing models for full dataset
---

Overview on the configuration of all simple models

|Model name|Description| # Car|# vars|# targets|# const_vars| # steps | # futures
|---|:--|:-:|:-:|:-:|:-:|:-:|:-:|

## Import packages
"""
#%% Import packages
# For general
import matplotlib.pyplot as plt
import numpy as np
import time
from io import StringIO, BytesIO
from zipfile import ZipFile
import urllib.request
plt.rcParams['figure.figsize'] = (8, 6)
from math import sqrt
import os
# For data processing
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

# For prediction model

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.layers import LSTM
from tensorflow.keras.layers import Bidirectional
from tensorflow.keras.layers import Flatten
from tensorflow.keras.layers import TimeDistributed
from tensorflow.keras.layers import RepeatVector
from tensorflow.keras.layers import ConvLSTM2D
from tensorflow.keras.layers import MaxPool1D, Conv1D

#%% import data without saving it in local directory
def url2pd(link):
    url = urllib.request.urlopen(link)
    with ZipFile(BytesIO(url.read())) as my_zip_file:
        for contained_file in my_zip_file.namelist():
            fzip=my_zip_file.open(contained_file)
            data=fzip.read()
    s=str(data,'utf-8')
    data = StringIO(s) 
    print('Done loading data')
    return pd.read_csv(data)
#%% Load dataset
filenames = ['0750_0805_us101_smoothed_11_.zip',
             '0805_0820_us101_smoothed_11_.zip',
             '0820_0835_us101_smoothed_11_.zip',
             'trajectories-0400-0415.zip',
             'trajectories-0500-0515.zip',
             'trajectories-0515-0530.zip']
url_path = 'https://github.com/duonghung86/Vehicle-trajectory-tracking/raw/master/Data/'
url_1 = url_path + filenames[0]

df = url2pd(url_1)

#  keep only columns that are useful for now
kept_cols = ['Vehicle_ID', 'Frame_ID', 'Total_Frames', 'Local_X','Local_Y',
             'v_Length', 'v_Width', 'v_Vel', 'v_Acc', 'Lane_ID']
df = df[kept_cols]

# %%
# Filter time step
print(df.shape)
df = df.iloc[::2,:].copy()
print('After filtering:', df.shape)

vehicle_ids = df.Vehicle_ID.unique()
# Set constant values
HISTORY_LENGTH = 3
FUTURE_LENGTH = 5
n_steps = int(HISTORY_LENGTH/0.2)
n_future = int(FUTURE_LENGTH/0.2)
n_features = len(df)
series_feature_names = ['Local_X','v_Vel','Local_Y', 'v_Acc', 'Lane_ID']
target_names = ['Local_X','v_Vel']
n_labels = len(target_names)
LSTM_names = ['Vanilla LSTM',
              'Stacked LSTM',
              'Bidirectional',
              'CNN LSTM',
              'Conv LSTM',
              'Encoder-Decoder LSTM']

print('the number of vehicles is {}'.format(len(vehicle_ids)))

#%% function that turns series to sequences

""" `series2seq`: 
    Function that return sequence input and output for one object

**Arguments**:
- data: Sequence of observations as a Pandas dataframe.
- n_in: Number of lag observations as input (X).
- n_out: Number of observations as output (y).
- series_features: names of series features
- labels: names of target variables
- dropnan: Boolean whether or not to drop rows with NaN values.
    
**Returns**:
- X: Feature Pandas DataFrame
- y: Label Pandas dataframe
"""
def series2seq(data, n_in, n_out,labels,series_features, show_result=False):
    
    dat = data.copy()
    cols, names = list(), list()
    
    # input sequence (t-n, ... t-1)
    for i in range(n_in, 0, -1):
        cols.append(dat[series_features].shift(i))
        names += ['{}(t-{})'.format(j, i) for j in series_features]
    
    # forecast sequence (t, t+1, ... t+n) for selected labels
    for i in range(0, n_out):
        cols.append(dat[labels].shift(-i))
        names += ['{}(t+{})'.format(j, i) for j in labels]
        
    # put it all together
    agg = pd.concat(cols, axis=1).dropna()
    agg.columns = names
    # concatenate with constant features

    X = agg.iloc[:,:len(series_features)*n_in].copy()
    X = pd.concat([X,dat.drop(columns=series_features)], axis=1).dropna()
    y = agg.iloc[:,len(series_features)*n_in:].copy()
    
    # Show some information on the data sets X and y
    if show_result:
      X.info()
      print(X.head(), X.shape)
      y.info()
      print(y.head(), y.shape)
    return X, y
  
# Test the function
# X, y = series2seq(df[df.Vehicle_ID==vehicle_ids[0]], 
#                   n_in=2, n_out=1,labels = target_names,
#                   series_features=series_feature_names, 
#                   show_result=True)

"""### `treatment_cars` Function to prepare the data set for multiple cars
"""
#%% function that prepare sequence for multi object

def treatment_cars(data, n_in, n_out,labels,series_features, show_result=False):
  veh_ids = data.Vehicle_ID.unique()
  dat_X, dat_y = pd.DataFrame(),pd.DataFrame()

  for id in veh_ids:
    dat = data[data.Vehicle_ID==id].copy()
    X, y = series2seq(dat.drop(columns=['Frame_ID']), n_in=n_in, n_out=n_out,labels = labels,series_features=series_features)
    dat_X = pd.concat([dat_X,X],ignore_index=True)
    dat_y = pd.concat([dat_y,y],ignore_index=True)
  if show_result:
    dat_X.info()
    print(dat_X.head(), dat_X.shape)
    dat_y.info()
    print(dat_y.head(), dat_y.shape)
  return dat_X ,dat_y

# Test the function
# treatment_cars(df[df.Vehicle_ID.isin(vehicle_ids[:4])],
#                n_in=2, n_out=1, labels = target_names,
#                series_features=series_feature_names, show_result=True)

#%% Function to create simple LSTM models
def create_model(LSTM_name,train):
    # Create a new model

    model = Sequential()
      
    if LSTM_name == LSTM_names[0]:    
      model.add(LSTM(50, activation='tanh', input_shape=(train.shape[1],1)))
      model.add(Dense(n_labels*n_future))
      
    elif LSTM_name == LSTM_names[1]:
      # Stacked LSTM
      model.add(LSTM(50, activation='relu', return_sequences=True, input_shape=(train.shape[1],1)))
      model.add(LSTM(50, activation='relu'))
      model.add(Dense(n_labels*n_future))
    
    elif LSTM_name == LSTM_names[2]:
      # Bidirectional
      model.add(Bidirectional(LSTM(50, activation='relu'), input_shape=(train.shape[1],1)))
      model.add(Dense(n_labels*n_future))
      
    elif LSTM_name == LSTM_names[3]:
      # CNN LSTM
      model.add(TimeDistributed(Conv1D(filters=64, kernel_size=1, activation='relu'), input_shape=(None, 4,1)))
      model.add(TimeDistributed(MaxPool1D(pool_size=2)))
      model.add(TimeDistributed(Flatten()))
      model.add(LSTM(50, activation='relu'))
      model.add(Dense(n_labels*n_future))
      
    elif LSTM_name == LSTM_names[4]:
      # Conv LSTM
      model.add(ConvLSTM2D(filters=64, kernel_size=(1,2), activation='relu', input_shape=(3, 1, 4,1)))
      model.add(Flatten())
      model.add(Dense(n_labels*n_future))
      
    elif LSTM_name == LSTM_names[5]:
      # Encoder-Decoder LSTM.
      model.add(LSTM(50, activation='relu', input_shape=(train.shape[1],1)))
      model.add(RepeatVector(n_labels*n_future))
      model.add(LSTM(50, activation='relu', return_sequences=True))
      model.add(TimeDistributed(Dense(1)))
      
    # compile the model
    model.compile(optimizer='adam', loss='mse', metrics=['mse'])
    return model
#%% LSTM traning - main program
def lstm_training(cars=5,standard=False, model_name=LSTM_names[0]):
    np.random.seed(23)
    veh_list = np.random.choice(vehicle_ids,cars)
    sub_df = df[df.Vehicle_ID.isin(veh_list)].copy()
    


    """## Data preparation"""
    
    # turn the data set into sequences
    X, y = treatment_cars(sub_df, 
                          n_in=n_steps, n_out=n_future,
                          labels = target_names,
                          series_features=series_feature_names, show_result=True)

    # Split the data set
    X_train, X_test, y_train, y_test = train_test_split(X,y, 
                                                    test_size=0.3, random_state=42)
    #print(X_train.shape,X_test.shape, y_train.shape, y_test.shape)
    #X_train.describe()

    ### Standardize the data
    if standard:        
        train_mean = X_train.mean()
        train_std = X_train.std()
        
        X_train = (X_train - train_mean) / train_std
        X_test = (X_test - train_mean) / train_std


    """### Reshape data sets to match the selected model"""

    X_train = X_train.values
    X_test = X_test.values
    # reshape into [# samples, # timesteps,# features]
    X_train = X_train.reshape((X_train.shape[0], X_train.shape[1],1))
    X_test = X_test.reshape((X_test.shape[0], X_test.shape[1],1))
    
    
    """## Prediction model"""
  
    tf.random.set_seed(24)
    # create model
    #mirrored_strategy = tf.distribute.MirroredStrategy()

    #with mirrored_strategy.scope():
    model = create_model(LSTM_names[0],X_train)
    # Interrupt training if `val_loss` stops improving for over 10 epochs
    stop_learn= tf.keras.callbacks.EarlyStopping(patience=10, monitor='val_loss')
    #print(model.summary())
    
    # fit model
    start = time.time()
    model.fit(X_train,y_train, epochs=5, 
                        callbacks=[stop_learn],
                        validation_data=(X_test,y_test), verbose=1)
    end = time.time()

    # Evaluation

    yhat = model.predict(X_test, verbose=1)
    rms = sqrt(mean_squared_error(y_test, yhat))
    #print(yhat[:5])
    
    return [rms, end-start]
result = lstm_training()
print("The RMSE is {0:.3f} and the model was trained within {1:.3f} sec".format(result[0],result[1]))
#%%
"""# Various models (3 → 7)"""

# LSTM_names = ['Vanilla LSTM',
#               'Stacked LSTM',
#               'Bidirectional',
#               'CNN LSTM',
#               'Conv LSTM',
#               'Encoder-Decoder LSTM']


# """## Prediction model"""

# # for model ConvLSTM
# X_train = X_train.reshape((X_train.shape[0],3,1,4,1))
# X_test = X_test.reshape((X_test.shape[0],3,1,4,1))
# X_train.shape
# # = X.reshape((X.shape[0], n_seq, n_steps, n_features))

# X_train.shape

# # for model E-D LSTM
# X_train = X_train.reshape((X_train.shape[0], X_train.shape[1],1))
# X_test = X_test.reshape((X_test.shape[0], X_train.shape[1],1))
# X_train.shape

# y_train = y_train.reshape((y_train.shape[0], y_train.shape[1]))
# y_test = y_test.reshape((y_test.shape[0], y_train.shape[1]))
# y_train.shape

# model.summary()


# # # create model
# # model = create_model(LSTM_names[5])
# # 
# # # fit model
# # Monitor = model.fit(X_train, y_train, epochs=50, 
# #                     callbacks=[stop_learn],
# #                     validation_data=(X_test, y_test), verbose=1)
# # # Check training process
# # hist = pd.DataFrame(Monitor.history)
# # hist['epoch'] = Monitor.epoch
# # fig, axes = plt.subplots(nrows=1, ncols=2,figsize=(10,4),dpi=150)
# # hist[['loss','val_loss']].plot(ax=axes[0])
# # hist[['mse','val_mse']].plot(ax=axes[1])
# # plt.show()
# # hist.tail()

# """## Evaluation"""

# yhat.shape

# yhat = model.predict(X_test, verbose=1)

# yhat = yhat.reshape((yhat.shape[0], yhat.shape[1]))
# rms += [sqrt(mean_squared_error(y_test, yhat))]
# print(yhat[:5])
# rms



"""#END"""