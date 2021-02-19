# -*- coding: utf-8 -*-
"""VAE_v1_1.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/github/nina-prog/DataAnalysis_VAE/blob/main/VAE_v2.0.ipynb
"""
from typing import Any, Union

import numpy as np
import pandas as pd
from pandas import Series, DataFrame
from pandas.io.parsers import TextFileReader

pd.options.mode.chained_assignment = None  # default='warn'

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
from tensorflow.keras.layers import LSTM, Dense, TimeDistributed, Bidirectional, Dropout, Reshape, Flatten
# from tensorflow.keras.visualize_util import plot_model
from tensorflow.keras.regularizers import l2
from tensorflow.keras.optimizers import SGD, Adam
from tensorflow.keras.wrappers.scikit_learn import KerasRegressor

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import RandomizedSearchCV
from sklearn.metrics import make_scorer

import matplotlib.pyplot as plt
import seaborn as sns
import pickle

### set plot design
sns.set()
sns.set_palette(sns.color_palette("Set1"))  # tab10 #viridis
# sns.set_style("whitegrid")
sns.set_context("paper")

### set seed
tf.random.set_seed(7)

"""# Data Preprocessing

---

## Load Data
"""

### Load ecg5000 data using read_csv
ecg5000 = pd.read_csv(r'C:\Users\merti\git\DataAnalysis_VAE\ECG5000\ECG5000_ALL.txt', sep='\s+', header=None)

### Optional test and info about data set
print("Type of ecg5000: \t \t {}".format(type(ecg5000)))
print("Dimensions of ecg5000: \t \t {}".format(ecg5000.shape))
print("Number of elements of ecg5000: \t {}".format(ecg5000.size))
print("Display first 10 rows of ecg5000: \n {}".format(ecg5000.head(10)))

# ### Normalize dataframe with min-max-normalization to range between [-0.8, 0.8] using sklearn MinMaxScaler
# min_max_scaler = MinMaxScaler(feature_range=(-0.8,0.8))
# scaled_ecg5000 = pd.DataFrame(min_max_scaler.fit_transform(ecg5000))
# print(scaled_ecg5000)

"""## Split Data"""

### Split Data into 80/20 Training, Test
trainDF, testDF = train_test_split(ecg5000, test_size=0.2, shuffle=True, random_state=1)

# get all labels from trainDF and then drop it
trainDF_Y = trainDF.iloc[:, 0]
trainDF.drop(trainDF.columns[[0]], axis=1, inplace=True)

# get all labels from testDF and then drop it
testDF_Y = testDF.iloc[:, 0]
testDF.drop(testDF.columns[[0]], axis=1, inplace=True)

# optional test and info about new data sets
print("Shape of Train DataFrame: \t {}".format(trainDF.shape))
print("Shape of Test DataFrame: \t {}".format(testDF.shape))
print("Shape of Train Y DataFrame: \t {}".format(trainDF_Y.shape))
print("Shape of Test Y DataFrame: \t {}".format(testDF_Y.shape))

"""## Reshape Data"""

### Convert to array
x_train = trainDF.to_numpy()
x_test = testDF.to_numpy()

y_train = trainDF_Y.to_numpy()
y_test = testDF_Y.to_numpy()

### Reshape datasets X/Y train/test into [samples, time steps, features]
s_x_train = len(trainDF.index)  # samples
n_x_train = len(trainDF.columns)  # time steps

s_x_test = len(testDF.index)  # samples
n_x_test = len(testDF.columns)  # time steps

s_y_train = len(trainDF_Y.index)  # samples

s_y_test = len(testDF_Y.index)  # samples

x_train = x_train.reshape(s_x_train, n_x_train, 1)
x_test = x_test.reshape(s_x_test, n_x_test, 1)

y_train = y_train.reshape(s_y_train, 1, 1)
y_test = y_test.reshape(s_y_test, 1, 1)

