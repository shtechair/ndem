#!/usr/bin/env python
# coding=utf-8

from __future__ import division, print_function, unicode_literals

import tensorflow as tf
import tensorflow.contrib.slim as slim

from sacred import Ingredient
from tensorflow.contrib.rnn import RNNCell
from utils import ACTIVATION_FUNCTIONS

import numpy as np

net = Ingredient('network')


@net.config
def cfg():
    use_NEM_formulation = False
    input = []
    recurrent = [
        {'name': 'rnn', 'size': 250, 'act': 'sigmoid', 'ln': False}
    ]
    output = [
        {'name': 'fc', 'size': 784, 'act': '*', 'ln': False},
    ]



net.add_named_config('flying_mnist', {
    'input': [
        {'name': 'input_norm'},
        {'name': 'reshape', 'shape': (24, 24, 1)},
        {'name': 'conv', 'size': 32, 'act': 'elu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'conv', 'size': 64, 'act': 'elu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'conv', 'size': 128, 'act': 'elu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'reshape', 'shape': -1},
        {'name': 'fc', 'size': 512, 'act': 'elu', 'ln': True}
    ],
    'recurrent': [
        {'name': 'rnn', 'size': 250, 'act': 'sigmoid', 'ln': True}
    ],
    'output': [
        {'name': 'fc', 'size': 512, 'act': 'relu', 'ln': True},
        {'name': 'fc', 'size': 3 * 3 * 128, 'act': 'relu', 'ln': True},
        {'name': 'reshape', 'shape': (3, 3, 128)},
        {'name': 'r_conv', 'size': 64, 'act': 'relu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'r_conv', 'size': 32, 'act': 'relu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'r_conv', 'size': 1, 'act': '*', 'stride': [2, 2], 'kernel': (4, 4), 'ln': False},
        {'name': 'reshape', 'shape': -1}
    ]})


net.add_named_config('flying_shapes', {
    'input': [
        {'name': 'reshape', 'shape': (28, 28, 1)},
        {'name': 'conv', 'size': 32, 'act': 'elu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'conv', 'size': 64, 'act': 'elu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'reshape', 'shape': -1},
        {'name': 'fc', 'size': 512, 'act': 'elu', 'ln': True},
    ],
    'recurrent': [
        {'name': 'rnn', 'size': 100, 'act': 'sigmoid', 'ln': True}
    ],
    'output': [
        {'name': 'fc', 'size': 512, 'act': 'relu', 'ln': True},
        {'name': 'fc', 'size': 7*7*64, 'act': 'relu', 'ln': True},
        {'name': 'reshape', 'shape': (7, 7, 64)},
        {'name': 'r_conv', 'size': 32, 'act': 'relu', 'stride': [2, 2], 'kernel': (4, 4), 'ln': True},
        {'name': 'r_conv', 'size': 1, 'act': '*', 'stride': [2, 2], 'kernel': (4, 4), 'ln': False},
        {'name': 'reshape', 'shape': -1},
    ]})


net.add_named_config('shapes', {
    'input': [],
    'recurrent': [
        {'name': 'rnn', 'size': 250, 'act': 'sigmoid', 'ln': False}
    ],
    'output': [
        {'name': 'fc', 'size': 784, 'act': '*', 'ln': False}
    ]
    # 'discriminative': [
    #     {'s_hidden_dim': 10}
    # ]
})


net.add_named_config('NEM', {
    'use_NEM_formulation': True,
    'input': [],
    'recurrent': [
        {'name': 'rnn', 'size': 250, 'act': 'sigmoid', 'ln': False}
    ],
    'output': [
        {'name': 'fc', 'size': 784, 'act': 'sigmoid', 'ln': False}
    ]})


# GENERIC WRAPPERS


class InputWrapper(RNNCell):
    """Adding an input projection to the given cell."""

    def __init__(self, cell, spec, name="InputWrapper"):
        self._cell = cell
        self._spec = spec
        self._name = name

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._cell.output_size

    def __call__(self, inputs, state, scope=None):
        projected = None
        with tf.variable_scope(scope or self._name):
            if self._spec['name'] == 'fc':
                projected = slim.fully_connected(inputs, self._spec['size'], activation_fn=None)
            elif self._spec['name'] == 'conv':
                projected = slim.conv2d(inputs, self._spec['size'], self._spec['kernel'], self._spec['stride'], activation_fn=None)
            else:
                raise ValueError('Unknown layer name "{}"'.format(self._spec['name']))

        return self._cell(projected, state)


class OutputWrapper(RNNCell):
    def __init__(self, cell, spec, n_out=1, name="OutputWrapper"):
        self._cell = cell
        self._spec = spec
        self._name = name
        self._n_out = n_out

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._spec['size']

    def __call__(self, inputs, state, scope=None):
        output, res_state = self._cell(inputs, state)

        projected = None
        with tf.variable_scope((scope or self._name)):
            if self._spec['name'] == 'fc':
                projected = slim.fully_connected(output, self._spec['size'], activation_fn=None)
            elif self._spec['name'] == 't_conv':
                projected = slim.layers.conv2d_transpose(output, self._spec['size'], self._spec['kernel'], self._spec['stride'], activation_fn=None)
            elif self._spec['name'] == 'r_conv':
                resized = tf.image.resize_images(output, (self._spec['stride'][0] * output.get_shape()[1].value,
                                                          self._spec['stride'][1] * output.get_shape()[2].value), method=1)
                projected = slim.layers.conv2d(resized, self._spec['size'], self._spec['kernel'], activation_fn=None)
            else:
                raise ValueError('Unknown layer name "{}"'.format(self._spec['name']))

        return projected, res_state


class ReshapeWrapper(RNNCell):
    def __init__(self, cell, shape='flatten', apply_to='output'):
        self._cell = cell
        self._shape = shape
        self._apply_to = apply_to

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._cell.output_size

    def __call__(self, inputs, state, scope=None):
        batch_size = tf.shape(inputs)[0]

        if self._apply_to == 'input':
            inputs = slim.flatten(inputs) if self._shape == -1 else tf.reshape(inputs, [batch_size] + self._shape)
            return self._cell(inputs, state)
        elif self._apply_to == 'output':
            output, res_state = self._cell(inputs, state)
            output = slim.flatten(output) if self._shape == -1 else tf.reshape(output, [batch_size] + self._shape)
            return output, res_state
        elif self._apply_to == 'state':
            output, res_state = self._cell(inputs, state)
            res_state = slim.flatten(res_state) if self._shape == -1 else tf.reshape(res_state, [batch_size] + self._shape)
            return output, res_state
        else:
            raise ValueError('Unknown apply_to: "{}"'.format(self._apply_to))


class ActivationFunctionWrapper(RNNCell):
    def __init__(self, cell, activation='linear', apply_to='output'):
        self._cell = cell
        self._activation = ACTIVATION_FUNCTIONS[activation]
        self._apply_to = apply_to

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._cell.output_size

    def __call__(self, inputs, state, scope=None):
        if self._apply_to == 'input':
            inputs = self._activation(inputs)
            return self._cell(inputs, state)
        elif self._apply_to == 'output':
            output, res_state = self._cell(inputs, state)
            output = self._activation(output)
            return output, res_state
        elif self._apply_to == 'state':
            output, res_state = self._cell(inputs, state)
            res_state = self._activation(res_state)
            return output, res_state
        else:
            raise ValueError('Unknown apply_to: "{}"'.format(self._apply_to))


class LayerNormWrapper(RNNCell):
    def __init__(self, cell, apply_to='output', name="LayerNorm"):
        self._cell = cell
        self._name = name
        self._apply_to = apply_to

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._cell.output_size

    def __call__(self, inputs, state, scope=None):
        if self._apply_to == 'input':
            with tf.variable_scope(scope or self._name):
                inputs = slim.layer_norm(inputs)
            return self._cell(inputs, state)
        elif self._apply_to == 'output':
            output, res_state = self._cell(inputs, state)
            with tf.variable_scope(scope or self._name):
                output = slim.layer_norm(output)
                return output, res_state
        elif self._apply_to == 'state':
            output, res_state = self._cell(inputs, state)
            with tf.variable_scope(scope or self._name):
                res_state = slim.layer_norm(res_state)
                return output, res_state
        else:
            raise ValueError('Unknown apply_to: "{}"'.format(self._apply_to))


class InputNormalizationWrapper(RNNCell):
    def __init__(self, cell, name="InputNorm"):
        self._cell = cell
        self._name = name

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._cell.output_size

    def __call__(self, inputs, state, scope=None):
        with tf.variable_scope(scope or self._name):
            mean, var = tf.nn.moments(inputs, axes=[1])
            inputs = (inputs - tf.expand_dims(mean, axis=1)) / tf.sqrt(tf.expand_dims(var, axis=1))

        return self._cell(inputs, state)


# EM CELL (WRAPPERS)

class NEMCell(RNNCell):
    def __init__(self, num_units, name="NEMCell"):
        self._num_units = num_units
        self._name = name

    @property
    def state_size(self):
        return self._num_units

    @property
    def output_size(self):
        return self._num_units

    def __call__(self, inputs, state, scope=None):
        with tf.variable_scope(scope or self._name):
            with tf.variable_scope(scope or "lr"):
                lr = tf.get_variable("scalar", shape=(1, 1), dtype=tf.float32)

            # apply z = z' + lr * sigma(z')(1 - sigma(z'))* W^T * x
            output = state + lr * tf.sigmoid(state) * (1 - tf.sigmoid(state)) * slim.fully_connected(
                inputs, self._num_units, scope='input', activation_fn=None, biases_initializer=None)

        return tf.sigmoid(output), output


class NEMOutputWrapper(RNNCell):
    def __init__(self, cell, size, weight_path, name="NEMOutputWrapper"):
        self._cell = cell
        self._size = size
        self._weight_path = weight_path
        self._name = name

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._size

    def __call__(self, inputs, state, scope=None):
        output, res_state = self._cell(inputs, state)

        with tf.variable_scope("multi_rnn_cell/cell_0/NEMCell/input", reuse=True):
            W_t = tf.transpose(tf.get_variable("weights"))

        projected = tf.matmul(output, W_t)

        return projected, res_state


class NEMOutputDiscriWrapper(RNNCell):
    def __init__(self, cell, size, weight_path, name="NEMOutputDiscriWrapper"):
        self._cell = cell
        self._size = size
        self._weight_path = weight_path
        self._name = name
        self.lambda_v = 0
        self.lambda_vs = [1.0 for i in range(20)] + [i/11.0 for i in range(11)]

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._size

    def inference_network(self, x, latent_dim):
        """Construct an inference network parametrizing a Gaussian.
           Ref: https://github.com/altosaar/variational-autoencoder.git

        Args:
          x: A batch of pictures.
          latent_dim: The latent dimensionality.
          hidden_size: The size of the neural net hidden layers.

        Returns:
          mu: Mean parameters for the variational family Normal
          sigma: Standard deviation parameters for the variational family Normal
        """
        with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu):
            input_layer = tf.reshape(x, [-1, 28, 28, 1])
            conv1 = slim.layers.conv2d(
                inputs=input_layer,
                num_outputs=32,
                kernel_size=[5, 5],
                padding="same",
                activation_fn=tf.nn.relu)
            pool1 = slim.layers.max_pool2d(inputs=conv1, kernel_size=[2, 2], stride=[2,2])
            conv2 = slim.layers.conv2d(
                inputs=pool1,
                num_outputs=64,
                kernel_size=[5, 5],
                padding="same",
                activation_fn=tf.nn.relu)
            pool2 = slim.layers.max_pool2d(inputs=conv2, kernel_size=[2, 2], stride=[2,2])
            pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
            dense1 = slim.layers.fully_connected(inputs=pool2_flat, num_outputs=latent_dim*2, activation_fn=tf.nn.relu)
            mu = dense1[:, :latent_dim]
            sigma = tf.nn.softplus(dense1[:, latent_dim:])
            q_s = tf.distributions.Normal(loc=mu, scale=sigma)
            q_s_sample = q_s.sample()
            dense2 = slim.layers.fully_connected(inputs=q_s_sample, num_outputs=784 * 3, activation_fn=tf.nn.relu)  # k=3
            # dropout = tf.layers.dropout(inputs=dense2, rate=0.5)  # , training=mode == tf.estimator.ModeKeys.TRAIN
            out_context = tf.reshape(dense2, [-1, 784])
        # with slim.arg_scope([slim.fully_connected], activation_fn=tf.nn.relu, reuse=True):
        #     #  for check given s
        #     s_input = tf.placeholder(tf.float32, [None, latent_dim])
        #     dense2 = slim.layers.fully_connected(inputs=s_input, num_outputs=784 * 3, activation_fn=tf.nn.relu)
        #     out_context = tf.reshape(dense2, [-1, 784])
        return q_s, out_context

    def __call__(self, inputs_and_context_ctxtw_klw, state, scope=None):
        # print('+++++++++++++++++++++++++++++++++++')
        inputs, context, context_weight, klloss_weight = inputs_and_context_ctxtw_klw
        output, res_state = self._cell(inputs, state)  # output = sigmoid(W*sigmoid(theta))  res_state=theta
        # context_weight.trainable = False
        # context_weight.name = 'context_weight1'
        # klloss_weight.trainable = False
        # klloss_weight = tf.identity(klloss_weight, name='klloss_weight1')

        # print('name: ', context_weight.name)

        anti_overfit_type = 'variational_2' # 'dropout', 'denoising'
        # with tf.variable_scope('context_and_klloss_weight', reuse=True):
        #     context_weight2 = tf.get_variable(name='context_weight222', shape=[1], dtype=tf.float32)
        #     klloss_weight = tf.get_variable(name='klloss_weight', shape=[1], dtype=tf.float32)

        if anti_overfit_type == 'variational_2':
            with tf.variable_scope("multi_rnn_cell/cell_0/EMCell_discri/input_discri"):
                latent_s_dim = 10

                input_layer = tf.reshape(context, [-1, 28, 28, 1])
                conv1 = slim.layers.conv2d(
                    inputs=input_layer,
                    num_outputs=32,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool1 = slim.layers.max_pool2d(inputs=conv1, kernel_size=[2, 2], stride=[2, 2])
                conv2 = slim.layers.conv2d(
                    inputs=pool1,
                    num_outputs=64,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool2 = slim.layers.max_pool2d(inputs=conv2, kernel_size=[2, 2], stride=[2, 2])
                pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
                s_mu = slim.layers.fully_connected(inputs=pool2_flat, num_outputs=latent_s_dim,
                                                     # activation_fn=tf.nn.relu,
                                                     weights_regularizer=slim.l2_regularizer(scale=0.1),
                                                     biases_regularizer=slim.l2_regularizer(scale=0.1)
                                                     )
                s_logvar = slim.layers.fully_connected(inputs=pool2_flat, num_outputs=latent_s_dim,
                                                     # activation_fn=tf.nn.relu,
                                                     weights_regularizer=slim.l2_regularizer(scale=0.1),
                                                     biases_regularizer=slim.l2_regularizer(scale=0.1)
                                                     )
                kltype = 1
                if kltype==1:
                    eps = tf.random_normal(shape=tf.shape(s_mu))
                    q_s_sample = s_mu + tf.exp(s_logvar / 2) * eps
                    kl = 0.5 * tf.reduce_sum(tf.exp(s_logvar) + s_mu ** 2 - 1. - s_logvar, 1)
                else:
                    q_s = tf.distributions.Normal(loc=s_mu, scale=tf.exp(s_logvar))
                    # assert q_s.reparameterization_type == tf.distributions.FULLY_REPARAMETERIZED
                    q_s_sample = q_s.sample()
                    p_s = tf.distributions.Normal(loc=np.zeros(latent_s_dim, dtype=np.float32),
                                                  scale=np.ones(latent_s_dim, dtype=np.float32))
                    kl = tf.reduce_sum(tf.distributions.kl_divergence(q_s, p_s), 1) # minimize it.

                self.lambda_v = self.lambda_v + 1
                # print('self.lambda_vs[self.lambda_v]:  ', self.lambda_vs[self.lambda_v])
                # print('self.lambda_v: ', self.lambda_v)
                variational_loss = tf.reduce_sum(kl, 0)* klloss_weight
                # variational_loss = tf.reduce_sum(kl, 0) * self.lambda_vs[self.lambda_v]
                # variational_loss = tf.Variable(0, dtype='float32')
                dense2 = slim.layers.fully_connected(inputs=q_s_sample, num_outputs=784 * 3,
                                                     # activation_fn=tf.nn.relu,
                                                     weights_regularizer=slim.l2_regularizer(scale=0.1),
                                                     biases_regularizer=slim.l2_regularizer(scale=0.1)
                                                     )  # k=3
                # dropout = tf.layers.dropout(inputs=dense2, rate=0.5)  # , training=mode == tf.estimator.ModeKeys.TRAIN
                out_context = tf.reshape(dense2, [-1, 784])
                # out_context = slim.layers.dropout(inputs=out_context, keep_prob=0.5)  # dropout correct
                # print(out_context)

                # train_op = optimizer.minimize(elbo)

            # context_weight = tf.Print(context_weight, [context_weight])
            # tf.Session().run(context_weight)
            # print(context_weight.eval())
                weighted_context = out_context *context_weight
                weighted_context =tf.identity(weighted_context, name='weighted_context')
                print(weighted_context.name)
            projected = output + weighted_context  # q_s_sample.size() = batch_size * latent_dim
        elif anti_overfit_type == 'variational':
            with tf.variable_scope("multi_rnn_cell/cell_0/EMCell_discri/input_discri"):
                latent_s_dim = 10

                input_layer = tf.reshape(context, [-1, 28, 28, 1])
                conv1 = slim.layers.conv2d(
                    inputs=input_layer,
                    num_outputs=32,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool1 = slim.layers.max_pool2d(inputs=conv1, kernel_size=[2, 2], stride=[2, 2])
                conv2 = slim.layers.conv2d(
                    inputs=pool1,
                    num_outputs=64,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool2 = slim.layers.max_pool2d(inputs=conv2, kernel_size=[2, 2], stride=[2, 2])
                pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
                dense1 = slim.layers.fully_connected(inputs=pool2_flat, num_outputs=latent_s_dim * 2,
                                                     # activation_fn=tf.nn.relu,
                                                     weights_regularizer=slim.l2_regularizer(scale=0.1),
                                                     biases_regularizer=slim.l2_regularizer(scale=0.1)
                                                     )
                mu = dense1[:, :latent_s_dim]
                sigma = tf.nn.softplus(dense1[:, latent_s_dim:])
                q_s = tf.distributions.Normal(loc=mu, scale=sigma)
                assert q_s.reparameterization_type == tf.distributions.FULLY_REPARAMETERIZED
                q_s_sample = q_s.sample()
                dense2 = slim.layers.fully_connected(inputs=q_s_sample, num_outputs=784 * 3,
                                                     # activation_fn=tf.nn.relu,
                                                     weights_regularizer=slim.l2_regularizer(scale=0.1),
                                                     biases_regularizer=slim.l2_regularizer(scale=0.1))  # k=3
                # dropout = tf.layers.dropout(inputs=dense2, rate=0.5)  # , training=mode == tf.estimator.ModeKeys.TRAIN
                out_context = tf.reshape(dense2, [-1, 784])
                # out_context = slim.layers.dropout(inputs=out_context, keep_prob=0.5)  # dropout correct
                # debug
                # q_s, out_context = self.inference_network(x=context, latent_dim=latent_s_dim)
                p_s = tf.distributions.Normal(loc=np.zeros(latent_s_dim, dtype=np.float32),
                                              scale=np.ones(latent_s_dim, dtype=np.float32))
                kl = tf.reduce_sum(tf.distributions.kl_divergence(q_s, p_s), 1) # minimize it.
                variational_loss = tf.reduce_sum(kl, 0)
                # variational_loss = tf.Variable(0, dtype='float32')
                print(out_context)

                # train_op = optimizer.minimize(elbo)
            projected = output + out_context  # q_s_sample.size() = batch_size * latent_dim
        elif anti_overfit_type == 'dropout_with_slim':
            with tf.variable_scope("multi_rnn_cell/cell_0/EMCell_discri/input_discri"):
                input_layer = tf.reshape(context, [-1, 28, 28, 1])
                conv1 = slim.layers.conv2d(
                    inputs=input_layer,
                    num_outputs=32,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool1 = slim.layers.max_pool2d(inputs=conv1, kernel_size=[2, 2], stride=[2,2])
                conv2 = slim.layers.conv2d(
                    inputs=pool1,
                    num_outputs=64,
                    kernel_size=[5, 5],
                    padding="same",
                    activation_fn=tf.nn.relu)
                pool2 = slim.layers.max_pool2d(inputs=conv2, kernel_size=[2, 2], stride=[2,2])
                pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
                dense1 = slim.layers.fully_connected(inputs=pool2_flat, num_outputs=10, activation_fn=tf.nn.relu)
                dense2 = slim.layers.fully_connected(inputs=dense1, num_outputs=784 * 3, activation_fn=tf.nn.relu)  # k=3
                dropout = slim.layers.dropout(inputs=dense2, keep_prob=0.5)  # , training=mode == tf.estimator.ModeKeys.TRAIN
                out_context = tf.reshape(dropout, [-1, 784])

                variational_loss = tf.Variable(0, dtype='float32')

            projected = output + out_context
        elif anti_overfit_type == 'dropout':
            with tf.variable_scope("multi_rnn_cell/cell_0/EMCell_discri/input_discri"):  # , reuse=True
                # W_t = tf.transpose(tf.get_variable("weights"))  ??
                input_layer = tf.reshape(context, [-1, 28, 28, 1])
                conv1 = tf.layers.conv2d(
                    inputs=input_layer,
                    filters=32,
                    kernel_size=[5, 5],
                    padding="same",
                    activation=tf.nn.relu)
                pool1 = tf.layers.max_pooling2d(inputs=conv1, pool_size=[2, 2], strides=2)
                conv2 = tf.layers.conv2d(
                    inputs=pool1,
                    filters=64,
                    kernel_size=[5, 5],
                    padding="same",
                    activation=tf.nn.relu)
                pool2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[2, 2], strides=2)
                pool2_flat = tf.reshape(pool2, [-1, 7 * 7 * 64])
                dense1 = tf.layers.dense(inputs=pool2_flat, units=10, activation=tf.nn.relu)
                dense2 = tf.layers.dense(inputs=dense1, units=784*4, activation=tf.nn.relu)
                # dense2 = tf.layers.dense(inputs=dense1, units=784, activation=tf.nn.relu)
                dropout = tf.layers.dropout(
                    inputs=dense2, rate=0.5) # , training=mode == tf.estimator.ModeKeys.TRAIN
                out_context = tf.reshape(dropout, [-1, 784])
            projected = output + out_context


        return (projected, variational_loss), res_state  # projected = output+cnn(context)


class NEMOutputNoneWrapper(RNNCell):
    def __init__(self, cell, size, weight_path, name="NEMOutputNoneWrapper"):
        self._cell = cell
        self._size = size
        self._weight_path = weight_path
        self._name = name

    @property
    def state_size(self):
        return self._cell.state_size

    @property
    def output_size(self):
        return self._size

    def __call__(self, inputs_and_context, state, scope=None):
        inputs, context = inputs_and_context
        output, res_state = self._cell(inputs, state)  # output = sigmoid(W*sigmoid(theta))  res_state=theta
        with tf.variable_scope("multi_rnn_cell/cell_0/EMCell_None/input_discri"):  # , reuse=True
            pass
        projected = output
        return projected, res_state  # projected = output+cnn(context)

# NETWORK BUILDER


@net.capture
def build_network(out_size, output_dist, input, recurrent, output, use_NEM_formulation=False):
    with tf.name_scope('inner_RNN'):

        # use proper mathematical formulation
        if use_NEM_formulation:
            cell = NEMCell(recurrent[0]['size'])
            cell = tf.contrib.rnn.MultiRNNCell([cell])

            cell = NEMOutputWrapper(cell, out_size, "multi_rnn_cell/cell_0/EMCell")
            # print('++++++++++++++++++++++++++++++++')
            # print(output[0]['act'])
            cell = ActivationFunctionWrapper(cell, output[0]['act'])
            # DEBUG
            cell = NEMOutputDiscriWrapper(cell, out_size, "multi_rnn_cell/cell_0/EMCell_discri")

            return cell

        # build recurrent
        cell_list = []
        for i, layer in enumerate(recurrent):

            if layer['name'] == 'rnn':
                cell = tf.contrib.rnn.BasicRNNCell(layer['size'], activation=ACTIVATION_FUNCTIONS['linear'])
                cell = LayerNormWrapper(cell, apply_to='output', name='LayerNormR{}'.format(i)) if layer['ln'] else cell
                cell = ActivationFunctionWrapper(cell, activation=layer['act'], apply_to='state')
                cell = ActivationFunctionWrapper(cell, activation=layer['act'], apply_to='output')

            else:
                raise ValueError('Unknown recurrent name "{}"'.format(layer['name']))

            cell_list.append(cell)

        cell = tf.contrib.rnn.MultiRNNCell(cell_list)

        # build input
        for i, layer in reversed(list(enumerate(input))):
            if layer['name'] == 'reshape':
                cell = ReshapeWrapper(cell, layer['shape'], apply_to='input')
            elif layer['name'] == 'input_norm':
                cell = InputNormalizationWrapper(cell, name='InputNormalization')
            else:
                cell = ActivationFunctionWrapper(cell, layer['act'], apply_to='input')
                cell = LayerNormWrapper(cell, apply_to='input', name='LayerNormI{}'.format(i)) if layer['ln'] else cell
                cell = InputWrapper(cell, layer, name="InputWrapper{}".format(i))

        # build output
        for i, layer in enumerate(output):
            if layer['name'] == 'reshape':
                cell = ReshapeWrapper(cell, layer['shape'])
            else:
                n_out = layer.get('n_out', 1)
                cell = OutputWrapper(cell, layer, n_out=n_out, name="OutputWrapper{}".format(i))
                cell = LayerNormWrapper(cell, apply_to='output', name='LayerNormO{}'.format(i)) if layer['ln'] else cell

                if layer['act'] == '*':
                    output_act = 'linear' if output_dist == 'gaussian' else 'sigmoid'
                    cell = ActivationFunctionWrapper(cell, output_act, apply_to='output')
                    # DEBUG
                    cell = NEMOutputDiscriWrapper(cell, out_size, "multi_rnn_cell/cell_0/EMCell_discri")
                else:
                    cell = ActivationFunctionWrapper(cell, layer['act'], apply_to='output')


        return cell
