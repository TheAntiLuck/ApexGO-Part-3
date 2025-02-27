import numpy as np
from dlgo.goboard_fast import Move
from dlgo.gotypes import Player, Point


class ZeroEncoder:
    def __init__(self, board_size):
        self.board_size = board_size

        # 11 planes total
        # 0: 1 liberty stones
        # 1: 2 liberty stones
        # 2: 3 liberty stones
        # 3: 4 or more liberties
        # 4: opponent stones with 1 liberty
        # 5: opponent stones with 2 liberties
        # 6: opponent stones with 3 liberties
        # 7: opponent stones with 4 or more liberties
        # 8: 1 if komi
        # 9: 1 if opponent komi
        # 10: illegal moves due to ko
        self.num_planes = 11

    def encode(self, game_state):
        board_tensor = np.zeros(self.shape())
        next_player = game_state.next_player

        if game_state.next_player == Player.white:
            board_tensor[8] = 1
        else:
            board_tensor[9] = 1

        for r in range(self.board_size):
            for c in range(self.board_size):
                p = Point(row=r + 1, col=c + 1)
                go_string = game_state.board.get_go_string(p)

                if go_string is None:
                    if game_state.does_move_violate_ko(next_player, Move.play(p)):
                        board_tensor[10][r][c] = 1

                else:
                    liberty_plane = min(4, go_string.num_liberties) - 1

                    if go_string.color != next_player:
                        liberty_plane += 4

                    board_tensor[liberty_plane][r][c] = 1

        return board_tensor

    # convert move to index, except passing is now the (num rows * num cols)-th option
    def encode_move(self, move):
        if move.is_play:
            return self.board_size * (move.point.row - 1) + (move.point.col - 1)
        elif move.is_pass:
            return self.board_size * self.board_size

        raise ValueError('Cannot encode resign move')

    def decode_move_index(self, index):
        if index == self.board_size * self.board_size:
            return Move.pass_turn()

        row = index // self.board_size
        col = index % self.board_size

        return Move.play(Point(row=row + 1, col=col + 1))

    def num_moves(self):
        return self.board_size * self.board_size + 1

    def shape(self):
        return self.num_planes, self.board_size, self.board_size