### Properties
print("Shape of x_train: {}".format(x_train.shape))
print("Shape of x_test: {}".format(x_test.shape))

print("Shape of y_train: {}".format(y_train.shape))
print("Shape of y_test: {}".format(y_test.shape))

"""# Sampling

---


"""


class Sampling(layers.Layer):
    """Uses (z_mean, z_log_var) to sample z"""

    def call(self, inputs, **kwargs):
        z_mean, z_log_var = inputs
        batch = tf.shape(z_mean)[0]
        dim = tf.shape(z_mean)[1]
        epsilon = tf.keras.backend.random_normal(shape=(batch, dim))
        return z_mean + tf.exp(0.5 * z_log_var) * epsilon


"""# Build Variational Autoencoder (VAE)

---

## Encoder
"""


def create_encoder(intermediate_dim=140, latent_dim=5, dropout_rate=0.2, regularizer_rate=0.004):
    """Maps ECG5000 time series to a triplet (z_mean, z_log_var, z)."""

    ### Define Layers
    encoder_inputs = keras.Input(shape=(140, 1), name='Encoder_Input_layer')

    encoded = Bidirectional(LSTM(intermediate_dim, activation='tanh', name=''), name='Encode_1')(encoder_inputs)
    # encoded = Flatten()(encoded), LSTM return_sequence=True
    encoded = Dropout(dropout_rate, name='Dropout_1')(encoded)
    encoded = Dense(latent_dim, activation='tanh', name='Encode_2', kernel_regularizer=l2(regularizer_rate),
                    activity_regularizer=l2(regularizer_rate))(encoded)

    z_mean = Dense(latent_dim, activation='softplus', name="z_mean")(encoded)
    z_log_var = Dense(latent_dim, activation='softplus', name="z_log_var")(encoded)
    z = Sampling(name='Sample_layer')([z_mean, z_log_var])

    ### Instantiate encoder
    encoder = keras.Model(encoder_inputs, [z_mean, z_log_var, z], name="encoder")

    return encoder


# ### Check if encoder works
# encoder_test = create_encoder()
# encoder_test.summary()

"""## Decoder"""


def create_decoder(encoding_dim=140, intermediate_dim=140, latent_dim=5, dropout_rate=0.2,
                   regularizer_rate=0.004):
    """Converts z, the encoded time series, back into a readable time series."""

    ### Define Layers
    latent_inputs = keras.Input(shape=(latent_dim,), name='Decoder_Input_layer')

    decoded = Dense(encoding_dim * 256, activation='tanh', name='Decode_1', kernel_regularizer=l2(regularizer_rate),
                    activity_regularizer=l2(regularizer_rate))(latent_inputs)
    decoded = Reshape((140, 256), name='Decode_2')(decoded)
    decoded = Dropout(dropout_rate, name='Dropout_1')(decoded)
    decoded = Bidirectional(LSTM(intermediate_dim, activation='tanh', return_sequences=True, name=''), name='Decode_3')(
        decoded)

    decoder_outputs = TimeDistributed(Dense(1, activation='linear', name=''), name='Decoder_Output_Layer')(decoded)

    ### Instantiate decoder
    decoder = keras.Model(latent_inputs, decoder_outputs, name="decoder")

    return decoder


# ### Check if decoder works
# decoder_test = create_decoder()
# decoder_test.summary()

"""## VAE

### Define VAE Model
"""


