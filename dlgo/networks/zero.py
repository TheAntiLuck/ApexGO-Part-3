from keras.layers import BatchNormalization, Conv2D, Flatten, Dense, Activation, Add
from keras.models import Model, Input
import dlgo.zero as zero


def create_residual_block(skip_from):
    conv = skip_from

    conv = Conv2D(128, (3, 3), padding='same', data_format='channels_first')(conv)
    conv = BatchNormalization(axis=1)(conv)
    conv = Activation(activation='relu')(conv)

    conv = Conv2D(128, (3, 3), padding='same', data_format='channels_first')(conv)
    conv = BatchNormalization(axis=1)(conv)
    conv = Activation(activation='relu')(conv)

    conv = Conv2D(128, (3, 3), padding='same', data_format='channels_first')(conv)
    conv = BatchNormalization(axis=1)(conv)

    # skip connection
    conv = Add()([conv, skip_from])

    conv = Activation(activation='relu')(conv)

    return conv


def create_policy_head(neck, board_size):
    neck = Conv2D(2, (2, 2), padding='same', data_format='channels_first')(neck)
    neck = BatchNormalization(axis=1)(neck)
    neck = Activation(activation='relu')(neck)

    neck = Flatten(data_format='channels_first')(neck)

    neck = Dense(board_size * board_size + 1)(neck)  # +1 includes padding as a move (idx 361)
    head = Activation(activation='softmax')(neck)

    return head


def create_value_head(neck, board_size):
    neck = Conv2D(1, (2, 2), padding='same', data_format='channels_first')(neck)
    neck = BatchNormalization(axis=1)(neck)
    neck = Activation(activation='relu')(neck)

    neck = Flatten(data_format='channels_first')(neck)  # (19, 19)

    neck = Dense(board_size * board_size, activation='relu')(neck)  # 361
    neck = Dense(128, activation='relu')(neck)
    head = Dense(1, activation='tanh')(neck)

    return head


def zero_model(board_size):
    residual_layers = 4

    encoder = zero.ZeroEncoder(board_size)
    board_input = Input(shape=encoder.shape(), name='board_input')
    pb = board_input

    pb = Conv2D(128, (3, 3), padding='same', data_format='channels_first')(pb)
    pb = BatchNormalization(axis=1)(pb)
    pb = Activation(activation='relu')(pb)

    for i in range(residual_layers):
        pb = create_residual_block(pb)
        conv = pb

    neck = pb

    policy_head = create_policy_head(neck, board_size)
    value_head = create_value_head(neck, board_size)

    return Model(inputs=[board_input], outputs=[policy_head, value_head])
