import argparse
import os
import random
import time

import numpy as np
import game_env_dino
import tensorflow as tf
import game_utils

parser = argparse.ArgumentParser()
parser.add_argument('--train', dest='train', default=True)
parser.add_argument('--test', dest='test', default=True)

parser.add_argument('--gamma', type=float, default=0.95)
parser.add_argument('--learning_rate', type=float, default=0.005)
parser.add_argument('--batch_size', type=int, default=32)
parser.add_argument('--eps', type=float, default=0.1)

parser.add_argument('--train_episodes', type=int, default=200)
parser.add_argument('--test_episodes', type=int, default=20)
args = parser.parse_args()

ALG_NAME = 'DuelingDQN'
ENV_ID = 'dino'


class ReplayBuffer:
    def __init__(self, capacity=1000):
        self.capacity = capacity
        self.buffer = []
        self.position = 0

    def push(self, state, action, reward, next_state, done):
        if len(self.buffer) < self.capacity:
            self.buffer.append(None)
        self.buffer[self.position] = (state, action, reward, next_state, done)
        self.position = int((self.position + 1) % self.capacity)

    def sample(self, batch_size=args.batch_size):
        batch = random.sample(self.buffer, batch_size)
        state, action, reward, next_state, done = map(np.stack, zip(*batch))
        """ 
        the * serves as unpack: sum(a,b) <=> batch=(a,b), sum(*batch) ;
        zip: a=[1,2], b=[2,3], zip(a,b) => [(1, 2), (2, 3)] ;
        the map serves as mapping the function on each list element: map(square, [2,3]) => [4,9] ;
        np.stack((1,2)) => array([1, 2])
        """
        return state, action, reward, next_state, done


class Agent:
    def __init__(self, env, hidden_layer, model_path):
        self.env = env
        self.model_path = model_path
        self.input_shape = self.env.get_game_frame_shape()
        self.output_dim = self.env.get_game_action_dim()
        self.hidden_layer = hidden_layer

        self.model = game_utils.create_model(input_shape=self.input_shape,
                                             output_dim=self.output_dim,
                                             hidden_layer=self.hidden_layer)

        self.target_model = game_utils.create_model(input_shape=self.input_shape,
                                                    output_dim=self.output_dim,
                                                    hidden_layer=self.hidden_layer)

        self.model_optim = tf.optimizers.Adam(learning_rate=args.learning_rate)

        self.epsilon = args.eps

        self.buffer = ReplayBuffer()

    def target_update(self):
        """Copy q network to target q network"""
        for weights, target_weights in zip(
                self.model.trainable_weights, self.target_model.trainable_weights):
            target_weights.assign(weights)

    def choose_action(self, state):
        if np.random.uniform() < self.epsilon:
            return np.random.choice(self.output_dim)
        else:
            q_value = self.model(state[np.newaxis, :])[0]
            return np.argmax(q_value)

    def replay(self):
        for _ in range(10):
            states, actions, rewards, next_states, done = self.buffer.sample()
            target = self.target_model(states).numpy()
            # next_q_values [batch_size, action_dim]
            next_target = self.target_model(next_states)
            next_q_value = tf.reduce_max(next_target, axis=1)
            target[range(args.batch_size), actions] = rewards + (1 - done) * args.gamma * next_q_value

            # use sgd to update the network weight
            with tf.GradientTape() as tape:
                q_pred = self.model(states)
                loss = tf.losses.mean_squared_error(target, q_pred)
            grads = tape.gradient(loss, self.model.trainable_weights)
            self.model_optim.apply_gradients(zip(grads, self.model.trainable_weights))

    def train(self, train_episodes=200, test_episodes=20):
        max_reward = 0
        if args.train:
            for episode in range(train_episodes):
                total_reward, is_game_over = 0, False
                state = self.env.reset().astype(np.float32)
                while not is_game_over:
                    action = self.choose_action(state)
                    game_frame, reward, is_game_over, step_count, time_cost = self.env.step(action)
                    game_frame = game_frame.astype(np.float32)
                    self.buffer.push(state, action, reward, game_frame, is_game_over)
                    total_reward += reward
                    state = game_frame
                if len(self.buffer.buffer) > args.batch_size:
                    self.replay()
                    self.target_update()
                if total_reward > max_reward:
                    max_reward = total_reward
                    self.save()
                if is_game_over:
                    # 暂停两秒,因为游戏game over后有两秒时间无法操作
                    time.sleep(3)
                print('EP{} Episode Reward={} , Max Reward={}'.format(episode, total_reward, max_reward))
        if args.test:
            self.load()
            return self.test_episode(test_episodes=test_episodes)

    def test_episode(self, test_episodes):
        total_reward_list = []
        for episode in range(test_episodes):
            total_reward, is_game_over = 0, False
            state = self.env.reset().astype(np.float32)
            while not is_game_over:
                action = self.model(np.array([state], dtype=np.float32))[0]
                action = np.argmax(action)
                game_frame, reward, is_game_over, step_count, time_cost = self.env.step(action)
                game_frame = game_frame.astype(np.float32)
                total_reward += reward
                state = game_frame
                # self.env.render()

            if is_game_over:
                # 暂停两秒,因为游戏game over后有两秒时间无法操作
                time.sleep(3)
            print("Test {} | episode rewards is {}".format(episode, total_reward))
            total_reward_list.append(total_reward)
        total_reward_avg = sum(total_reward_list) / test_episodes
        print(f"total_reward_avg={total_reward_avg}")
        return total_reward_avg

    def save(self):
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path)
        print("save model")
        tf.saved_model.save(self.model, os.path.join(self.model_path, 'model'))
        tf.saved_model.save(self.target_model, os.path.join(self.model_path, 'target_model'))

    def load(self):
        if not os.path.exists(self.model_path):
            print("can not find model path ,so can not load model")
            exit(-1)
        print("load model")
        self.model = tf.saved_model.load(os.path.join(self.model_path, 'model'))
        self.target_model = tf.saved_model.load(os.path.join(self.model_path, 'target_model'))


if __name__ == '__main__':
    env = game_env_dino.DinoEnv()
    hidden_layer = {}
    model_path = r"F:\models\dino\_test"
    agent = Agent(env, hidden_layer, model_path)
    agent.train(train_episodes=args.train_episodes, test_episodes=args.test_episodes)
    env.close()