class VAE(keras.Model):
    """Combines the encoder and decoder into an end-to-end model for training."""

    def __init__(self, encoder, decoder, **kwargs):
        super(VAE, self).__init__(**kwargs)
        self.encoder = encoder
        self.decoder = decoder

    def train_step(self, data):
        # unpack the data
        if isinstance(data, tuple):
            data = data[0]
        with tf.GradientTape() as tape:
            # forward pass
            z_mean, z_log_var, z = self.encoder(data)
            reconstruction = self.decoder(z)
            # Compute own loss
            reconstruction_loss = tf.reduce_mean(
                keras.losses.mean_squared_error(data, reconstruction) * 140
            )
            kl_loss = 1 + z_log_var - tf.square(z_mean) - tf.exp(z_log_var)
            kl_loss = tf.reduce_mean(kl_loss)
            kl_loss *= -0.5
            total_loss = reconstruction_loss + kl_loss
        # compute gradients
        grads = tape.gradient(total_loss, self.trainable_weights)
        # update weights
        self.optimizer.apply_gradients(zip(grads, self.trainable_weights))
        # compute own metrics
        return {
            "loss": total_loss,
            "reconstruction_loss": reconstruction_loss,
            "kl_loss": kl_loss,
        }

    def test_step(self, data):
        # unpack the data
        x, y = data
        # compute predictions
        y_pred = self(x, training=False)
        # updates the metrics tracking the loss
        self.compiled_loss(y, y_pred, regularization_losses=self.losses)
        # update the metrics
        self.compiled_metrics.update_state(y, y_pred)
        # return a dict mapping metric names to current value
        return {m.name: m.result() for m in self.metrics}

    def call(self, data, **kwargs):
        z_mean, z_log_var, z = self.encoder(data)
        reconstructed = self.decoder(z)
        return reconstructed


"""### Build VAE connecting Encoder and Decoder"""


### Define function to create model
def create_model(intermediate_dim=140, dropout_rate=0.2, regularizer_rate=0.004, optimizer='adam', learn_rate=0.001,
                 name='VAE'):
    """Creates VAE model, required for wrapping in estimator interface KerasRegressor, while accepting the hyperparameters we want to tune. We also pass some default values."""

    # create encoder 
    encoder = create_encoder(intermediate_dim=intermediate_dim, dropout_rate=dropout_rate,
                             regularizer_rate=regularizer_rate)
    # create decoder 
    decoder = create_decoder(intermediate_dim=intermediate_dim, dropout_rate=dropout_rate,
                             regularizer_rate=regularizer_rate)
    # create vae
    model = VAE(encoder, decoder, name=name)
    # compile model
    if optimizer == 'adam':
        opt = Adam(lr=learn_rate, amsgrad=True)
    else:
        opt = SGD(lr=learn_rate)
    model.compile(optimizer=opt)
    model.build((None, 140, 1))

    return model


### Instantiate VAE model
vae = create_model(name='VAE')

### Display VAE model and it`s parts
# encoder 
vae.encoder.summary(line_length=100)
# plot_model(vae.encoder, show_shapes=True, to_file='vae_encoder.png')
print("\n")
# decoder
vae.decoder.summary(line_length=100)
# plot_model(vae.decoder, show_shapes=True, to_file='vae_decoder.png')
print("\n")
# vae
vae.summary(line_length=100)

"""# Train VAE

---


"""

### Train Properties
epochs = 100  # 50, 100
batch_size = 16  # 16, 32

"""## Train"""

### Train
train_history = vae.fit(x_train, x_train, epochs=epochs, batch_size=batch_size, validation_data=(x_test, x_test))

### Save history
with open('/trainHistoryDict', 'wb') as file_pi:
    pickle.dump(train_history.history, file_pi)

### Check displayed values in the command line with actual output values of the trainings process
print("----- loss: -----\n{}".format(train_history.history["loss"]))
print("----- reconstruction_loss: -----\n{}".format(train_history.history["reconstruction_loss"]))
print("----- kl_loss: -----\n{}".format(train_history.history["kl_loss"]))
print("----- val_loss: -----\n{}".format(train_history.history["val_loss"]))

"""## Recreate"""

# Encoder output is a list [z_mean, z_log_var, z] thus list[2] = z, see subsection encoder line 12

### Extract myu i.e. z_mean
z_mean = vae.encoder.predict(x_test)[0]
print("----- z_mean: -----")
print(z_mean)
print("\n")

### Extract sigma i.e. z_log_var
z_log_var = vae.encoder.predict(x_test)[1]
print("----- z_log_var: -----")
print(z_log_var)
print("\n")

