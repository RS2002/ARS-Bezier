import pickle
import tqdm
import copy
import numpy as np

class ARS():
    def __init__(self,state_dim,action_dim,env,max_epoch,episode_num=16,update_num=10,learning_rate=0.03,exploration_noise=0.05):
        self.state_dim=state_dim
        self.action_dim=action_dim

        self.state = np.zeros(state_dim)
        self.mean = np.zeros(state_dim)
        self.mean_diff = np.zeros(state_dim)
        self.var = np.zeros(state_dim)

        self.param = np.zeros([action_dim, state_dim])

        self.env=env
        self.learning_rate=learning_rate
        self.max_epoch=max_epoch
        self.episode_num=episode_num
        self.update_num=update_num
        self.exploration_noise=exploration_noise

        self.best_reward=None
        self.best_distance=None

    def norm(self,x):
        self.state += 1.0
        last_mean = copy.deepcopy(self.mean)
        # running avg
        self.mean += (x - self.mean) / self.state
        # running variance
        self.mean_diff += (x - last_mean) * (x - self.mean)
        self.var = (self.mean_diff / self.state).clip(min=1e-8)
        # normalization
        return (x - self.mean) / np.sqrt(self.var)

    def forward(self,x,param):
        x=self.norm(x)
        y = param.dot(x)
        y = np.tanh(y)
        return y

    def update(self,delta_list,pos_reward,neg_reward):
        rewards_dev=np.std(pos_reward+neg_reward)
        update_direction=0
        for i in range(delta_list.shape[0]):
            update_direction+=(pos_reward[i]-neg_reward[i])*delta_list[i]
        self.param += self.learning_rate / (self.update_num * rewards_dev) * update_direction

    def store(self,path="ARS.pkl"):
        dict={"state":self.state,"mean":self.mean,"mean_diff":self.mean_diff,"var":self.var,"param":self.param}
        with open(path,'wb') as file:
            pickle.dump(dict,file)

    def load(self,path="ARS.pkl"):
        with open(path, 'rb') as file:
            dict = pickle.load(file)
        self.state = dict["state"]
        self.mean = dict["mean"]
        self.mean_diff = dict["mean_diff"]
        self.var = dict["var"]
        self.param = dict["param"]

    def iteration(self,param):
        step=0
        total_reward=0
        distance=None
        state = self.env.reset()
        done = False
        while not done:
            step += 1
            state = np.array(state)
            action = self.forward(state,param)
            state, reward, done, pos = self.env.runStep(action)
            total_reward+=reward
            distance=-pos[1]
        return total_reward,distance,step

    def train(self):
        self.eval()

        for i in range(self.max_epoch):
            pabr=tqdm.tqdm(range(self.episode_num))
            delta_list = np.random.randn(self.episode_num, self.action_dim, self.state_dim)
            pos_reward = np.zeros([self.episode_num])
            neg_reward = np.zeros([self.episode_num])


            for j in pabr:
                delta=delta_list[j]

                param=self.param+delta*self.exploration_noise
                pos_reward[j],_,_ = self.iteration(param)

                param=self.param-delta*self.exploration_noise
                neg_reward[j],_,_ = self.iteration(param)

            best_reward = np.max([neg_reward, pos_reward],axis=0)
            indices = np.argsort(best_reward)


            indices=indices[-self.update_num:]
            delta_list=delta_list[indices]
            pos_reward=pos_reward[indices]
            neg_reward=neg_reward[indices]

            self.update(delta_list,pos_reward,neg_reward)
            reward,distance,_=self.iteration(self.param)
            self.store()
            if self.best_reward is None or reward>=self.best_reward or distance>=self.best_distance:
                self.store("best.pkl")
                if self.best_reward is None:
                    self.best_distance=distance
                    self.best_reward=reward
                if reward>self.best_reward:
                    self.best_reward=reward
                if distance>self.best_distance:
                    self.best_distance=distance
            log="Epoch: {:} | Reward: {:} | Distance: {:}".format(i,reward,distance)
            print("Epoch: {:} | Reward: {:} | Distance: {:}".format(i,reward,distance))
            with open("log.txt",'a') as file:
                file.write(log+"\n")
    def eval(self):
        reward, distance, _ = self.iteration(self.param)
        print("Eval | Reward: {:} | Distance: {:}".format(reward,distance))