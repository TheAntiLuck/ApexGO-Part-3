import numpy as np

from keras.optimizers import SGD

from dlgo import encoders
from dlgo import goboard
from dlgo import kerasutil
from dlgo.agent import Agent
from dlgo.agent.helpers import is_point_an_eye

__all__ = [
    'QAgent',
    'load_q_agent',
]


class QAgent(Agent):    # 11.5
    def __init__(self, model, encoder, policy='eps-greedy'):
        Agent.__init__(self)
        self.model = model
        self.encoder = encoder
        self.collector = None
        self.temperature = 0.0
        self.policy = policy
        self.last_move_value = 0

    # Temperature is the epsilon value that controls how randomized the policy is
    def set_temperature(self, temperature):
        self.temperature = temperature

    # See chapter 9 for more information about using a collector object to record the agent's exp
    def set_collector(self, collector):
        self.collector = collector

    def set_policy(self, policy):
        if policy not in ('eps-greedy', 'weighted'):
            raise ValueError(policy)
        self.policy = policy

    def select_move(self, game_state):  # 11.6
        board_tensor = self.encoder.encode(game_state)

        # Generates a list of all valid moves
        moves = []
        board_tensors = []
        for move in game_state.legal_moves():
            if not move.is_play:
                continue
            moves.append(self.encoder.encode_point(move.point))
            board_tensors.append(board_tensor)
        # If there are no valid moves left, the agent can just pass.
        if not moves:
            return goboard.Move.pass_turn()

        num_moves = len(moves)
        board_tensors = np.array(board_tensors)
        # One-hot encodes all the valid moves (see chapter 5 for more on one-hot encoding)
        move_vectors = np.zeros((num_moves, self.encoder.num_points()))
        for i, move in enumerate(moves):
            move_vectors[i][move] = 1

        # This is the two-input form of predict: you pass the two inputs as a list.
        values = self.model.predict([board_tensors, move_vectors])

        # Values will be an N × 1 matrix, where N is the number of legal moves;
        # the reshape call converts to a vector of size N.
        values = values.reshape(len(moves))

        # Ranks according to the epsilon-greedy policy
        # ranked_moves = self.rank_moves_eps_greedy(values)
        if self.policy == 'eps-greedy':
            ranked_moves = self.rank_moves_eps_greedy(values)
        elif self.policy == 'weighted':
            ranked_moves = self.rank_moves_weighted(values)
        else:
            ranked_moves = None

        # Picks the first non­self­destructive move in your list, 
        # similar to the self­play agents from chapter 9
        for move_idx in ranked_moves:
            point = self.encoder.decode_point_index(moves[move_idx])
            if not is_point_an_eye(game_state.board,
                                   point,
                                   game_state.next_player):
                # Records the decision in an experience buffers; see chapter 9
                if self.collector is not None:
                    self.collector.record_decision(
                        state=board_tensor,
                        action=moves[move_idx],
                    )
                return goboard.Move.play(point)
        # You'll fall through here if all the valid moves are determined to be self-destructive.
        return goboard.Move.pass_turn()

    def rank_moves_eps_greedy(self, values):    # 11.7
        # In the exploration case, rank the moves by random numbers instead of the real values.
        if np.random.random() < self.temperature:
            values = np.random.random(values.shape)
        # Gets the indices of the moves in order from least value to highest value
        ranked_moves = np.argsort(values)
        # [::-1] syntax is the most efficient way to reverse a vector in NumPy.
        # This returns the moves in order from highest value to least
        return ranked_moves[::-1]

    def rank_moves_weighted(self, values):
        p = values / np.sum(values)
        p = np.power(p, 1.0 / self.temperature)
        p = p / np.sum(p)
        return np.random.choice(
            np.arange(0, len(values)),
            size=len(values),
            p=p,
            replace=False)

    def train(self, experience, lr=0.1, batch_size=128):    # 11.8
        # lr and batch_size are options to fine-tun the training process.
        # See chapter 10 for more discussion
        opt = SGD(lr=lr)
        # mse is mean squared error. You use mse instead of categorical_crossentropy
        # because you're trying to learn a continuous value.
        self.model.compile(loss='mse', optimizer=opt)

        n = experience.states.shape[0]
        num_moves = self.encoder.num_points()
        y = np.zeros((n,))
        actions = np.zeros((n, num_moves))
        for i in range(n):
            action = experience.actions[i]
            reward = experience.rewards[i]
            actions[i][action] = 1
            y[i] = reward

        # Passes the two different inputs as a list
        self.model.fit(
            [experience.states, actions], y,
            batch_size=batch_size,
            epochs=1)

    def serialize(self, h5file):
        h5file.create_group('encoder')
        h5file['encoder'].attrs['name'] = self.encoder.name()
        h5file['encoder'].attrs['board_width'] = self.encoder.board_width
        h5file['encoder'].attrs['board_height'] = self.encoder.board_height
        h5file.create_group('model')
        kerasutil.save_model_to_hdf5_group(self.model, h5file['model'])

    def diagnostics(self):
        return {'value': self.last_move_value}


def load_q_agent(h5file):
    model = kerasutil.load_model_from_hdf5_group(h5file['model'])
    encoder_name = h5file['encoder'].attrs['name']
    if not isinstance(encoder_name, str):
        encoder_name = encoder_name.decode('ascii')
    board_width = h5file['encoder'].attrs['board_width']
    board_height = h5file['encoder'].attrs['board_height']
    encoder = encoders.get_encoder_by_name(
        encoder_name,
        (board_width, board_height))
    return QAgent(model, encoder)