### Extract z_values and predict x_test
z_values = vae.encoder.predict(x_test)[2]
decoded_ecg5000 = vae.decoder.predict(z_values)
# z_values contains list of each z_value per sample, i.e. we get 1000 SubLists with 5 elements in each.
# Those 5 elements (z_values for Sample i) is our bottleneck which the decoder receives.
print("----- z_values: -----")
print(z_values)
print("\n")

### Save extracted values
np.savetxt(r'C:\Users\merti\git\DataAnalysis_VAE\figures\z_values.csv', z_values, delimiter=",")
np.savetxt('decoded_ecg5000.csv', decoded_ecg5000.reshape(-1, 140), delimiter=",")

### Properties
print("Shape and Type of z_mean: {}, {}".format(z_mean.shape, type(z_mean)))
print("Shape and Type of z_log_var: {}, {}".format(z_log_var.shape, type(z_log_var)))
print("Shape and Type of z_values: {}, {}".format(z_values.shape, type(z_values)))
print("Shape and Type of decoded_ecg5000: {}, {}".format(decoded_ecg5000.shape, type(decoded_ecg5000)))

"""## Display the training progress

#### Loss
"""

### Loss vs Reconstruction_loss vs KL Divergence
plt.figure(figsize=(8, 5))
plt.plot(train_history.history['loss'])
plt.plot(train_history.history['reconstruction_loss'])
plt.plot(train_history.history['kl_loss'])
plt.legend(["Loss", "Reconstruction Loss", "KL Divergence"])
plt.xlabel("Epoch")
plt.title("Loss vs. Reconstruction Loss vs. KL Divergence")

plt.savefig('loss.png')

### Train loss vs val loss
# returns the loss value & metrics values for the model in test mode
plt.figure(figsize=(8, 5))
plt.plot(train_history.history['loss'])
plt.plot(train_history.history['val_loss'])
plt.legend(["Loss", "Validation Loss"])
plt.xlabel("Epoch")
plt.title("Loss vs. Validation Loss")

plt.savefig('valLoss.png')

"""### Latent Space"""

### Scale Data (PCA)
# transform to dataframe
z_test = pd.DataFrame(z_values)
# standardize the data
z_test = StandardScaler().fit_transform(z_test)

### Estimate how many components are needed to describe the data (PCA)
pca_explained = PCA().fit(z_test)
plt.plot(np.cumsum(pca_explained.explained_variance_ratio_))
plt.xlabel('number of components')
plt.ylabel('cumulative explained variance')

### PCA (5 dim -> 2 dim): display a 2D plot of the classes in the latent space.
# make PCA instance
pca = PCA(n_components=2)
# fit transform features
principalComponents = pca.fit_transform(z_test)
# build pca dataframe
principalDf = pd.DataFrame(data=principalComponents, columns=['principal component 1', 'principal component 2'])
targetDF = pd.DataFrame(data=testDF_Y.to_numpy(), columns=['target'])
finalDF = pd.concat([principalDf, targetDF], axis=1)
# scatterplot
plt.figure(figsize=(8, 5))
plt.xlabel('Principal Component 1')
plt.ylabel('Principal Component 2')
plt.title('Principal Component Analysis of Latent Space')
plt.scatter(finalDF['principal component 1'], finalDF['principal component 2'], c=finalDF['target'],
            cmap=plt.cm.get_cmap('Set1', 6), s=40, alpha=0.7)  # or cmap=hsv
plt.colorbar(ticks=range(6), label='Classes of ECG500')
plt.clim(-0.5, 5.5)

plt.show()
plt.savefig('PCA.png')

"""# Plot Data Results

---


"""

### Test if Input fits Dim of Output
print("Shape of x_train: {}".format(x_train.shape))
print("Shape of decoded_ecg5000: {}".format(decoded_ecg5000.shape))

