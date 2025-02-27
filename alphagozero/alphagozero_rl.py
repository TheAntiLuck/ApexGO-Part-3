import time

from keras.layers import Conv2D, Flatten, Dense
from keras.models import Model, Input

import h5py

import dlgo.zero as zero
from dlgo.goboard_fast import GameState
from dlgo.gotypes import Player
from dlgo import scoring


def simulate_game(
        board_size,
        black_agent, black_collector,
        white_agent, white_collector):
    print('Starting the game!')
    game = GameState.new_game(board_size)
    agents = {
        Player.black: black_agent,
        Player.white: white_agent,
    }

    black_collector.begin_episode()
    white_collector.begin_episode()
    while not game.is_over():
        next_move = agents[game.next_player].select_move(game)
        game = game.apply_move(next_move)

    game_result = scoring.compute_game_result(game)
    if game_result.winner == Player.black:
        black_collector.complete_episode(1)
        white_collector.complete_episode(-1)
    else:
        black_collector.complete_episode(-1)
        white_collector.complete_episode(1)


def run():
    board_size = 9
    encoder = zero.ZeroEncoder(board_size)
    board_input = Input(shape=encoder.shape(), name='board_input')
    pb = board_input

    for i in range(16):
        pb = Conv2D(64, (3, 3), padding='same', data_format='channels_first', activation='relu')(pb)

    policy_conv = Conv2D(2, (1, 1), data_format='channels_first', activation='relu')(pb)

    policy_flat = Flatten()(policy_conv)

    policy_output = Dense(encoder.num_moves(), activation='softmax')(policy_flat)

    value_conv = Conv2D(1, (1, 1), data_format='channels_first', activation='relu')(pb)

    value_flat = Flatten()(value_conv)
    value_hidden = Dense(256, activation='relu')(value_flat)
    value_output = Dense(1, activation='tanh')(value_hidden)

    model = Model(inputs=[board_input], outputs=[policy_output, value_output])

    black_agent = zero.ZeroAgent(model, encoder, rounds_per_move=10, c=2.0)
    white_agent = zero.ZeroAgent(model, encoder, rounds_per_move=10, c=2.0)

    c1 = zero.ZeroExperienceCollector()
    c2 = zero.ZeroExperienceCollector()

    black_agent.set_collector(c1)
    white_agent.set_collector(c2)

    num_games = 10

    for i in range(num_games):
        print(f'Game {i+1}/{num_games}')
        start_time = time.time()
        simulate_game(board_size, black_agent, c1, white_agent, c2)

        elapsed = time.time() - start_time
        print(f'elapsed: {elapsed} s')
        print(f'estimated time remaining this session: {(num_games - (i + 1)) * elapsed} s')

    exp = zero.combine_experience([c1, c2], board_size)
    black_agent.train(exp, 0.01, 1024)

    with h5py.File('agz_experience.h5', 'a') as expfile:
        exp.serialize(expfile)


if __name__ == '__main__':
    run()