### Covert to 2D Array ("-1" = make a dimension (here rows) the size that will use the remaining unspecified elements)
new_x_train = x_train.reshape(-1, 140)
new_decoded_ecg5000 = decoded_ecg5000.reshape(-1, 140)

print("Shape of Input after reshaping: {}".format(new_x_train.shape))
print("Shape of Output after reshaping: {}".format(new_decoded_ecg5000.shape))

# ### Plot figure for paper
# i = 934 # sample which is going to be plotted
# plt.figure(linewidth = 1, figsize=(25,6))
# plt.xlabel('time steps')
# plt.plot(new_x_train[i])
# plt.show()
# plt.savefig('diagramm_original.jpg')

# plt.figure(linewidth = 1, figsize=(25,6))
# plt.xlabel('time steps')
# plt.plot(new_decoded_ecg5000[i], label='decoded ecg5000')
# plt.show()
# plt.savefig('diagramm_decoded.jpg')

### Plot only one sample
i = 901  # sample which is going to be plotted
plt.figure(linewidth=1, figsize=(20, 6))
plt.title('Autoencoder Result')
plt.xlabel('time steps')
plt.plot(new_decoded_ecg5000[i], label='decoded ecg5000')
plt.plot(new_x_train[i], label='original ecg5000')
plt.legend(loc="upper left")
plt.show()

### Plot Multiple Samples
n_rows = 2
n_cols = 3

# size properties and layout design for tighter representation
fig, axs = plt.subplots(nrows=n_rows, ncols=n_cols, figsize=(13, 6))
fig.tight_layout(w_pad=4, h_pad=5)

# subplotting
i = 50
for row in range(n_rows):
    for col in range(n_cols):
        axs[row, col].plot(new_decoded_ecg5000[i])
        axs[row, col].plot(new_x_train[i])
        axs[row, col].legend(["Decoded ECG5000 Sample {}".format(i), "Original ECG5000 Sample {}".format(i)])
        axs[row, col].set(xlabel="Time Steps", ylabel="Heartbeat Interpolated", title="Sample {}".format(i))
        i = i + 75

plt.savefig('dataComparison.png')

"""# Optimization

---

## Hyperparameter (Sckit_GridSearchCV)
"""


### Define scorer
def score_mse(y_true, y_pred):
    """Implementing mean squared error as a score for RandomizedSearchCV."""

    y_pred = tf.convert_to_tensor(y_pred)
    y_true = tf.cast(y_true, y_pred.dtype)
    # removing all size 1 dimensions in y_true
    y_true = tf.squeeze(y_true)
    return np.mean(tf.math.squared_difference(y_pred, y_true))


### Define Function for Randomized Search
def randomizedSearch_pipeline(x_train_data, x_test_data, model, space, n_iter=10, scoring_fit='neg_mean_squared_error',
                              cv=5, do_probabilities=False):
    """Pipeline for RandomizedSearchCV: Select settings and run randomizedSearchCV, returning results."""
    # define randomizedSearch
    rs = RandomizedSearchCV(
        estimator=model,
        param_distributions=space,
        n_iter=n_iter,
        scoring=scoring_fit,
        n_jobs=1,
        cv=cv,
        verbose=2,
        random_state=1,
    )
    # fit model
    fitted_model = rs.fit(x_train_data, x_train_data, verbose=0)
    # get results
    rs_result = pd.DataFrame(rs.cv_results_)
    # save compromised version of the results
    min_rs_results = pd.concat([pd.DataFrame(rs.cv_results_["mean_test_score"], columns=["score"]),
                                pd.DataFrame(rs.cv_results_["params"])], axis=1)
    min_rs_results = min_rs_results.sort_values(by="score", ascending=False)
    min_rs_results.to_latex(buf='randomizedSearchResults.tex', caption=(
        "Results of 20 candidates using a cross-validation of 5", "Randomized Search Results"), label='table:1')

    if do_probabilities:
        pred = fitted_model.predict_proba(x_test_data)
    else:
        pred = fitted_model.predict(x_test_data)

    return fitted_model, pred, rs_result, min_rs_results


### Define evaluated params and it's value range
space = {
    'optimizer': ['adam', 'SGD'],
    'batch_size': list(np.logspace(0, 6, 7, base=2, dtype=int)),
    'dropout_rate': list(np.linspace(0, 1)),
    'regularizer_rate': list(np.logspace(-6, -1, 6)),
    'learn_rate': list(np.logspace(np.log10(0.005), np.log10(0.5), base=10, num=100)),
}

### Wrap keras custom VAE model with the KerasClassifier thus it implements estimator interface
model = KerasRegressor(build_fn=create_model)

### Run RandomizedSearch
fitted_model, pred, rs_result, min_rs_results = randomizedSearch_pipeline(x_train, x_test, model, space, n_iter=4,
                                                                          scoring_fit=make_scorer(score_mse,
                                                                                                  greater_is_better=False))

### Summarize results
print("----- Results RandomizedSearchCV: -----\n" + "Best: {} using {}\n".format(fitted_model.best_score_,
                                                                                 fitted_model.best_params_))
# pd.set_option("display.max_rows", None, "display.max_columns", None)
# pd.reset_option('all')
print("Summary:\n {}".format(rs_result))

"""## Dropout"""

# ###Dropout_rate

# # configure the experiment
# def experiment_dropout():
#   # configure the experiment
#   n_dropout = [0.0, 0.2, 0.4, 0.6, 0.8]
#   # run the experiment
#   results = []
#   for drop_value in n_dropout:
#       # set dropout
#       drop_out_rate = drop_value
#       print("----- Dropout Rate: {} -----".format(drop_out_rate))
#       # evaluate
#       # rather shorten code with defining a train function of code above and using it here
#       vae = VAE(encoder, decoder, name="VAE")
#       vae.compile(optimizer='adam', loss='mean_squared_error')
#       history = vae.fit(x_train, y_train, epochs=epochs, batch_size=batch_size, validation_data=(x_test, y_test), verbose=0)
#       # report performance
#       # rather make a dataframe or something different which is simpler to plot
#       evaluation = []
#       evaluation.append(vae.evaluate(x_test, y_test))
#       evaluation.append(drop_value)

#       res = []
#       res.append(history.history["val_loss"])
#       print("val_loss = {}".format(res))
#       results.append(evaluation)
#   return results

# results = experiment_dropout()
# # summarize results
# print(results)

"""# Visualization of Hyperparameter Opt. Results

Bar Plot
"""

# Scores of our Hyperparameter Optimization
scores = rs_result['mean_test_score'].tolist()

# Positive Score, i.e. each score in scores * (-1)
posScores = []
for s in scores:
    posScores.append(s * (-1))

indices = np.arange(0, len(scores))

plt.bar(indices, posScores, tick_label=indices)
plt.title("Score of each parameter combination")
plt.xlabel("Unit")
plt.ylabel("Score")
# save fig
plt.savefig(fname="scores.png")

"""Scatter Plot"""

###
features = ['batch_size', 'dropout_rate', 'regulazier_rate', 'learn_rate']

fig, axs = plt.subplots(nrows=len(features), ncols=len(features), figsize=(12, 12))
fig.tight_layout(w_pad=2, h_pad=2)

col = 0
for feature_1 in features:
    row = 0
    for feature_2 in features:
        bestComb = min_rs_results.iloc[0:5]
        rest = min_rs_results.iloc[5:]
        axs[row, col].scatter(bestComb[feature_1], bestComb[feature_2], color='green', alpha=0.7)
        axs[row, col].scatter(rest[feature_1], rest[feature_2], color='red', alpha=0.7)
        axs[row, col].set_xlabel(feature_1, fontsize=9)
        axs[row, col].set_ylabel(feature_2, fontsize=9)
        row = row + 1
    col = col + 1

# save fig
plt.savefig('scoresScatter.png')
